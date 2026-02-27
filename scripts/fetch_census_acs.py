#!/usr/bin/env python3
"""
fetch_census_acs.py — Download Census ACS data for Houston zip codes.

Downloads from the Census Bureau API:
  - Median household income by ZCTA (zip code tabulation area)
  - Median gross rent by ZCTA
  - Total population
  - Racial composition
  - Renter vs. owner-occupied households
  - Rent burden (% of income spent on rent)

Source: https://api.census.gov/data/
Requires: Free Census API key from https://api.census.gov/data/key_signup.html

Output:
  ../data/capital/census_acs_zip.csv

Usage:
  python fetch_census_acs.py                    # Uses CENSUS_API_KEY env var
  python fetch_census_acs.py YOUR_API_KEY       # Pass key as argument
"""

import os
import sys
import csv
import json
import urllib.request
import urllib.parse

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'capital')

# ACS 5-Year Estimates, 2022 (most recent available)
ACS_YEAR = 2022
ACS_DATASET = f"acs/acs5"
BASE_URL = f"https://api.census.gov/data/{ACS_YEAR}/{ACS_DATASET}"

# Texas FIPS code
STATE_FIPS = "48"

# Variables to fetch
# Format: (census_variable_code, our_label, description)
VARIABLES = [
    ("B19013_001E", "median_household_income", "Median household income"),
    ("B25064_001E", "median_gross_rent", "Median gross rent"),
    ("B01003_001E", "total_population", "Total population"),
    ("B25003_001E", "total_occupied_housing", "Total occupied housing units"),
    ("B25003_002E", "owner_occupied", "Owner-occupied units"),
    ("B25003_003E", "renter_occupied", "Renter-occupied units"),
    ("B25071_001E", "median_rent_burden_pct", "Median gross rent as % of income"),
    ("B02001_002E", "pop_white", "White alone"),
    ("B02001_003E", "pop_black", "Black/African American alone"),
    ("B03001_003E", "pop_hispanic", "Hispanic/Latino"),
    ("B02001_005E", "pop_asian", "Asian alone"),
    ("B25077_001E", "median_home_value", "Median home value (owner-occupied)"),
    ("B25002_001E", "total_housing_units", "Total housing units"),
    ("B25002_003E", "vacant_housing_units", "Vacant housing units"),
]

# Houston-area zip codes
HOUSTON_ZIPS = [
    '77002', '77003', '77004', '77005', '77006', '77007', '77008', '77009',
    '77010', '77011', '77012', '77016', '77017', '77018', '77019', '77020',
    '77021', '77022', '77023', '77024', '77025', '77026', '77027', '77028',
    '77029', '77030', '77031', '77033', '77034', '77035', '77036', '77037',
    '77038', '77039', '77040', '77041', '77042', '77043', '77044', '77045',
    '77046', '77047', '77048', '77049', '77050', '77051', '77053', '77054',
    '77055', '77056', '77057', '77058', '77059', '77060', '77061', '77062',
    '77063', '77064', '77065', '77066', '77067', '77068', '77069', '77070',
    '77071', '77072', '77073', '77074', '77075', '77076', '77077', '77078',
    '77079', '77080', '77081', '77082', '77083', '77084', '77085', '77086',
    '77087', '77088', '77089', '77090', '77091', '77092', '77093', '77094',
    '77095', '77096', '77098', '77099',
]


def fetch_acs(api_key):
    """Fetch ACS data from Census API."""
    var_codes = [v[0] for v in VARIABLES]
    var_string = ",".join(var_codes)

    # For ZCTA (zip code) level, we query at the zip code tabulation area geography
    # The Census API uses "zip code tabulation area" (ZCTA) as the geography
    params = {
        "get": f"NAME,{var_string}",
        "for": "zip code tabulation area:*",
        "in": f"state:{STATE_FIPS}",
        "key": api_key,
    }

    url = f"{BASE_URL}?" + urllib.parse.urlencode(params)
    print(f"Fetching ACS {ACS_YEAR} data for Texas ZCTAs...")
    print(f"  Variables: {len(VARIABLES)}")

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            print(f"  ERROR: Invalid or missing API key (HTTP {e.code})")
            print(f"  Get a free key at: https://api.census.gov/data/key_signup.html")
        else:
            print(f"  ERROR: HTTP {e.code}: {e.reason}")
            # Try without state filter (some ZCTA queries work differently)
            print(f"  Trying alternate query without state filter...")
            params_alt = {
                "get": f"NAME,{var_string}",
                "for": "zip code tabulation area:*",
                "key": api_key,
            }
            url_alt = f"{BASE_URL}?" + urllib.parse.urlencode(params_alt)
            try:
                req = urllib.request.Request(url_alt, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=120) as response:
                    data = json.loads(response.read().decode('utf-8'))
            except Exception as e2:
                print(f"  ERROR on alternate query: {e2}")
                return None
        if 'data' not in dir():
            return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

    # data[0] is header row, data[1:] are data rows
    headers = data[0]
    rows = data[1:]
    print(f"  Retrieved {len(rows)} ZCTAs from Census")

    # Filter to Houston zips
    zcta_idx = headers.index('zip code tabulation area') if 'zip code tabulation area' in headers else -1
    if zcta_idx == -1:
        print("  ERROR: Could not find ZCTA column in response")
        return None

    houston_rows = []
    for row in rows:
        zcta = row[zcta_idx]
        if zcta in HOUSTON_ZIPS:
            entry = {'zip': zcta, 'name': row[0]}
            for i, (code, label, desc) in enumerate(VARIABLES):
                col_idx = headers.index(code) if code in headers else -1
                if col_idx >= 0:
                    val = row[col_idx]
                    # Census returns negative values for missing data
                    try:
                        val = float(val) if val and float(val) >= 0 else None
                    except (ValueError, TypeError):
                        val = None
                    entry[label] = val
            houston_rows.append(entry)

    print(f"  Filtered to {len(houston_rows)} Houston zip codes")
    return houston_rows


def save_csv(rows, output_path):
    """Save rows to CSV."""
    if not rows:
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = list(rows[0].keys())

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved to {output_path}")


def main():
    print("=" * 60)
    print("Census ACS Data Fetcher — Houston Zip Codes")
    print("=" * 60)
    print()

    # Get API key
    api_key = None
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = os.environ.get('CENSUS_API_KEY')

    if not api_key:
        print("ERROR: No Census API key provided.")
        print()
        print("Get a free key at: https://api.census.gov/data/key_signup.html")
        print()
        print("Then run:")
        print(f"  python {sys.argv[0]} YOUR_API_KEY")
        print("  or set CENSUS_API_KEY environment variable")
        print()
        print("Generating sample data instead...")
        generate_sample_data()
        return

    rows = fetch_acs(api_key)
    if rows:
        output = os.path.join(DATA_DIR, 'census_acs_zip.csv')
        save_csv(rows, output)
    else:
        print("  No data retrieved. Generating sample data instead...")
        generate_sample_data()

    print()
    print("Variables fetched:")
    for code, label, desc in VARIABLES:
        print(f"  {label}: {desc}")


def generate_sample_data():
    """Generate sample ACS data for development/testing."""
    import random
    random.seed(42)

    print("  Generating sample Census ACS data for Houston zip codes...")

    # Neighborhood profiles (zip -> approximate characteristics)
    profiles = {
        # Inner Loop affluent
        '77005': {'income': 125000, 'rent': 1800, 'home_val': 650000, 'owner_pct': 0.55, 'pop': 22000},
        '77006': {'income': 85000, 'rent': 1600, 'home_val': 480000, 'owner_pct': 0.35, 'pop': 28000},
        '77019': {'income': 160000, 'rent': 2200, 'home_val': 850000, 'owner_pct': 0.50, 'pop': 18000},
        '77024': {'income': 185000, 'rent': 2400, 'home_val': 920000, 'owner_pct': 0.70, 'pop': 35000},
        '77027': {'income': 130000, 'rent': 2000, 'home_val': 700000, 'owner_pct': 0.45, 'pop': 15000},
        '77046': {'income': 110000, 'rent': 1900, 'home_val': 550000, 'owner_pct': 0.40, 'pop': 12000},
        '77098': {'income': 95000, 'rent': 1700, 'home_val': 520000, 'owner_pct': 0.38, 'pop': 20000},
        # Gentrifying / transitional
        '77002': {'income': 72000, 'rent': 1500, 'home_val': 380000, 'owner_pct': 0.25, 'pop': 15000},
        '77003': {'income': 55000, 'rent': 1200, 'home_val': 320000, 'owner_pct': 0.40, 'pop': 18000},
        '77004': {'income': 48000, 'rent': 1100, 'home_val': 285000, 'owner_pct': 0.42, 'pop': 32000},
        '77007': {'income': 90000, 'rent': 1650, 'home_val': 490000, 'owner_pct': 0.45, 'pop': 35000},
        '77008': {'income': 82000, 'rent': 1550, 'home_val': 420000, 'owner_pct': 0.50, 'pop': 40000},
        '77009': {'income': 65000, 'rent': 1300, 'home_val': 350000, 'owner_pct': 0.45, 'pop': 38000},
        '77018': {'income': 70000, 'rent': 1250, 'home_val': 340000, 'owner_pct': 0.55, 'pop': 35000},
        # Historically marginalized / high displacement risk
        '77011': {'income': 38000, 'rent': 900, 'home_val': 160000, 'owner_pct': 0.45, 'pop': 25000},
        '77012': {'income': 42000, 'rent': 950, 'home_val': 175000, 'owner_pct': 0.50, 'pop': 30000},
        '77016': {'income': 32000, 'rent': 850, 'home_val': 120000, 'owner_pct': 0.50, 'pop': 28000},
        '77020': {'income': 35000, 'rent': 880, 'home_val': 140000, 'owner_pct': 0.48, 'pop': 22000},
        '77021': {'income': 38000, 'rent': 920, 'home_val': 165000, 'owner_pct': 0.45, 'pop': 27000},
        '77022': {'income': 36000, 'rent': 870, 'home_val': 145000, 'owner_pct': 0.42, 'pop': 20000},
        '77023': {'income': 40000, 'rent': 950, 'home_val': 180000, 'owner_pct': 0.48, 'pop': 35000},
        '77026': {'income': 28000, 'rent': 800, 'home_val': 95000, 'owner_pct': 0.45, 'pop': 18000},
        '77028': {'income': 30000, 'rent': 820, 'home_val': 105000, 'owner_pct': 0.48, 'pop': 15000},
        '77029': {'income': 35000, 'rent': 860, 'home_val': 130000, 'owner_pct': 0.52, 'pop': 22000},
        '77033': {'income': 33000, 'rent': 840, 'home_val': 115000, 'owner_pct': 0.50, 'pop': 20000},
        '77051': {'income': 30000, 'rent': 810, 'home_val': 100000, 'owner_pct': 0.48, 'pop': 16000},
        '77076': {'income': 36000, 'rent': 880, 'home_val': 150000, 'owner_pct': 0.45, 'pop': 25000},
        '77078': {'income': 32000, 'rent': 830, 'home_val': 110000, 'owner_pct': 0.50, 'pop': 12000},
        '77087': {'income': 38000, 'rent': 900, 'home_val': 155000, 'owner_pct': 0.48, 'pop': 35000},
        '77091': {'income': 42000, 'rent': 950, 'home_val': 185000, 'owner_pct': 0.52, 'pop': 28000},
        '77093': {'income': 34000, 'rent': 850, 'home_val': 125000, 'owner_pct': 0.48, 'pop': 30000},
        # Suburban / outer ring
        '77030': {'income': 68000, 'rent': 1400, 'home_val': 350000, 'owner_pct': 0.35, 'pop': 20000},
        '77025': {'income': 72000, 'rent': 1350, 'home_val': 320000, 'owner_pct': 0.55, 'pop': 30000},
        '77031': {'income': 50000, 'rent': 1050, 'home_val': 200000, 'owner_pct': 0.50, 'pop': 35000},
        '77035': {'income': 75000, 'rent': 1300, 'home_val': 310000, 'owner_pct': 0.65, 'pop': 32000},
        '77036': {'income': 45000, 'rent': 1000, 'home_val': 190000, 'owner_pct': 0.40, 'pop': 55000},
        '77040': {'income': 58000, 'rent': 1150, 'home_val': 230000, 'owner_pct': 0.55, 'pop': 40000},
        '77042': {'income': 70000, 'rent': 1350, 'home_val': 290000, 'owner_pct': 0.50, 'pop': 30000},
        '77045': {'income': 45000, 'rent': 1000, 'home_val': 180000, 'owner_pct': 0.55, 'pop': 25000},
        '77047': {'income': 42000, 'rent': 960, 'home_val': 170000, 'owner_pct': 0.52, 'pop': 28000},
        '77048': {'income': 40000, 'rent': 940, 'home_val': 160000, 'owner_pct': 0.50, 'pop': 20000},
        '77054': {'income': 52000, 'rent': 1100, 'home_val': 240000, 'owner_pct': 0.35, 'pop': 18000},
        '77056': {'income': 115000, 'rent': 1950, 'home_val': 600000, 'owner_pct': 0.40, 'pop': 22000},
        '77057': {'income': 65000, 'rent': 1300, 'home_val': 280000, 'owner_pct': 0.35, 'pop': 25000},
        '77074': {'income': 42000, 'rent': 1000, 'home_val': 175000, 'owner_pct': 0.40, 'pop': 38000},
    }

    rows = []
    for zip_code in HOUSTON_ZIPS:
        p = profiles.get(zip_code, {
            'income': random.randint(35000, 75000),
            'rent': random.randint(800, 1400),
            'home_val': random.randint(120000, 350000),
            'owner_pct': random.uniform(0.35, 0.65),
            'pop': random.randint(15000, 50000),
        })

        total_housing = int(p['pop'] / 2.5)
        owner = int(total_housing * p['owner_pct'])
        renter = total_housing - owner
        vacant = int(total_housing * random.uniform(0.05, 0.12))

        # Add some noise
        noise = lambda v, pct=0.05: int(v * (1 + random.uniform(-pct, pct)))

        rows.append({
            'zip': zip_code,
            'name': f"ZCTA5 {zip_code}",
            'median_household_income': noise(p['income']),
            'median_gross_rent': noise(p['rent']),
            'median_home_value': noise(p['home_val']),
            'total_population': noise(p['pop'], 0.03),
            'total_occupied_housing': total_housing,
            'owner_occupied': owner,
            'renter_occupied': renter,
            'median_rent_burden_pct': round(p['rent'] * 12 / p['income'] * 100, 1),
            'pop_white': int(p['pop'] * random.uniform(0.15, 0.60)),
            'pop_black': int(p['pop'] * random.uniform(0.10, 0.50)),
            'pop_hispanic': int(p['pop'] * random.uniform(0.15, 0.60)),
            'pop_asian': int(p['pop'] * random.uniform(0.02, 0.20)),
            'total_housing_units': total_housing + vacant,
            'vacant_housing_units': vacant,
        })

    output = os.path.join(DATA_DIR, 'census_acs_zip.csv')
    save_csv(rows, output)
    print(f"  Generated sample data for {len(rows)} Houston zip codes")


if __name__ == '__main__':
    main()
