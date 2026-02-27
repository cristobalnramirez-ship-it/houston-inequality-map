import json, os, sys

sys.setrecursionlimit(10000)

# Load capital data (has the indicator values + zip codes)
with open('data/capital/houston_capital.geojson') as f:
    cap = json.load(f)

cap_by_zip = {}
for feat in cap['features']:
    z = feat['properties']['zip']
    cap_by_zip[z] = feat['properties']

print("Capital data: %d zip codes" % len(cap_by_zip))

# Load Texas ZCTA boundaries
with open('data/capital/tx_zcta.json') as f:
    zcta = json.load(f)

print("Texas ZCTAs: %d" % len(zcta['features']))

# Filter for our zip codes
matched = []
unmatched = []
for feat in zcta['features']:
    z = feat['properties'].get('ZCTA5CE10', '')
    if z in cap_by_zip:
        matched.append((z, feat))

matched_zips = set(z for z, _ in matched)
for z in cap_by_zip:
    if z not in matched_zips:
        unmatched.append(z)

print("Matched: %d, Unmatched: %d" % (len(matched), len(unmatched)))
if unmatched:
    print("Unmatched zips:", unmatched[:10])

# Simplify geometry
def simplify(coords, tol=0.001):
    if len(coords) <= 4:
        return coords
    f, l = coords[0], coords[-1]
    md = mi = 0
    for i in range(1, len(coords)-1):
        dx, dy = l[0]-f[0], l[1]-f[1]
        if dx == 0 and dy == 0:
            d = ((coords[i][0]-f[0])**2+(coords[i][1]-f[1])**2)**0.5
        else:
            t = max(0, min(1, ((coords[i][0]-f[0])*dx+(coords[i][1]-f[1])*dy)/(dx*dx+dy*dy)))
            d = ((coords[i][0]-(f[0]+t*dx))**2+(coords[i][1]-(f[1]+t*dy))**2)**0.5
        if d > md:
            md, mi = d, i
    if md > tol:
        return simplify(coords[:mi+1], tol)[:-1] + simplify(coords[mi:], tol)
    return [f, l]

def simplify_geom(geom, tol=0.001):
    if geom['type'] == 'Polygon':
        return {
            'type': 'Polygon',
            'coordinates': [simplify(ring, tol) for ring in geom['coordinates']]
        }
    elif geom['type'] == 'MultiPolygon':
        return {
            'type': 'MultiPolygon',
            'coordinates': [[simplify(ring, tol) for ring in poly] for poly in geom['coordinates']]
        }
    return geom

# Build output features
features = []
for z, feat in matched:
    props = dict(cap_by_zip[z])  # copy capital properties
    geom = simplify_geom(feat['geometry'], 0.0008)
    features.append({
        'type': 'Feature',
        'properties': props,
        'geometry': geom,
    })

# For unmatched zips, keep the original hexagon geometry from capital data
for feat in cap['features']:
    z = feat['properties']['zip']
    if z not in matched_zips:
        features.append(feat)

output = {
    'type': 'FeatureCollection',
    'features': features,
}

# Backup original
with open('data/capital/houston_capital.geojson') as f:
    orig = json.load(f)
with open('data/capital/houston_capital_original.geojson', 'w') as f:
    json.dump(orig, f)

# Write new
with open('data/capital/houston_capital.geojson', 'w') as f:
    json.dump(output, f)

size = os.path.getsize('data/capital/houston_capital.geojson')
print("Output: %d features, %.1f KB" % (len(features), size/1024))

# Count coord points
total_pts = 0
for feat in features:
    g = feat['geometry']
    if g['type'] == 'Polygon':
        for ring in g['coordinates']:
            total_pts += len(ring)
    elif g['type'] == 'MultiPolygon':
        for poly in g['coordinates']:
            for ring in poly:
                total_pts += len(ring)
print("Total coordinate points: %d" % total_pts)

# Clean up
os.remove('data/capital/tx_zcta.json')
