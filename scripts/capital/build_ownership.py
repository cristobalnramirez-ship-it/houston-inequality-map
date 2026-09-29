"""
Who owns single-family homes, by ZIP code, from county appraisal-district records.

Sources
  Harris County:  HCAD "Real_acct_owner.zip" (real_acct.txt + owners.txt), from
                  https://hcad.org/hcad-online-services/pdata/   (tab-delimited text)
  Cameron County: Cameron Appraisal District GIS parcel export (shapefile with owner data),
                  https://www.cameroncad.org/cad/exports/GIS/parcels_public.zip

Usage
  python build_ownership.py --source hcad    --input data/raw/Real_acct_owner.zip --out data/capital/ownership_zip.json
  python build_ownership.py --source cameron --input data/raw/parcels_public.zip  --out data/capital/ownership_zip_cameron.json [--inspect]

Measures per ZIP, over single-family homes (Texas state property class A1):
  homes                    single-family parcels
  company_owned_pct        % owned by a company or a large rental operator (see owner_classes.py)
  institutional_pct        % owned by large single-family-rental operators (Invitation Homes, AMH, Progress ...)
  out_of_state_owner_pct   % whose owner's mailing address is outside Texas
  absentee_pct             % whose owner's mailing address is not the property itself
  recent_sales             homes with an ownership change in the last 36 months (from the appraisal record's
                           new-owner date, when the source has one)
  recent_company_pct       % of those recent changes where the new owner is a company or rental operator

Shares are withheld for ZIPs with fewer than 50 homes (or 20 recent sales).
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
from owner_classes import classify, INVESTOR_TYPES  # noqa: E402

MIN_HOMES, MIN_SALES = 50, 20
csv.field_size_limit(10 ** 8)


def norm_addr(s):
    s = re.sub(r'[^A-Z0-9 ]', ' ', (s or '').upper())
    s = re.sub(r'\b(STREET|ST|AVENUE|AVE|DRIVE|DR|ROAD|RD|LANE|LN|BOULEVARD|BLVD|COURT|CT|CIRCLE|CIR|PLACE|PL|WAY|TRAIL|TRL|PARKWAY|PKWY)\b', '', s)
    return ' '.join(s.split())


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
    """Yield dicts: zip, cls, owner, mail_state, mail_addr, site_addr, new_owner_date."""
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
            yield {
                'zip': m.group(1) if m else None,
                'cls': (row.get('state_class') or '').strip().upper(),
                'owner': owners.get(acct) or row.get('mailto'),
                'mail_state': (row.get('mail_state') or '').strip().upper(),
                'mail_addr': row.get('mail_addr_1'),
                'site_addr': row.get('site_addr_1'),
                'new_owner_date': parse_date(row.get('new_own_dt')),
            }


# Candidate field names for the Cameron CAD parcel export; the first one present is used.
CAMERON_FIELDS = {
    'zip': ['situs_zip', 'SITUS_ZIP', 'situszip', 'prop_zip', 'ZIP', 'zip'],
    'cls': ['state_cd', 'STATE_CD', 'imprv_stat', 'state_code', 'ptd_code', 'STATECODE'],
    'owner': ['file_as_na', 'FILE_AS_NA', 'owner_name', 'OWNER_NAME', 'py_owner_n', 'OWNER', 'owner'],
    'mail_state': ['addr_state', 'ADDR_STATE', 'mail_state', 'MAIL_STATE', 'state', 'STATE'],
    'mail_addr': ['addr_line1', 'ADDR_LINE1', 'addr_line2', 'mail_addr1', 'MAIL_ADDR1', 'address1'],
    'site_addr': ['situs_disp', 'SITUS_DISP', 'situs', 'SITUS', 'situs_addr', 'SITUS_ADDR'],
    'new_owner_date': ['deed_dt', 'DEED_DT', 'deed_date', 'DEED_DATE', 'sale_date', 'SALE_DATE'],
}


def rows_cameron(path, inspect=False):
    import shapefile  # pip install pyshp
    zf = zipfile.ZipFile(path)
    base = next(n[:-4] for n in zf.namelist() if n.lower().endswith('.dbf'))
    r = shapefile.Reader(dbf=io.BytesIO(zf.read(base + '.dbf')), encoding='latin-1')
    names = [f[0] for f in r.fields[1:]]
    pick = {k: next((c for c in cands if c in names), None) for k, cands in CAMERON_FIELDS.items()}
    if inspect or not (pick['owner'] and pick['cls'] and pick['zip']):
        print('Fields in export:', names)
        print('Mapped:', pick)
        for i, rec in enumerate(r.iterRecords()):
            if i >= 3:
                break
            print(dict(zip(names, rec)))
        if not (pick['owner'] and pick['cls'] and pick['zip']):
            raise SystemExit('Update CAMERON_FIELDS with the right field names above.')
    for rec in r.iterRecords():
        d = dict(zip(names, rec))
        z = str(d.get(pick['zip']) or '').strip()[:5]
        yield {
            'zip': z if z.isdigit() else None,
            'cls': str(d.get(pick['cls']) or '').strip().upper(),
            'owner': d.get(pick['owner']),
            'mail_state': str(d.get(pick['mail_state']) or '').strip().upper() if pick['mail_state'] else '',
            'mail_addr': d.get(pick['mail_addr']) if pick['mail_addr'] else None,
            'site_addr': d.get(pick['site_addr']) if pick['site_addr'] else None,
            'new_owner_date': parse_date(str(d.get(pick['new_owner_date']))) if pick['new_owner_date'] else None,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=['hcad', 'cameron'], required=True)
    ap.add_argument('--input', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--asof', default=date.today().isoformat(), help='reference date for "recent" (YYYY-MM-DD)')
    ap.add_argument('--inspect', action='store_true')
    args = ap.parse_args()
    asof = date.fromisoformat(args.asof)
    cutoff = date(asof.year - 3, asof.month, min(asof.day, 28))

    rows = rows_hcad(args.input) if args.source == 'hcad' else rows_cameron(args.input, args.inspect)
    z = defaultdict(Counter)
    types_all = Counter()
    has_dates = False
    for row in rows:
        if not row['zip'] or not row['cls'].startswith('A1'):
            continue
        t = classify(row['owner'])
        types_all[t] += 1
        c = z[row['zip']]
        c['homes'] += 1
        c['t_' + t] += 1
        if t in INVESTOR_TYPES:
            c['investor'] += 1
        if row['mail_state'] and row['mail_state'] not in ('TX', 'TEXAS'):
            c['out_of_state'] += 1
        if row['mail_addr'] and row['site_addr'] and norm_addr(row['mail_addr']) != norm_addr(row['site_addr']):
            c['absentee'] += 1
        if row['new_owner_date']:
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
            'company_owned_pct': share(c['investor'], c['homes'], MIN_HOMES),
            'institutional_pct': share(c['t_institutional'], c['homes'], MIN_HOMES),
            'out_of_state_owner_pct': share(c['out_of_state'], c['homes'], MIN_HOMES),
            'absentee_pct': share(c['absentee'], c['homes'], MIN_HOMES),
            'recent_sales': c['recent'] if has_dates else None,
            'recent_company_pct': share(c['recent_investor'], c['recent'], MIN_SALES) if has_dates else None,
        }
    meta = {'source': args.source, 'asof': args.asof, 'recent_since': cutoff.isoformat(),
            'owner_type_counts': dict(types_all), 'min_homes': MIN_HOMES, 'min_recent_sales': MIN_SALES}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump({'metadata': meta, 'zips': out}, f, indent=1)
    print(f"{len(out)} ZIPs, {sum(types_all.values())} single-family homes; owner types: {dict(types_all)}")


if __name__ == '__main__':
    main()
