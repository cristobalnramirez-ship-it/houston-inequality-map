"""
Build Houston's HOLC redlining layer from Mapping Inequality.

Source: Digital Scholarship Lab, University of Richmond — Mapping Inequality
(Nelson, Winling, et al.), via the census-tract crosswalk published at
https://github.com/americanpanorama/mapping-inequality-census-crosswalk
License: CC BY-NC-SA 4.0 — credit Mapping Inequality wherever the layer is shown.

The crosswalk splits each HOLC area along 2010 census-tract lines, so this
script dissolves the pieces back into one polygon per HOLC area (area_id).

Requires: shapely  (pip install shapely)
"""

import json
import os
import urllib.request
from collections import defaultdict

from shapely.geometry import shape, mapping
from shapely.ops import unary_union

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'redlining', 'houston_holc.geojson')
URL = ("https://raw.githubusercontent.com/americanpanorama/mapping-inequality-census-crosswalk/"
       "main/MIv3Areas_2010TractCrosswalk.geojson")
KEEP = ['area_id', 'city', 'state', 'city_survey', 'cat', 'grade', 'label', 'res', 'com', 'ind']


def rnd(c):
    if isinstance(c[0], (int, float)):
        return [round(c[0], 5), round(c[1], 5)]
    return [rnd(x) for x in c]


def main():
    print(f"Downloading {URL} (~70 MB)...")
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode('utf-8'))

    parts = defaultdict(list)
    for f in data['features']:
        p = f['properties']
        if p.get('city') == 'Houston' and p.get('state') == 'TX':
            parts[p['area_id']].append(f)

    out = []
    for area_id, fs in parts.items():
        geom = unary_union([shape(f['geometry']).buffer(0) for f in fs]).buffer(0)
        props = {k: fs[0]['properties'].get(k) for k in KEEP}
        g = (props['grade'] or '').strip().upper()
        props['grade'] = props['holc_grade'] = g if g in ('A', 'B', 'C', 'D') else None
        props['label'] = (props['label'] or '').strip() or None
        geo = mapping(geom)
        out.append({'type': 'Feature', 'properties': props,
                    'geometry': {'type': geo['type'], 'coordinates': rnd(geo['coordinates'])}})

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'type': 'FeatureCollection', 'features': out}, f)
    print(f"Saved {len(out)} HOLC areas to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
