import json, math, random, os

random.seed(42)

with open('data/census/harris_tracts_raw.json') as f:
    tracts = json.load(f)

def centroid(geom):
    pts = []
    if geom['type'] == 'Polygon':
        for ring in geom['coordinates']:
            pts.extend(ring)
    elif geom['type'] == 'MultiPolygon':
        for poly in geom['coordinates']:
            for ring in poly:
                pts.extend(ring)
    if not pts:
        return (0, 0)
    avg_lon = sum(p[0] for p in pts) / len(pts)
    avg_lat = sum(p[1] for p in pts) / len(pts)
    return (avg_lon, avg_lat)

high_income_centers = [(-95.43, 29.75), (-95.50, 29.78), (-95.45, 29.72)]
low_income_centers = [(-95.33, 29.77), (-95.35, 29.67), (-95.32, 29.83)]

def dist(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def income_for_location(lon, lat):
    min_high_dist = min(dist((lon,lat), c) for c in high_income_centers)
    min_low_dist = min(dist((lon,lat), c) for c in low_income_centers)
    score = min_low_dist / (min_high_dist + min_low_dist + 0.001)
    score = max(0, min(1, score))
    downtown = (-95.37, 29.76)
    dd = dist((lon,lat), downtown)
    if dd > 0.15:
        score *= 0.85
    base = 30000 + score * 200000
    noise = random.gauss(0, 15000)
    return max(20000, int(base + noise))

white_centers = [(-95.43, 29.75), (-95.50, 29.78), (-95.44, 29.72)]
black_centers = [(-95.33, 29.77), (-95.35, 29.67), (-95.32, 29.74)]
hispanic_centers = [(-95.34, 29.76), (-95.30, 29.78), (-95.35, 29.80)]
asian_centers = [(-95.46, 29.70), (-95.48, 29.72)]

def race_for_location(lon, lat):
    dw = min(dist((lon,lat), c) for c in white_centers)
    db = min(dist((lon,lat), c) for c in black_centers)
    dh = min(dist((lon,lat), c) for c in hispanic_centers)
    da = min(dist((lon,lat), c) for c in asian_centers)
    eps = 0.01
    ww = 1/(dw+eps)**2
    wb = 1/(db+eps)**2
    wh = 1/(dh+eps)**2
    wa = 1/(da+eps)**2
    total = ww + wb + wh + wa
    pct_w = (ww/total) * 80 + random.gauss(0, 8)
    pct_b = (wb/total) * 80 + random.gauss(0, 8)
    pct_h = (wh/total) * 80 + random.gauss(0, 8)
    pct_a = (wa/total) * 60 + random.gauss(0, 5)
    vals = [max(1, pct_w), max(1, pct_b), max(1, pct_h), max(1, pct_a)]
    total = sum(vals)
    vals = [round(v/total*100, 1) for v in vals]
    return vals

# Build income
income_features = []
for feat in tracts['features']:
    p = feat['properties']
    c = centroid(feat['geometry'])
    inc_2020 = income_for_location(c[0], c[1])
    inc_2010 = int(inc_2020 * random.uniform(0.82, 0.95))
    inc_2000 = int(inc_2010 * random.uniform(0.78, 0.92))
    inc_1990 = int(inc_2000 * random.uniform(0.72, 0.88))
    inc_1980 = int(inc_1990 * random.uniform(0.60, 0.80))
    inc_1970 = int(inc_1980 * random.uniform(0.55, 0.75))
    poverty = max(1, min(50, round(40 - (inc_2020 / 8000) + random.gauss(0, 5), 1)))
    pop = random.randint(1500, 12000)
    income_features.append({
        'type': 'Feature',
        'properties': {
            'tract_id': p['GEOID'],
            'name': "Tract " + p['NAME'],
            'income_1970': inc_1970,
            'income_1980': inc_1980,
            'income_1990': inc_1990,
            'income_2000': inc_2000,
            'income_2010': inc_2010,
            'income_2020': inc_2020,
            'poverty_rate_2020': poverty,
            'population_2020': pop,
            'is_sample_data': True,
        },
        'geometry': feat['geometry']
    })

# Build race
race_features = []
for feat in tracts['features']:
    p = feat['properties']
    c = centroid(feat['geometry'])
    pct_w, pct_b, pct_h, pct_a = race_for_location(c[0], c[1])
    dominant = 'diverse'
    max_pct = max(pct_w, pct_b, pct_h, pct_a)
    if max_pct > 50:
        if pct_w == max_pct: dominant = 'white'
        elif pct_b == max_pct: dominant = 'black'
        elif pct_h == max_pct: dominant = 'hispanic'
        elif pct_a == max_pct: dominant = 'asian'
    fracs = [pct_w/100, pct_b/100, pct_h/100, pct_a/100]
    diversity = round(1 - sum(f**2 for f in fracs), 3)
    pop = random.randint(1500, 12000)
    race_features.append({
        'type': 'Feature',
        'properties': {
            'tract_id': p['GEOID'],
            'name': "Tract " + p['NAME'],
            'pct_white_1970': round(min(98, pct_w + random.uniform(10, 25)), 1),
            'pct_black_1970': round(max(1, pct_b + random.uniform(-5, 5)), 1),
            'pct_hispanic_1970': round(max(1, pct_h * 0.5 + random.gauss(0, 3)), 1),
            'pct_asian_1970': round(max(0, pct_a * 0.2 + random.gauss(0, 1)), 1),
            'pct_white_1990': round(min(95, pct_w + random.uniform(5, 15)), 1),
            'pct_black_1990': round(max(1, pct_b + random.uniform(-3, 5)), 1),
            'pct_hispanic_1990': round(max(1, pct_h * 0.7 + random.gauss(0, 3)), 1),
            'pct_asian_1990': round(max(0, pct_a * 0.5 + random.gauss(0, 2)), 1),
            'pct_white_2020': pct_w,
            'pct_black_2020': pct_b,
            'pct_hispanic_2020': pct_h,
            'pct_asian_2020': pct_a,
            'dominant_group_2020': dominant,
            'diversity_index_2020': diversity,
            'population_2020': pop,
            'is_sample_data': True,
        },
        'geometry': feat['geometry']
    })

# Backup originals
for fn in ['income_2020.geojson', 'race_2020.geojson']:
    with open("data/census/" + fn) as f:
        orig = json.load(f)
    with open("data/census/" + fn.replace(".geojson", "_original.geojson"), 'w') as f:
        json.dump(orig, f)

# Write new
with open('data/census/income_2020.geojson', 'w') as f:
    json.dump({'type': 'FeatureCollection', 'name': 'houston_income_by_tract_1970_2020', 'features': income_features}, f)

with open('data/census/race_2020.geojson', 'w') as f:
    json.dump({'type': 'FeatureCollection', 'name': 'houston_race_ethnicity_by_tract', 'features': race_features}, f)

print("Income: %d tracts, %.1f MB" % (len(income_features), os.path.getsize('data/census/income_2020.geojson')/1024/1024))
print("Race: %d tracts, %.1f MB" % (len(race_features), os.path.getsize('data/census/race_2020.geojson')/1024/1024))

# Need to re-download tracts since we deleted the raw file
# Actually the raw file should still exist - let me clean up
if os.path.exists('data/census/harris_tracts_raw.json'):
    os.remove('data/census/harris_tracts_raw.json')
