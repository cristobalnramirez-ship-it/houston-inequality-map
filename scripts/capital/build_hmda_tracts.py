"""
Mortgage lending by census tract from HMDA (Home Mortgage Disclosure Act) data.

Download (one file per county; any machine with internet):
  curl -o data/raw/hmda_48201.csv "https://ffiec.cfpb.gov/v2/data-browser-api/view/csv?years=2023,2024,2025&counties=48201&loan_purposes=1&actions_taken=1,2,3"
  (48201 = Harris County; 48061 = Cameron County)

Build:
  python build_hmda_tracts.py --csv data/raw/hmda_48201.csv --tracts data/census/income_2020.geojson --out data/capital/hmda_tracts.geojson

Measures (home-purchase loans for 1-4 unit site-built homes, years pooled):
  purchase_loans      loans originated
  investor_share      % of originated purchase loans for an investment property (occupancy_type 3)
  denial_rate         % of owner-occupant purchase applications denied (denied / (originated + approved-not-accepted + denied))
  hispanic_share      % of originated owner-occupant purchase loans to Hispanic or Latino borrowers
  black_share         % of originated owner-occupant purchase loans to Black borrowers

HMDA covers loans, not cash purchases, so it UNDERCOUNTS investor buying: many
investors, especially large ones, pay cash. Shares are withheld for tracts with
fewer than MIN_N loans or applications. Tracts are 2020 census tracts
(HMDA uses 2020 tracts from 2022 onward).
"""

import argparse
import csv
import json
from collections import defaultdict

MIN_N = 20


def pct(a, b):
    return round(100 * a / b, 1) if b >= MIN_N else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--tracts', required=True, help='GeoJSON of 2020 tracts with a tract_id (11-digit GEOID) property')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    t = defaultdict(lambda: defaultdict(int))
    county = defaultdict(int)
    years = set()
    with open(args.csv, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r.get('loan_purpose') != '1':
                continue
            if not (r.get('derived_dwelling_category') or '').startswith('Single Family (1-4 Units):Site-Built'):
                continue
            tract = (r.get('census_tract') or '').strip()
            if len(tract) != 11:
                continue
            years.add(r.get('activity_year'))
            act, occ = r.get('action_taken'), r.get('occupancy_type')
            for bucket in (t[tract], county):
                if act == '1':
                    bucket['orig'] += 1
                    if occ == '3':
                        bucket['orig_investor'] += 1
                    if occ == '1':
                        bucket['orig_owner'] += 1
                        if r.get('derived_ethnicity') == 'Hispanic or Latino':
                            bucket['orig_owner_hisp'] += 1
                        if r.get('derived_race') == 'Black or African American':
                            bucket['orig_owner_black'] += 1
                if occ == '1' and act in ('1', '2', '3'):
                    bucket['apps_owner'] += 1
                    if act == '3':
                        bucket['denied_owner'] += 1

    def metrics(b):
        return {
            'purchase_loans': b['orig'],
            'investor_share': pct(b['orig_investor'], b['orig']),
            'denial_rate': pct(b['denied_owner'], b['apps_owner']),
            'hispanic_share': pct(b['orig_owner_hisp'], b['orig_owner']),
            'black_share': pct(b['orig_owner_black'], b['orig_owner']),
        }

    with open(args.tracts, encoding='utf-8') as f:
        geo = json.load(f)
    feats = []
    for ft in geo['features']:
        tid = str(ft['properties'].get('tract_id'))
        p = {'tract_id': tid, 'name': ft['properties'].get('name')}
        p.update(metrics(t.get(tid, defaultdict(int))))
        feats.append({'type': 'Feature', 'properties': p, 'geometry': ft['geometry']})

    meta = {'years': sorted(y for y in years if y), 'county_benchmark': metrics(county), 'min_n': MIN_N,
            'source': 'CFPB/FFIEC HMDA Data Browser, https://ffiec.cfpb.gov/data-browser/'}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump({'type': 'FeatureCollection', 'metadata': meta, 'features': feats}, f)
    print(f"{len(feats)} tracts; years {meta['years']}; county benchmark {meta['county_benchmark']}")


if __name__ == '__main__':
    main()
