"""
Fetch census tract geometry and ACS income/demographics for Harris County, TX.

Sources:
- Geometry: TIGERweb ArcGIS REST API (no key needed)
- ACS data: Census Bureau API (free key required)

Get a free Census API key at: https://api.census.gov/data/key_signup.html
Set as environment variable CENSUS_API_KEY or pass as argument.
"""

import json
import urllib.request
import os
import sys

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'census')

# Harris County FIPS: State=48, County=201
STATE_FIPS = '48'
COUNTY_FIPS = '201'

# TIGERweb ArcGIS REST endpoint for census tracts
TIGER_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
    "Tracts_Blocks/MapServer/8/query"
)

# Census ACS 5-Year API
ACS_URL = "https://api.census.gov/data/{year}/acs/acs5"


def fetch_tract_geometry(max_features=2000):
    """Fetch census tract polygons from TIGERweb (paginated)."""
    print("Fetching tract geometry from TIGERweb...")
    all_features = []
    offset = 0
    page_size = 500

    while offset < max_features:
        params = (
            f"?where=STATE%3D%27{STATE_FIPS}%27+AND+COUNTY%3D%27{COUNTY_FIPS}%27"
            f"&outFields=GEOID,NAME,AREALAND"
            f"&returnGeometry=true"
            f"&f=geojson"
            f"&resultOffset={offset}"
            f"&resultRecordCount={page_size}"
        )
        url = TIGER_URL + params
        print(f"  Fetching offset {offset}...")

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode('utf-8'))

        features = data.get('features', [])
        if not features:
            break
        all_features.extend(features)
        print(f"  Got {len(features)} tracts (total: {len(all_features)})")

        if len(features) < page_size:
            break
        offset += page_size

    geojson = {
        "type": "FeatureCollection",
        "features": all_features
    }
    print(f"Total tracts: {len(all_features)}")
    return geojson


def fetch_acs_data(year=2022, api_key=None):
    """Fetch ACS income and demographic data for Harris County tracts."""
    if not api_key:
        api_key = os.environ.get('CENSUS_API_KEY')

    if not api_key:
        print("WARNING: No Census API key provided.")
        print("Get one free at: https://api.census.gov/data/key_signup.html")
        print("Set CENSUS_API_KEY environment variable or pass as argument.")
        return None

    # ACS variables:
    # B19013_001E = Median household income
    # B01003_001E = Total population
    # B17001_002E = Population below poverty level
    # B02001_002E = White alone
    # B02001_003E = Black alone
    # B03003_003E = Hispanic or Latino
    # B02001_005E = Asian alone
    variables = "B19013_001E,B01003_001E,B17001_002E,B02001_002E,B02001_003E,B03003_003E,B02001_005E"

    url = (
        f"{ACS_URL.format(year=year)}"
        f"?get=NAME,{variables}"
        f"&for=tract:*"
        f"&in=state:{STATE_FIPS}%20county:{COUNTY_FIPS}"
        f"&key={api_key}"
    )

    print(f"Fetching ACS {year} data...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.loads(response.read().decode('utf-8'))

    # First row is headers
    headers = data[0]
    rows = data[1:]
    print(f"Got {len(rows)} tract records")

    # Convert to dict keyed by GEOID
    result = {}
    for row in rows:
        record = dict(zip(headers, row))
        geoid = STATE_FIPS + COUNTY_FIPS + record.get('tract', '')
        total_pop = safe_int(record.get('B01003_001E'))

        result[geoid] = {
            'median_income': safe_int(record.get('B19013_001E')),
            'population': total_pop,
            'poverty_pop': safe_int(record.get('B17001_002E')),
            'white': safe_int(record.get('B02001_002E')),
            'black': safe_int(record.get('B02001_003E')),
            'hispanic': safe_int(record.get('B03003_003E')),
            'asian': safe_int(record.get('B02001_005E')),
        }

        # Compute percentages
        if total_pop and total_pop > 0:
            r = result[geoid]
            r['pct_white'] = round(100 * (r['white'] or 0) / total_pop, 1)
            r['pct_black'] = round(100 * (r['black'] or 0) / total_pop, 1)
            r['pct_hispanic'] = round(100 * (r['hispanic'] or 0) / total_pop, 1)
            r['pct_asian'] = round(100 * (r['asian'] or 0) / total_pop, 1)
            r['poverty_rate'] = round(100 * (r['poverty_pop'] or 0) / total_pop, 1)

    return result


def safe_int(val):
    """Safely convert Census value to int, handling negatives (missing data)."""
    try:
        v = int(val)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def join_data(geometry, acs_data):
    """Join ACS data to tract geometry by GEOID."""
    if not acs_data:
        return geometry

    for feature in geometry['features']:
        geoid = feature['properties'].get('GEOID', '')
        if geoid in acs_data:
            feature['properties'].update(acs_data[geoid])

    return geometry


def main():
    api_key = sys.argv[1] if len(sys.argv) > 1 else None

    # Step 1: Get geometry
    geometry = fetch_tract_geometry()

    # Step 2: Get ACS data (if API key available)
    acs_data = fetch_acs_data(year=2022, api_key=api_key)

    # Step 3: Join
    result = join_data(geometry, acs_data)

    # Step 4: Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    income_file = os.path.join(OUTPUT_DIR, 'income_2020.geojson')
    with open(income_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(f"Saved income data to {income_file}")

    # Also save a race-focused version with just demographic fields
    race_geojson = json.loads(json.dumps(result))  # deep copy
    for feature in race_geojson['features']:
        props = feature['properties']
        keep = ['GEOID', 'NAME', 'population', 'pct_white', 'pct_black',
                'pct_hispanic', 'pct_asian', 'poverty_rate']
        feature['properties'] = {k: v for k, v in props.items() if k in keep}

    race_file = os.path.join(OUTPUT_DIR, 'race_2020.geojson')
    with open(race_file, 'w', encoding='utf-8') as f:
        json.dump(race_geojson, f, indent=2)
    print(f"Saved race data to {race_file}")


if __name__ == '__main__':
    main()
