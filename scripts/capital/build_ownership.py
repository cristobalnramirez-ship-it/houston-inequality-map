"""
Who owns single-family homes, by ZIP code, from county appraisal-district records.

Sources
  Harris County:  HCAD "Real_acct_owner.zip" (real_acct.txt + owners.txt), from
                  https://hcad.org/hcad-online-services/pdata/   (tab-delimited text)
  Cameron County: Cameron Appraisal District GIS parcel export (shapefile with owner data),
                  https://www.cameroncad.org/cad/exports/GIS/parcels_public.zip

Usage
  python build_ownership.py --source hcad    --input data/raw/Real_acct_owner.zip --out data/capital/ownership_zip.json
  python build_ownership.py --source cameron --input data/raw/parcels_public.zip  --out OUT.json \
         --areas data/census/tracts.geojson --area-id tract_id [--inspect]

Measures per ZIP (or per polygon with --areas), over single-family homes (Texas state property class A1 in
Harris; class A with a building in Cameron, which does not split out mobile homes on owned land):
  homes                    single-family parcels
  company_owned_pct        % owned by a company or a large rental operator (see owner_classes.py),
                           not counting company-held homes built in the last two years (developer inventory)
  institutional_pct        % owned by large single-family-rental operators (Invitation Homes, AMH, Progress ...),
                           matched by holding-entity name or by the operator's own office address
  new_build_company        company-held homes built in the last two years (excluded above)
  out_of_state_owner_pct   % whose owner's mailing address is outside Texas
  absentee_pct             % whose owner's mailing address is not the property itself
  no_homestead_pct         % without a homestead exemption, i.e. not claimed as the owner's home
                           (Cameron only; the HCAD file used here has no exemption codes)
  recent_sales             homes with an ownership change in the last 36 months (from the appraisal record's
                           new-owner date, when the source has one)
  recent_company_pct       % of those recent changes where the new owner is a company or rental operator
                           (existing homes only: homes built in the last two years are left out of both)

Shares are withheld for areas with fewer than 50 homes (or 20 recent sales).
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from owner_classes import classify, operator, operator_by_address, normalize, INVESTOR_TYPES  # noqa: E402

MIN_HOMES, MIN_SALES = 50, 20
csv.field_size_limit(10 ** 8)


def norm_addr(s):
    s = re.sub(r'[^A-Z0-9 ]', ' ', (s or '').upper())
    s = re.sub(r'\b(STREET|ST|AVENUE|AVE|DRIVE|DR|ROAD|RD|LANE|LN|BOULEVARD|BLVD|COURT|CT|CIRCLE|CIR|PLACE|PL|WAY|TRAIL|TRL|PARKWAY|PKWY)\b', '', s)
    return ' '.join(s.split())


_DIRS = {'N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW', 'NORTH', 'SOUTH', 'EAST', 'WEST'}


def same_place(mail, site):
    """True when a mailing address is the property itself: same house number and street name,
    ignoring directionals, street types and unit numbers (sources format these differently)."""
    a = [t for t in norm_addr(mail).split() if t not in _DIRS]
    b = [t for t in norm_addr(site).split() if t not in _DIRS]
    if not a or not b or not a[0].isdigit() or a[0] != b[0]:
        return False
    return bool(set(a[1:3]) & set(b[1:3]))


def parse_date(s):
    s = (s or '').strip()
    for fmt, n in (('%m/%d/%Y', 10), ('%Y-%m-%d', 10), ('%Y%m%d', 8)):
        try:
            return datetime.strptime(s[:n], fmt).date()
        except ValueError:
            continue
    return None


def open_member(zf, suffix):
    name = next((n for n in zf.namelist() if n.lower().endswith(suffix)), None)
    if not name:
        raise SystemExit(f"{suffix} not found in zip; members: {zf.namelist()[:20]}")
    return io.TextIOWrapper(zf.open(name), encoding='latin-1', newline='')


def rows_hcad(path):
    """Yield dicts: zip, home (single-family class A1), owner, mail_state, mail_addr, site_addr, new_owner_date, yr_built."""
    zf = zipfile.ZipFile(path)
    owners = {}
    with open_member(zf, 'owners.txt') as f:
        r = csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
        for row in r:
            acct = (row.get('acct') or '').strip()
            if row.get('ln_num', '1').strip() in ('1', '01', '') and acct and acct not in owners:
                owners[acct] = row.get('name')
    with open_member(zf, 'real_acct.txt') as f:
        r = csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
        for row in r:
            acct = (row.get('acct') or '').strip()
            m = re.search(r'\b(7\d{4})\b', (row.get('site_addr_3') or '') + ' ' + (row.get('site_addr_2') or ''))
            cls = (row.get('state_class') or '').strip().upper()
            yield {
                'zip': m.group(1) if m else None,
                'home': cls.startswith('A1'),
                'owner': owners.get(acct) or row.get('mailto'),
                'mail_state': (row.get('mail_state') or '').strip().upper(),
                'mail_addr': row.get('mail_addr_1'),
                'site_addr': row.get('site_addr_1'),
                'new_owner_date': parse_date(row.get('new_own_dt')),
                'yr_built': int(y) if (y := (row.get('yr_impr') or '').strip()).isdigit() else None,
            }


# Cameron Appraisal District GIS export (parcels_public.zip, checked Sept. 2026):
#   stateCd 'A' = single-family residential (Cameron does not split A1/A2), owner, addr1/addrState (mailing),
#   situsNo/sitPfx/sitStr/sitSfx (site), sitZip (blank for ~2/3 of homes), exms (exemption codes; 'HS' =
#   homestead), deedDt (latest deed, YYYY-MM-DD; 1900-01-01 = unknown), yrBuilt, lvgArea.
# Geometry is in NAD83 Texas South State Plane (ft); parcels are placed by the centre of their bounding box.


def rows_cameron(path, inspect=False):
    import shapefile  # pip install pyshp
    from pyproj import Transformer  # pip install pyproj
    zf = zipfile.ZipFile(path)
    base = next(n[:-4] for n in zf.namelist() if n.lower().endswith('.dbf'))
    r = shapefile.Reader(shp=io.BytesIO(zf.read(base + '.shp')), shx=io.BytesIO(zf.read(base + '.shx')),
                         dbf=io.BytesIO(zf.read(base + '.dbf')), encoding='latin-1')
    names = [f[0] for f in r.fields[1:]]
    if inspect:
        print('Fields in export:', names)
        for i, rec in enumerate(r.iterRecords()):
            if i >= 3:
                break
            print(dict(zip(names, rec)))
    to_wgs = Transformer.from_crs(zf.read(base + '.prj').decode('latin-1'), 'EPSG:4326', always_xy=True)
    for i, rec in enumerate(r.iterRecords()):
        d = rec.as_dict()
        if str(d.get('stateCd') or '').strip().upper() != 'A' or not (d.get('lvgArea') or 0) > 0:
            continue                                   # single-family homes with a building only
        lon = lat = None
        try:
            shp = r.shape(i)                           # a few parcels in the export have empty geometry
        except shapefile.ShapefileException:
            shp = None
        if shp is not None and getattr(shp, 'bbox', None) is not None and len(shp.points):
            x0, y0, x1, y1 = shp.bbox
            lon, lat = to_wgs.transform((x0 + x1) / 2, (y0 + y1) / 2)
        z = str(d.get('sitZip') or '').strip()[:5]
        deed = parse_date(str(d.get('deedDt') or ''))
        site = ' '.join(str(d.get(k) or '').strip() for k in ('situsNo', 'sitPfx', 'sitStr', 'sitSfx'))
        exms = {e.strip() for e in str(d.get('exms') or '').upper().split(',')}
        yield {
            'zip': z if z.isdigit() else None,
            'home': True,
            'lon': lon, 'lat': lat,
            'owner': d.get('owner'),
            'mail_state': str(d.get('addrState') or '').strip().upper(),
            'mail_addr': d.get('addr1'),
            'site_addr': site,
            'new_owner_date': deed if deed and deed.year > 1900 else None,
            'yr_built': d.get('yrBuilt') or None,
            'homestead': 'HS' in exms,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=['hcad', 'cameron'], required=True)
    ap.add_argument('--input', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--asof', default=date.today().isoformat(), help='reference date for "recent" (YYYY-MM-DD)')
    ap.add_argument('--label', help='how the map names this data, e.g. "HCAD 2026 certified roll"')
    ap.add_argument('--areas', help='GeoJSON of polygons to total by (e.g. census tracts); homes are placed by '
                                    'their coordinates, so the source must have them (Cameron does, HCAD does not)')
    ap.add_argument('--area-id', default='tract_id', help='property of --areas that identifies each polygon')
    ap.add_argument('--inspect', action='store_true')
    ap.add_argument('--report', help='also write a CSV of the largest company owners and shared mailing addresses (for checking the rules)')
    args = ap.parse_args()
    asof = date.fromisoformat(args.asof)
    cutoff = date(asof.year - 3, asof.month, min(asof.day, 28))

    rows = rows_hcad(args.input) if args.source == 'hcad' else rows_cameron(args.input, args.inspect)
    locate = None
    if args.areas:
        from shapely.geometry import shape, Point
        from shapely.strtree import STRtree
        with open(args.areas, encoding='utf-8') as f:
            feats = json.load(f)['features']
        polys = [shape(ft['geometry']) for ft in feats]
        ids = [str(ft['properties'][args.area_id]) for ft in feats]
        tree = STRtree(polys)

        def locate(row):
            if row.get('lon') is None:
                return None
            pt = Point(row['lon'], row['lat'])
            for i in tree.query(pt):
                if polys[i].contains(pt):
                    return ids[i]
            return None
    unplaced = 0
    z = defaultdict(Counter)
    types_all = Counter()
    ops = Counter()          # homes by operator: matched by owner name
    ops_addr = Counter()     # added by the operator's own office address
    managed = Counter()      # company-owned homes billed to a manager's address, owner not identified
    top_names, top_mail = Counter(), Counter()
    has_dates = False
    has_homestead = False
    new_build_company_all = 0
    for row in rows:
        if not row['home']:
            continue
        key = locate(row) if locate else row['zip']
        if not key:
            unplaced += 1
            continue
        t = classify(row['owner'])
        op = operator(row['owner'])
        if op:
            ops[op] += 1
        elif t == 'company':
            op, how = operator_by_address(norm_addr(row['mail_addr']), row['mail_state'], row['owner'])
            if how == 'office':
                ops_addr[op] += 1
                t = 'institutional'
            elif how == 'managed':
                managed[op] += 1
        types_all[t] += 1
        if t in INVESTOR_TYPES or t == 'unknown':
            top_names[(normalize(row['owner']), t, op or '')] += 1
            top_mail[(norm_addr(row['mail_addr']), row['mail_state'])] += 1
        c = z[key]
        c['homes'] += 1
        if row.get('homestead') is not None:
            has_homestead = True
            c['homestead'] += row['homestead']
        c['t_' + t] += 1
        # Homes built in the last two years and held by a company are mostly small developers' unsold
        # inventory (townhome LLCs), not landlords: count them separately.
        new_build = bool(row.get('yr_built') and row['yr_built'] >= asof.year - 2)
        if new_build and t == 'company':
            c['new_build_company'] += 1
            new_build_company_all += 1
        elif t in INVESTOR_TYPES:
            c['investor'] += 1
        if row['mail_state'] and row['mail_state'] not in ('TX', 'TEXAS'):
            c['out_of_state'] += 1
        if row['mail_addr'] and row['site_addr'] and not same_place(row['mail_addr'], row['site_addr']):
            c['absentee'] += 1
        if row['new_owner_date'] and not new_build:
            has_dates = True
            if row['new_owner_date'] >= cutoff:
                c['recent'] += 1
                if t in INVESTOR_TYPES:
                    c['recent_investor'] += 1

    def share(a, b, n):
        return round(100 * a / b, 1) if b >= n else None

    out = {}
    for zp, c in z.items():
        out[zp] = {
            'homes': c['homes'],
            'new_build_company': c['new_build_company'],
            'company_owned_pct': share(c['investor'], c['homes'], MIN_HOMES),
            'institutional_pct': share(c['t_institutional'], c['homes'], MIN_HOMES),
            'out_of_state_owner_pct': share(c['out_of_state'], c['homes'], MIN_HOMES),
            'absentee_pct': share(c['absentee'], c['homes'], MIN_HOMES),
            'no_homestead_pct': share(c['homes'] - c['homestead'], c['homes'], MIN_HOMES) if has_homestead else None,
            'recent_sales': c['recent'] if has_dates else None,
            'recent_company_pct': share(c['recent_investor'], c['recent'], MIN_SALES) if has_dates else None,
        }
    meta = {'source': args.source, 'asof': args.asof, 'label': args.label, 'recent_since': cutoff.isoformat(),
            'owner_type_counts': dict(types_all), 'operator_counts_by_name': dict(ops.most_common()),
            'operator_counts_added_by_office_address': dict(ops_addr.most_common()),
            'operator_counts_total': dict((ops + ops_addr).most_common()),
            'managed_for_unidentified_owners': dict(managed),
            'new_build_company_excluded': new_build_company_all, 'new_build_since': asof.year - 2,
            'min_homes': MIN_HOMES, 'min_recent_sales': MIN_SALES,
            'by': f'{args.areas}:{args.area_id}' if args.areas else 'site ZIP', 'homes_not_placed': unplaced}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump({'metadata': meta, ('areas' if args.areas else 'zips'): out}, f, indent=1)
    print(f"{len(out)} areas, {sum(types_all.values())} single-family homes ({unplaced} not placed); owner types: {dict(types_all)}")
    print('Large operators (by name):', dict(ops.most_common()))
    print('Added by office address:', dict(ops_addr.most_common()))
    print('Total:', dict((ops + ops_addr).most_common()))
    print('Managed for unidentified owners:', dict(managed))
    if args.report:
        with open(args.report, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['kind', 'key', 'type', 'operator', 'homes'])
            for (n, t, op), k in top_names.most_common(500):
                w.writerow(['owner_name', n, t, op, k])
            for (a, st), k in top_mail.most_common(300):
                w.writerow(['mailing_address', f'{a}, {st}', '', '', k])
        print('Report:', args.report)


if __name__ == '__main__':
    main()
