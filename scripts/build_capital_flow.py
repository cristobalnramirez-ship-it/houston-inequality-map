"""
Build the Capital Flow layer (data/capital/capital_flow.geojson) from real data only.

Inputs (all in data/capital/):
  zhvi_houston_zips.csv   Zillow Home Value Index (ZHVI), all homes, mid-tier, smoothed & seasonally
                          adjusted, monthly, filtered to the map's ZIPs.
                          Full file: https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv
  zori_houston_zips.csv   Zillow Observed Rent Index (ZORI), all homes + multifamily, smoothed, monthly.
                          Full file: https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uc_sfrcondomfr_sm_month.csv
  acs2024_5yr_houston_zips.json
                          Census ACS 2020-2024 5-year estimates by ZCTA (tables B01003, B19013, B25003,
                          B25064, B25070, B25077) via the Census Reporter API.
  zcta2010_houston.geojson
                          ZCTA boundaries.

To refresh: download the two full Zillow files, then run
  python build_capital_flow.py --zhvi PATH_TO_FULL_ZHVI.csv --zori PATH_TO_FULL_ZORI.csv
(without arguments it uses the committed extracts).

Every indicator is a direct, descriptive measure. There is deliberately no composite
"displacement risk" score: a credible one should come from a published method
(e.g. the Urban Displacement Project typology), not invented weights.
"""

import argparse
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(HERE, '..', 'data', 'capital')


def load_series(path, zips):
    with open(path, encoding='utf-8') as f:
        r = csv.reader(f)
        h = next(r)
        zip_col = h.index('RegionName') if 'RegionName' in h else h.index('zip')
        first_date = next(i for i, c in enumerate(h) if c[:2] in ('19', '20') and '-' in c)
        dates = h[first_date:]
        out = {}
        for row in r:
            z = row[zip_col].zfill(5)
            if z in zips:
                out[z] = {d: (float(v) if v else None) for d, v in zip(dates, row[first_date:])}
    return dates, out


def pct_change(series, d0, d1):
    a, b = series.get(d0), series.get(d1)
    if a and b:
        return round(100 * (b - a) / a, 1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zhvi', default=os.path.join(CAP, 'zhvi_houston_zips.csv'))
    ap.add_argument('--zori', default=os.path.join(CAP, 'zori_houston_zips.csv'))
    args = ap.parse_args()

    with open(os.path.join(CAP, 'zcta2010_houston.geojson'), encoding='utf-8') as f:
        geo = json.load(f)
    zips = {ft['properties']['zip'] for ft in geo['features']}

    zd, zhvi = load_series(args.zhvi, zips)
    rd, zori = load_series(args.zori, zips)
    latest = min(zd[-1], rd[-1])                    # same month for both
    y, m = latest[:4], latest[5:]
    def back(years):
        return f"{int(y) - years}{latest[4:]}"
    d1y, d3y, d10y = back(1), back(3), back(10)

    with open(os.path.join(CAP, 'acs2024_5yr_houston_zips.json'), encoding='utf-8') as f:
        acs_raw = json.load(f)
    acs = acs_raw['response']['data']
    release = acs_raw['response']['release']['name']

    def est(g, k):
        t = acs.get('86000US' + g, {}).get(k[:6], {})
        return (t.get('estimate') or {}).get(k)

    def moe(g, k):
        t = acs.get('86000US' + g, {}).get(k[:6], {})
        return (t.get('error') or {}).get(k)

    feats = []
    for ft in geo['features']:
        z = ft['properties']['zip']
        v, r = zhvi.get(z, {}), zori.get(z, {})
        pop = est(z, 'B01003001')
        inc, inc_moe = est(z, 'B19013001'), moe(z, 'B19013001')
        inc_reliable = bool(inc and inc_moe is not None and inc_moe / inc <= 0.30 and (pop or 0) >= 2000)
        hh, renters = est(z, 'B25003001'), est(z, 'B25003003')
        univ = est(z, 'B25070001')
        burden = sum(est(z, f'B25070{c:03d}') or 0 for c in (7, 8, 9, 10))
        not_computed = est(z, 'B25070011') or 0
        computed = (univ or 0) - not_computed
        value_now, rent_now = v.get(latest), r.get(latest)

        p = {
            'zip': z,
            'home_value': round(value_now) if value_now else None,
            'value_change_1y': pct_change(v, d1y, latest),
            'value_change_10y': pct_change(v, d10y, latest),
            'rent': round(rent_now) if rent_now else None,
            'rent_change_1y': pct_change(r, d1y, latest),
            'rent_change_3y': pct_change(r, d3y, latest),
            'median_income': inc,
            'median_income_moe': inc_moe,
            'price_to_income': round(value_now / inc, 1) if (value_now and inc and inc_reliable) else None,
            'rent_burdened_pct': round(100 * burden / computed, 1) if computed >= 100 else None,
            'renter_pct': round(100 * renters / hh, 1) if hh and hh >= 100 else None,
            'population': pop,
            'value_series': [round(v[d]) if v.get(d) else None for d in [back(k) for k in range(10, -1, -1)]],
            'rent_series': [round(r[d]) if r.get(d) else None for d in [back(k) for k in range(10, -1, -1)]],
        }
        if not inc_reliable:
            p['acs_note'] = 'Income estimate unreliable (small population or margin of error above 30%)'
        feats.append({'type': 'Feature', 'properties': p, 'geometry': ft['geometry']})

    meta = {
        'latest_month': latest,
        'series_years': [int(y) - k for k in range(10, -1, -1)],
        'acs_release': release,
        'sources': {
            'zhvi': 'https://www.zillow.com/research/data/ (ZHVI, all homes, mid-tier, SA)',
            'zori': 'https://www.zillow.com/research/data/ (ZORI, all homes + multifamily)',
            'acs': 'U.S. Census Bureau ACS 5-year via https://censusreporter.org',
        },
    }
    out = os.path.join(CAP, 'capital_flow.geojson')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'type': 'FeatureCollection', 'metadata': meta, 'features': feats}, f)
    print(f"Wrote {len(feats)} ZIPs to {out}; latest month {latest}; ACS {release}")


if __name__ == '__main__':
    main()
