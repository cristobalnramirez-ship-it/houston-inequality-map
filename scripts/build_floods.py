import urllib.request, json, os, sys, time

sys.setrecursionlimit(10000)

# Fetch flood zones from FEMA for Houston area in tiles
# The API has a max record count, so we tile the area

base_url = 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query'
bbox = {'xmin': -95.60, 'ymin': 29.60, 'xmax': -95.15, 'ymax': 29.92}
tile_size = 0.08  # degrees per tile

all_features = []
seen_geoms = set()

x = bbox['xmin']
tile_count = 0
while x < bbox['xmax']:
    y = bbox['ymin']
    while y < bbox['ymax']:
        geom = '%f,%f,%f,%f' % (x, y, min(x+tile_size, bbox['xmax']), min(y+tile_size, bbox['ymax']))
        offset = 0
        try:
            while True:
                params = (
                    'where=1%%3D1'
                    '&geometry=%s'
                    '&geometryType=esriGeometryEnvelope'
                    '&inSR=4326'
                    '&spatialRel=esriSpatialRelIntersects'
                    '&outFields=FLD_ZONE,ZONE_SUBTY,SFHA_TF'
                    '&returnGeometry=true'
                    '&outSR=4326'
                    '&f=geojson'
                    '&resultRecordCount=200'
                    '&resultOffset=%d'
                ) % (geom, offset)
                url = base_url + '?' + params
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=30)
                data = json.loads(resp.read())
                feats = data.get('features', [])
                for f in feats:
                    g = f['geometry']
                    if g and g.get('coordinates'):
                        coords = g['coordinates']
                        if g['type'] == 'Polygon' and coords and coords[0]:
                            key = (coords[0][0][0], coords[0][0][1]) if coords[0] else None
                        elif g['type'] == 'MultiPolygon' and coords and coords[0] and coords[0][0]:
                            key = (coords[0][0][0][0], coords[0][0][0][1])
                        else:
                            key = None
                        if key and key not in seen_geoms:
                            seen_geoms.add(key)
                            all_features.append(f)
                # Page until the server stops returning full pages
                if len(feats) < 200 and not data.get('exceededTransferLimit'):
                    break
                offset += len(feats)
                time.sleep(0.3)
            tile_count += 1
        except Exception as e:
            print('Tile error at %.2f,%.2f: %s' % (x, y, e))

        y += tile_size
        time.sleep(0.3)
    x += tile_size

print('Fetched %d unique flood zone features from %d tiles' % (len(all_features), tile_count))

# Classify zones
zone_info = {
    'A': {'flood_risk': 'high', 'desc': 'No Base Flood Elevations determined. 100-year flood zone.'},
    'AE': {'flood_risk': 'high', 'desc': 'Base Flood Elevations determined. 100-year flood zone.'},
    'AH': {'flood_risk': 'high', 'desc': 'Shallow flooding, 100-year flood zone with ponding.'},
    'AO': {'flood_risk': 'high', 'desc': 'Shallow flooding, 100-year flood zone with sheet flow.'},
    'V': {'flood_risk': 'coastal', 'desc': 'Coastal high hazard area, 100-year flood with wave action.'},
    'VE': {'flood_risk': 'coastal', 'desc': 'Coastal high hazard area with BFEs and wave action.'},
    'X': {'flood_risk': 'moderate', 'desc': '500-year flood zone or area with reduced flood risk.'},
    'D': {'flood_risk': 'undetermined', 'desc': 'Possible but undetermined flood hazard.'},
}

# Simplify geometry
def simplify(coords, tol=0.0003):
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

def simplify_geom(geom, tol=0.0003):
    if geom['type'] == 'Polygon':
        return {'type': 'Polygon', 'coordinates': [simplify(ring, tol) for ring in geom['coordinates']]}
    elif geom['type'] == 'MultiPolygon':
        return {'type': 'MultiPolygon', 'coordinates': [[simplify(ring, tol) for ring in poly] for poly in geom['coordinates']]}
    return geom

# Filter to only SFHA zones (high risk) - skip X zones to reduce size
# But keep some X zones for Harvey context
output_features = []
for feat in all_features:
    p = feat['properties']
    fld_zone = p.get('FLD_ZONE', '')
    sfha = p.get('SFHA_TF', '') == 'T'

    if not fld_zone:
        continue

    info = zone_info.get(fld_zone, {'flood_risk': 'unknown', 'desc': 'Flood zone ' + fld_zone})

    # Only keep high-risk and coastal zones (skip X/D to manage file size)
    if not sfha and fld_zone not in ('X',):
        continue
    if fld_zone == 'X' and p.get('ZONE_SUBTY', '') != '0.2 PCT ANNUAL CHANCE FLOOD HAZARD':
        continue

    new_props = {
        'zone': fld_zone,
        'flood_risk': info['flood_risk'],
        'zone_description': info['desc'],
        'sfha': sfha,
    }

    simp_geom = simplify_geom(feat['geometry'])
    output_features.append({
        'type': 'Feature',
        'properties': new_props,
        'geometry': simp_geom,
    })

print('Output features: %d (filtered from %d)' % (len(output_features), len(all_features)))

# Write
with open('data/environment/flood_zones.geojson', 'w') as f:
    json.dump({'type': 'FeatureCollection', 'features': output_features}, f)

size = os.path.getsize('data/environment/flood_zones.geojson')
print('Flood zones file: %.1f MB' % (size/1024/1024))

if size > 2 * 1024 * 1024:
    print('File too large, re-simplifying...')
    with open('data/environment/flood_zones.geojson') as f:
        data = json.load(f)
    for feat in data['features']:
        feat['geometry'] = simplify_geom(feat['geometry'], 0.0006)
    with open('data/environment/flood_zones.geojson', 'w') as f:
        json.dump(data, f)
    size = os.path.getsize('data/environment/flood_zones.geojson')
    print('After re-simplification: %.1f MB' % (size/1024/1024))
