"""
Fetch real ACS 5-Year data from Census API and update existing GeoJSON files.

Replaces synthetic 2020 values in income_2020.geojson and race_2020.geojson
with real Census data while keeping synthetic historical decade values (1970-2010).

Works without an API key at lower rate limits.
"""

import json
import urllib.request
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'census')

STATE_FIPS = '48'
COUNTY_FIPS = '201'

ACS_URL = "https://api.census.gov/data/2022/acs/acs5"

# ACS variables to fetch:
# B19013_001E = Median household income
# B01003_001E = Total population
# B17001_001E = Total poverty universe
# B17001_002E = Population below poverty level
# B03002_001E = Total (for race/ethnicity)
# B03002_003E = White alone, not Hispanic
# B03002_004E = Black alone, not Hispanic
# B03002_006E = Asian alone, not Hispanic
# B03002_012E = Hispanic or Latino
VARIABLES = (
    "B19013_001E,B01003_001E,B17001_001E,B17001_002E,"
    "B03002_001E,B03002_003E,B03002_004E,B03002_006E,B03002_012E"
)


def safe_int(val):
    """Safely convert Census value to int, handling negatives (missing data)."""
    try:
        v = int(val)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def fetch_acs_data(api_key=None):
    """Fetch ACS 5-Year data for all Harris County tracts."""
    url = (
        f"{ACS_URL}"
        f"?get=NAME,{VARIABLES}"
        f"&for=tract:*"
        f"&in=state:{STATE_FIPS}%20county:{COUNTY_FIPS}"
    )
    if api_key:
        url += f"&key={api_key}"

    print(f"Fetching ACS 2022 data from Census API...")
    print(f"  URL: {url[:100]}...")

    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=120) as response:
        data = json.loads(response.read().decode('utf-8'))

    headers = data[0]
    rows = data[1:]
    print(f"  Got {len(rows)} tract records")

    result = {}
    for row in rows:
        record = dict(zip(headers, row))
        tract = record.get('tract', '')
        geoid = STATE_FIPS + COUNTY_FIPS + tract

        total_pop = safe_int(record.get('B01003_001E'))
        median_income = safe_int(record.get('B19013_001E'))
        poverty_universe = safe_int(record.get('B17001_001E'))
        poverty_pop = safe_int(record.get('B17001_002E'))

        race_total = safe_int(record.get('B03002_001E'))
        white = safe_int(record.get('B03002_003E'))
        black = safe_int(record.get('B03002_004E'))
        asian = safe_int(record.get('B03002_006E'))
        hispanic = safe_int(record.get('B03002_012E'))

        # Compute percentages using race/ethnicity total
        denom = race_total or total_pop or 0
        pct_white = round(100 * (white or 0) / denom, 1) if denom > 0 else None
        pct_black = round(100 * (black or 0) / denom, 1) if denom > 0 else None
        pct_asian = round(100 * (asian or 0) / denom, 1) if denom > 0 else None
        pct_hispanic = round(100 * (hispanic or 0) / denom, 1) if denom > 0 else None

        # Poverty rate
        poverty_rate = None
        if poverty_universe and poverty_universe > 0 and poverty_pop is not None:
            poverty_rate = round(100 * poverty_pop / poverty_universe, 1)

        # Dominant group
        pcts = {
            'white': pct_white or 0,
            'black': pct_black or 0,
            'hispanic': pct_hispanic or 0,
            'asian': pct_asian or 0,
        }
        max_group = max(pcts, key=pcts.get)
        dominant = max_group if pcts[max_group] >= 50 else 'diverse'

        # Diversity index (Simpson's)
        diversity_index = None
        if denom > 0:
            fracs = [(v / 100) for v in pcts.values()]
            diversity_index = round(1 - sum(f * f for f in fracs), 2)

        result[geoid] = {
            'median_income': median_income,
            'population': total_pop,
            'poverty_rate': poverty_rate,
            'pct_white': pct_white,
            'pct_black': pct_black,
            'pct_hispanic': pct_hispanic,
            'pct_asian': pct_asian,
            'dominant_group': dominant,
            'diversity_index': diversity_index,
        }

    return result


def update_income_geojson(acs_data):
    """Update income GeoJSON with real 2020 values."""
    income_file = os.path.join(DATA_DIR, 'income_2020.geojson')
    print(f"\nUpdating {income_file}...")

    with open(income_file, 'r', encoding='utf-8') as f:
        geojson = json.load(f)

    matched = 0
    unmatched = 0
    for feature in geojson['features']:
        props = feature['properties']
        tract_id = props.get('tract_id', '')

        if tract_id in acs_data:
            acs = acs_data[tract_id]
            # Replace 2020 values with real data
            if acs['median_income'] is not None:
                props['income_2020'] = acs['median_income']
            if acs['poverty_rate'] is not None:
                props['poverty_rate_2020'] = acs['poverty_rate']
            if acs['population'] is not None:
                props['population_2020'] = acs['population']
            props['is_sample_data'] = False
            matched += 1
        else:
            unmatched += 1

    print(f"  Matched: {matched}, Unmatched: {unmatched}")

    with open(income_file, 'w', encoding='utf-8') as f:
        json.dump(geojson, f)
    print(f"  Saved (no indentation for smaller file size)")

    return matched


def update_race_geojson(acs_data):
    """Update race GeoJSON with real 2020 values."""
    race_file = os.path.join(DATA_DIR, 'race_2020.geojson')
    print(f"\nUpdating {race_file}...")

    with open(race_file, 'r', encoding='utf-8') as f:
        geojson = json.load(f)

    matched = 0
    unmatched = 0
    for feature in geojson['features']:
        props = feature['properties']
        tract_id = props.get('tract_id', '')

        if tract_id in acs_data:
            acs = acs_data[tract_id]
            # Replace 2020 values with real data
            if acs['pct_white'] is not None:
                props['pct_white_2020'] = acs['pct_white']
            if acs['pct_black'] is not None:
                props['pct_black_2020'] = acs['pct_black']
            if acs['pct_hispanic'] is not None:
                props['pct_hispanic_2020'] = acs['pct_hispanic']
            if acs['pct_asian'] is not None:
                props['pct_asian_2020'] = acs['pct_asian']
            if acs['dominant_group'] is not None:
                props['dominant_group_2020'] = acs['dominant_group']
            if acs['diversity_index'] is not None:
                props['diversity_index_2020'] = acs['diversity_index']
            if acs['population'] is not None:
                props['population_2020'] = acs['population']
            props['is_sample_data'] = False
            matched += 1
        else:
            unmatched += 1

    print(f"  Matched: {matched}, Unmatched: {unmatched}")

    with open(race_file, 'w', encoding='utf-8') as f:
        json.dump(geojson, f)
    print(f"  Saved (no indentation for smaller file size)")

    return matched


def main():
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('CENSUS_API_KEY')

    if api_key:
        print(f"Using Census API key: {api_key[:8]}...")
    else:
        print("No API key provided — using Census API without key (lower rate limit)")

    acs_data = fetch_acs_data(api_key=api_key)

    if not acs_data:
        print("ERROR: No data returned from Census API")
        sys.exit(1)

    print(f"\nFetched data for {len(acs_data)} tracts")

    # Show a few examples
    sample_ids = list(acs_data.keys())[:3]
    for gid in sample_ids:
        d = acs_data[gid]
        print(f"  {gid}: income=${d['median_income']}, "
              f"W={d['pct_white']}% B={d['pct_black']}% "
              f"H={d['pct_hispanic']}% A={d['pct_asian']}%")

    income_matched = update_income_geojson(acs_data)
    race_matched = update_race_geojson(acs_data)

    print(f"\nDone! Updated {income_matched} income tracts and {race_matched} race tracts with real ACS 2022 data.")


if __name__ == '__main__':
    main()
