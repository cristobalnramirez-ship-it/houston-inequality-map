"""
Fetch EPA Toxic Release Inventory (TRI) facilities for Harris County, TX.

Source: EPA Envirofacts REST API
https://data.epa.gov/efservice/

No API key required.
"""

import json
import urllib.request
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'environment')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'tri_sites.geojson')

# EPA Envirofacts TRI facility endpoint for Harris County, TX
# Returns JSON, paginated (1000 rows max per request)
BASE_URL = "https://data.epa.gov/efservice/tri_facility/state_abbr/TX/county_name/HARRIS"

# Additional detail from TRI release data
RELEASE_URL = "https://data.epa.gov/efservice/tri_release_qty/state_abbr/TX/county_name/HARRIS"


def fetch_page(url, offset=0, count=1000):
    """Fetch a single page from the EPA API."""
    page_url = f"{url}/rows/{offset}:{offset + count}/json"
    print(f"  Fetching: {page_url}")
    req = urllib.request.Request(page_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode('utf-8'))


def fetch_all_pages(url, max_rows=5000):
    """Fetch all pages from the EPA API."""
    all_rows = []
    offset = 0
    page_size = 1000

    while offset < max_rows:
        rows = fetch_page(url, offset, page_size)
        if not rows:
            break
        all_rows.extend(rows)
        print(f"  Retrieved {len(all_rows)} rows so far")
        if len(rows) < page_size:
            break
        offset += page_size

    return all_rows


def facilities_to_geojson(facilities):
    """Convert EPA facility records to GeoJSON."""
    features = []

    for fac in facilities:
        lat = fac.get('LATITUDE')
        lon = fac.get('LONGITUDE')
        if lat is None or lon is None:
            continue

        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            continue

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "facility_name": fac.get('FACILITY_NAME', ''),
                "address": fac.get('STREET_ADDRESS', ''),
                "city": fac.get('CITY_NAME', ''),
                "zip": fac.get('ZIP_CODE', ''),
                "latitude": lat,
                "longitude": lon,
                "industry": fac.get('INDUSTRY_SECTOR', fac.get('SIC_CODE', '')),
                "tri_facility_id": fac.get('TRI_FACILITY_ID', ''),
            }
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "EPA Toxics Release Inventory (TRI)",
            "region": "Harris County, TX",
            "url": BASE_URL,
        },
        "features": features
    }


def fetch_tri():
    print("Fetching TRI facility data for Harris County, TX...")
    facilities = fetch_all_pages(BASE_URL)
    print(f"Total facilities: {len(facilities)}")

    geojson = facilities_to_geojson(facilities)
    print(f"GeoJSON features with coordinates: {len(geojson['features'])}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)

    print(f"Saved to {OUTPUT_FILE}")
    return geojson


if __name__ == '__main__':
    fetch_tri()
