"""
Fetch HOLC redlining data for Houston from the Mapping Inequality project.

Source: Digital Scholarship Lab, University of Richmond
https://dsl.richmond.edu/panorama/redlining/

The GeoJSON is available from their GitHub mirror or direct download.
"""

import json
import urllib.request
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'redlining')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'houston_holc.geojson')

# Mapping Inequality / DSL Richmond GeoJSON URL for Houston
# This URL may change — check https://github.com/americanpanorama/mapping-inequality-census-crosswalk
HOLC_URL = (
    "https://raw.githubusercontent.com/americanpanorama/mapping-inequality/"
    "main/geojson/TXHouston1940.geojson"
)

# Alternative: Direct from DSL Richmond API
# HOLC_URL = "https://dsl.richmond.edu/panorama/redlining/static/downloads/geojson/TXHouston1940.geojson"


def fetch_redlining():
    print(f"Fetching HOLC redlining data from: {HOLC_URL}")

    req = urllib.request.Request(HOLC_URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode('utf-8'))

    num_features = len(data.get('features', []))
    print(f"Downloaded {num_features} HOLC zones")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"Saved to {OUTPUT_FILE}")
    return data


if __name__ == '__main__':
    fetch_redlining()
