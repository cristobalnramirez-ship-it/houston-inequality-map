"""
Fetch FEMA flood zone data for Harris County, TX.

Source: FEMA National Flood Hazard Layer (NFHL) ArcGIS REST API
https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer

No API key required. Data is paginated (1000 features max per request).
"""

import json
import urllib.request
import urllib.parse
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'environment')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'flood_zones.geojson')

# FEMA NFHL MapServer — Layer 28 = S_FLD_HAZ_AR (Flood Hazard Areas)
FEMA_URL = (
    "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query"
)

# Harris County bounding box (approximate)
HARRIS_BBOX = "-95.9,29.5,-94.9,30.1"


def fetch_page(offset=0, page_size=1000):
    """Fetch a single page of flood zone features."""
    params = {
        'where': "DFIRM_ID LIKE '%48201%' OR DFIRM_ID LIKE '%48339%'",
        'geometry': HARRIS_BBOX,
        'geometryType': 'esriGeometryEnvelope',
        'inSR': '4326',
        'spatialRel': 'esriSpatialRelIntersects',
        'outFields': 'FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,DEPTH',
        'returnGeometry': 'true',
        'outSR': '4326',
        'f': 'geojson',
        'resultOffset': str(offset),
        'resultRecordCount': str(page_size),
    }

    url = FEMA_URL + '?' + urllib.parse.urlencode(params)
    print(f"  Fetching offset {offset}...")

    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode('utf-8'))


def classify_zone(properties):
    """Add human-readable flood risk classification."""
    zone = properties.get('FLD_ZONE', '')
    sfha = properties.get('SFHA_TF', '')

    if zone in ('A', 'AE', 'AH', 'AO', 'A99'):
        properties['flood_risk'] = 'high'
        properties['zone_description'] = '1% annual chance flood (100-year floodplain)'
    elif zone in ('V', 'VE'):
        properties['flood_risk'] = 'coastal'
        properties['zone_description'] = 'Coastal high hazard area with wave action'
    elif zone == 'X' and 'SHADED' in (properties.get('ZONE_SUBTY') or '').upper():
        properties['flood_risk'] = 'moderate'
        properties['zone_description'] = '0.2% annual chance flood (500-year floodplain)'
    else:
        properties['flood_risk'] = 'minimal'
        properties['zone_description'] = 'Minimal flood hazard area'

    return properties


def fetch_flood_zones(max_features=10000):
    """Fetch all flood zone features for Harris County."""
    print("Fetching FEMA flood zone data for Harris County area...")
    all_features = []
    offset = 0
    page_size = 1000

    while offset < max_features:
        data = fetch_page(offset, page_size)
        features = data.get('features', [])

        if not features:
            break

        # Classify each feature
        for f in features:
            f['properties'] = classify_zone(f['properties'])

        all_features.extend(features)
        print(f"  Retrieved {len(all_features)} features so far")

        if len(features) < page_size:
            break
        offset += page_size

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "source": "FEMA National Flood Hazard Layer",
            "region": "Harris County, TX area",
            "note": "Simplified for visualization. See FEMA Map Service Center for official data."
        },
        "features": all_features
    }

    print(f"Total flood zone features: {len(all_features)}")
    return geojson


def main():
    geojson = fetch_flood_zones()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)

    print(f"Saved to {OUTPUT_FILE}")

    # Print summary
    risk_counts = {}
    for feat in geojson['features']:
        risk = feat['properties'].get('flood_risk', 'unknown')
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
    print("Risk classification summary:")
    for risk, count in sorted(risk_counts.items()):
        print(f"  {risk}: {count} features")


if __name__ == '__main__':
    main()
