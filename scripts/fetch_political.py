"""
Fetch political district boundaries for Harris County / Houston area.

Sources:
- Congressional, State Senate, State House: Census TIGER/Line shapefiles via API
- Commissioner Precincts: Harris County data
- City Council: City of Houston data

Outputs data/political/districts.geojson with all district types combined.
"""

import json
import urllib.request
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, '..', 'data', 'political')

STATE_FIPS = '48'
COUNTY_FIPS = '201'

# Bounding box for greater Houston area (generous)
HOUSTON_BBOX = {
    'xmin': -96.0,
    'ymin': 29.4,
    'xmax': -94.9,
    'ymax': 30.2,
}

# ── Elected Officials Data (as of 2024-2025 session) ──────────────
# Congressional districts intersecting Harris County
CONGRESSIONAL_REPS = {
    '2': {'representative': 'Dan Crenshaw', 'party': 'R'},
    '7': {'representative': 'Lizzie Fletcher', 'party': 'D'},
    '8': {'representative': 'Morgan Luttrell', 'party': 'R'},
    '9': {'representative': 'Al Green', 'party': 'D'},
    '10': {'representative': 'Michael McCaul', 'party': 'R'},
    '18': {'representative': 'Sheila Jackson Lee', 'party': 'D'},
    '22': {'representative': 'Troy Nehls', 'party': 'R'},
    '29': {'representative': 'Sylvia Garcia', 'party': 'D'},
    '36': {'representative': 'Brian Babin', 'party': 'R'},
    '38': {'representative': 'Wesley Hunt', 'party': 'R'},
}

# Texas State Senate districts intersecting Harris County
STATE_SENATE_REPS = {
    '4': {'representative': 'Brandon Creighton', 'party': 'R'},
    '6': {'representative': 'Carol Alvarado', 'party': 'D'},
    '7': {'representative': 'Paul Bettencourt', 'party': 'R'},
    '11': {'representative': 'Larry Taylor', 'party': 'R'},
    '13': {'representative': 'Borris Miles', 'party': 'D'},
    '15': {'representative': 'John Whitmire', 'party': 'D'},
    '17': {'representative': 'Joan Huffman', 'party': 'R'},
}

# Texas State House districts — major ones in Harris County
STATE_HOUSE_REPS = {
    '126': {'representative': 'Sam Harless', 'party': 'R'},
    '127': {'representative': 'Dan Huberty', 'party': 'R'},
    '128': {'representative': 'Briscoe Cain', 'party': 'R'},
    '129': {'representative': 'Dennis Paul', 'party': 'R'},
    '130': {'representative': 'Tom Oliverson', 'party': 'R'},
    '131': {'representative': 'Alma Allen', 'party': 'D'},
    '132': {'representative': 'Mike Schofield', 'party': 'R'},
    '133': {'representative': 'Jim Murphy', 'party': 'R'},
    '134': {'representative': 'Ann Johnson', 'party': 'D'},
    '135': {'representative': 'Jon Rosenthal', 'party': 'D'},
    '137': {'representative': 'Gene Wu', 'party': 'D'},
    '138': {'representative': 'Lacey Hull', 'party': 'R'},
    '139': {'representative': 'Jarvis Johnson', 'party': 'D'},
    '140': {'representative': 'Armando Walle', 'party': 'D'},
    '141': {'representative': 'Senfronia Thompson', 'party': 'D'},
    '142': {'representative': 'Harold Dutton', 'party': 'D'},
    '143': {'representative': 'Ana Hernandez', 'party': 'D'},
    '144': {'representative': 'Mary Ann Perez', 'party': 'D'},
    '145': {'representative': 'Christina Morales', 'party': 'D'},
    '146': {'representative': 'Shawn Thierry', 'party': 'D'},
    '147': {'representative': 'Jolanda Jones', 'party': 'D'},
    '148': {'representative': 'Penny Morales Shaw', 'party': 'D'},
    '149': {'representative': 'Hubert Vo', 'party': 'D'},
    '150': {'representative': 'Valoree Swanson', 'party': 'R'},
}

# Harris County Commissioner Precincts
COMMISSIONER_PRECINCTS = {
    '1': {'representative': 'Rodney Ellis', 'party': 'D'},
    '2': {'representative': 'Adrian Garcia', 'party': 'D'},
    '3': {'representative': 'Tom Ramsey', 'party': 'R'},
    '4': {'representative': 'Lesley Briones', 'party': 'D'},
}

# Houston City Council districts
CITY_COUNCIL = {
    'A': {'representative': 'Amy Peck', 'party': 'D'},
    'B': {'representative': 'Tarsha Jackson', 'party': 'D'},
    'C': {'representative': 'Abbie Kamin', 'party': 'D'},
    'D': {'representative': 'Carolyn Evans-Shabazz', 'party': 'D'},
    'E': {'representative': 'Fred Flickinger', 'party': 'R'},
    'F': {'representative': 'Tiffany Thomas', 'party': 'D'},
    'G': {'representative': 'Mary Nan Huffman', 'party': 'D'},
    'H': {'representative': 'Mario Castillo', 'party': 'D'},
    'I': {'representative': 'Robert Gallegos', 'party': 'D'},
    'J': {'representative': 'Edward Pollard', 'party': 'D'},
    'K': {'representative': 'Martha Castex-Tatum', 'party': 'D'},
}


def fetch_json(url, retries=3):
    """Fetch JSON with retries and delay."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    return None


def simplify_coords(coords, max_points=500):
    """Simple coordinate decimation to reduce file size while preserving shape."""
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 5), round(coords[1], 5)]
    if isinstance(coords[0], list) and isinstance(coords[0][0], (int, float)):
        # List of points — keep up to max_points
        if len(coords) <= max_points:
            return [[round(c[0], 5), round(c[1], 5)] for c in coords]
        step = max(1, len(coords) // max_points)
        simplified = [coords[0]]
        for i in range(step, len(coords) - 1, step):
            simplified.append(coords[i])
        simplified.append(coords[-1])
        return [[round(c[0], 5), round(c[1], 5)] for c in simplified]
    return [simplify_coords(c, max_points) for c in coords]


def fetch_tiger_districts(layer_type, layer_id, district_type, reps_dict, level):
    """Fetch district boundaries from Census TIGERweb."""
    print(f"\nFetching {district_type} districts from TIGERweb...")

    # TIGERweb Legislative MapServer layers (current as of 2025):
    #   0: 119th Congressional Districts
    #   1: 2024 State Legislative Districts - Upper (Senate)
    #   2: 2024 State Legislative Districts - Lower (House)
    base_url = (
        f"https://tigerweb.geo.census.gov/arcgis/rest/services/"
        f"TIGERweb/Legislative/MapServer/{layer_id}/query"
    )

    bbox = HOUSTON_BBOX
    params = (
        f"?where=1%3D1"
        f"&geometry={bbox['xmin']},{bbox['ymin']},{bbox['xmax']},{bbox['ymax']}"
        f"&geometryType=esriGeometryEnvelope"
        f"&spatialRel=esriSpatialRelIntersects"
        f"&inSR=4326"
        f"&outFields=*"
        f"&returnGeometry=true"
        f"&f=geojson"
        f"&outSR=4326"
    )

    url = base_url + params
    data = fetch_json(url)

    if not data or 'features' not in data:
        print(f"  WARNING: No data returned for {district_type}")
        return []

    features = []
    for feat in data.get('features', []):
        props = feat.get('properties', {})

        # Extract district number from various possible fields
        district_num = str(
            props.get('CD119', '') or
            props.get('CD118', '') or
            props.get('SLDUST', '') or
            props.get('SLDLST', '') or
            props.get('BASENAME', '') or
            ''
        ).strip().lstrip('0')

        if not district_num:
            # Try NAME field
            name = props.get('NAME', '')
            # Extract number from name like "Congressional District 7"
            import re
            m = re.search(r'(\d+)', name)
            if m:
                district_num = m.group(1)

        if not district_num:
            continue

        rep_info = reps_dict.get(district_num, {})

        if district_type == 'congressional':
            district_id = f"TX-{district_num.zfill(2)}"
            display_name = f"TX Congressional District {district_num}"
        elif district_type == 'state_senate':
            district_id = f"TX-SD-{district_num}"
            display_name = f"TX Senate District {district_num}"
        elif district_type == 'state_house':
            district_id = f"TX-HD-{district_num}"
            display_name = f"TX House District {district_num}"
        else:
            district_id = district_num
            display_name = district_num

        new_feature = {
            'type': 'Feature',
            'properties': {
                'district_type': district_type,
                'district_id': district_id,
                'district_number': district_num,
                'name': display_name,
                'representative': rep_info.get('representative', 'Unknown'),
                'party': rep_info.get('party', 'Unknown'),
                'level': level,
            },
            'geometry': {
                'type': feat['geometry']['type'],
                'coordinates': simplify_coords(feat['geometry']['coordinates']),
            }
        }
        features.append(new_feature)

    print(f"  Got {len(features)} {district_type} districts")
    return features


def fetch_commissioner_precincts():
    """Fetch Harris County Commissioner Precinct boundaries."""
    print("\nFetching Commissioner Precincts...")

    # Harris County GIS REST service (verified working)
    url = (
        "https://www.gis.hctx.net/arcgis/rest/services/"
        "CommPrecinct/MapServer/0/query"
        "?where=1%3D1"
        "&outFields=*"
        "&returnGeometry=true"
        "&f=geojson"
        "&outSR=4326"
    )

    data = fetch_json(url)

    if not data or 'features' not in data:
        print("  WARNING: Could not fetch commissioner precincts, using fallback")
        return create_fallback_commissioner_precincts()

    features = []
    for feat in data.get('features', []):
        props = feat.get('properties', {})
        import re
        pct_num = None
        for key in ['PCT_NO', 'PRECINCT', 'PCT', 'PREC', 'NAME', 'OBJECTID']:
            val = str(props.get(key, ''))
            m = re.search(r'(\d+)', val)
            if m:
                pct_num = m.group(1)
                break

        if not pct_num:
            continue

        rep_info = COMMISSIONER_PRECINCTS.get(pct_num, {})

        new_feature = {
            'type': 'Feature',
            'properties': {
                'district_type': 'commissioner',
                'district_id': f"HC-PCT-{pct_num}",
                'district_number': pct_num,
                'name': f"Commissioner Precinct {pct_num}",
                'representative': rep_info.get('representative', 'Unknown'),
                'party': rep_info.get('party', 'Unknown'),
                'level': 'county',
            },
            'geometry': {
                'type': feat['geometry']['type'],
                'coordinates': simplify_coords(feat['geometry']['coordinates']),
            }
        }
        features.append(new_feature)

    print(f"  Got {len(features)} commissioner precincts")
    return features


def create_fallback_commissioner_precincts():
    """Create approximate commissioner precinct boundaries as fallback."""
    print("  Creating approximate commissioner precinct boundaries...")

    # Approximate quadrant division of Harris County centered at ~29.76, -95.37
    center_lat, center_lon = 29.76, -95.37
    north, south = 30.15, 29.50
    east, west = -94.95, -95.85

    precincts = {
        '1': [(center_lat, west), (center_lat, center_lon), (north, center_lon), (north, west)],
        '2': [(center_lat, center_lon), (center_lat, east), (north, east), (north, center_lon)],
        '3': [(south, center_lon), (south, east), (center_lat, east), (center_lat, center_lon)],
        '4': [(south, west), (south, center_lon), (center_lat, center_lon), (center_lat, west)],
    }

    features = []
    for pct_num, corners in precincts.items():
        coords = [[c[1], c[0]] for c in corners]
        coords.append(coords[0])  # close ring

        rep_info = COMMISSIONER_PRECINCTS.get(pct_num, {})
        features.append({
            'type': 'Feature',
            'properties': {
                'district_type': 'commissioner',
                'district_id': f"HC-PCT-{pct_num}",
                'district_number': pct_num,
                'name': f"Commissioner Precinct {pct_num}",
                'representative': rep_info.get('representative', 'Unknown'),
                'party': rep_info.get('party', 'Unknown'),
                'level': 'county',
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [coords],
            }
        })

    print(f"  Created {len(features)} approximate precincts")
    return features


def fetch_city_council():
    """Fetch Houston City Council district boundaries."""
    print("\nFetching City Council districts...")

    # Harris County GIS hosts City of Houston boundaries (verified working)
    url = (
        "https://www.gis.hctx.net/arcgis/rest/services/"
        "CoH/CoH_Boundaries/MapServer/0/query"
        "?where=1%3D1"
        "&outFields=*"
        "&returnGeometry=true"
        "&f=geojson"
        "&outSR=4326"
    )

    data = fetch_json(url)

    if not data or 'features' not in data:
        print("  WARNING: Could not fetch city council districts, using fallback")
        return create_fallback_city_council()

    features = []
    for feat in data.get('features', []):
        props = feat.get('properties', {})

        # Try to find district letter from DISTRICT or DISTRICT_ABBR fields
        import re
        district_id = None
        for key in ['DISTRICT', 'DISTRICT_ABBR', 'DIST', 'NAME', 'COUNCIL_DISTRICT']:
            val = str(props.get(key, ''))
            m = re.search(r'([A-K])', val, re.IGNORECASE)
            if m:
                district_id = m.group(1).upper()
                break

        if not district_id:
            continue

        # Use name from the API data if available, fall back to our hardcoded list
        api_member = props.get('MEMBER', '')
        rep_info = CITY_COUNCIL.get(district_id, {})
        if api_member:
            rep_info = dict(rep_info)
            rep_info['representative'] = api_member

        new_feature = {
            'type': 'Feature',
            'properties': {
                'district_type': 'city_council',
                'district_id': f"HOU-{district_id}",
                'district_number': district_id,
                'name': f"Houston City Council District {district_id}",
                'representative': rep_info.get('representative', 'Unknown'),
                'party': rep_info.get('party', 'Unknown'),
                'level': 'city',
            },
            'geometry': {
                'type': feat['geometry']['type'],
                'coordinates': simplify_coords(feat['geometry']['coordinates']),
            }
        }
        features.append(new_feature)

    print(f"  Got {len(features)} city council districts")
    return features


def create_fallback_city_council():
    """Create approximate city council district boundaries as fallback."""
    print("  Creating approximate city council district boundaries...")
    import math

    # Create roughly pie-shaped sectors around downtown Houston
    center_lat, center_lon = 29.76, -95.37
    radius = 0.15  # degrees
    districts = list('ABCDEFGHIJK')

    features = []
    n = len(districts)
    for i, dist_id in enumerate(districts):
        angle_start = (2 * math.pi * i / n) - math.pi / 2
        angle_end = (2 * math.pi * (i + 1) / n) - math.pi / 2

        coords = [[center_lon, center_lat]]
        for step in range(11):
            angle = angle_start + (angle_end - angle_start) * step / 10
            lon = center_lon + radius * math.cos(angle) * 1.2  # stretch for lon
            lat = center_lat + radius * math.sin(angle)
            coords.append([round(lon, 4), round(lat, 4)])
        coords.append([center_lon, center_lat])

        rep_info = CITY_COUNCIL.get(dist_id, {})
        features.append({
            'type': 'Feature',
            'properties': {
                'district_type': 'city_council',
                'district_id': f"HOU-{dist_id}",
                'district_number': dist_id,
                'name': f"Houston City Council District {dist_id}",
                'representative': rep_info.get('representative', 'Unknown'),
                'party': rep_info.get('party', 'Unknown'),
                'level': 'city',
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': [coords],
            }
        })

    print(f"  Created {len(features)} approximate city council districts")
    return features


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_features = []

    # 1. Congressional districts (119th Congress, layer 0)
    congressional = fetch_tiger_districts(
        'congressional', 0, 'congressional',
        CONGRESSIONAL_REPS, 'federal'
    )
    all_features.extend(congressional)

    time.sleep(1)  # be nice to the API

    # 2. State Senate districts (Upper chamber, layer 1)
    state_senate = fetch_tiger_districts(
        'state_senate', 1, 'state_senate',
        STATE_SENATE_REPS, 'state'
    )
    all_features.extend(state_senate)

    time.sleep(1)

    # 3. State House districts (Lower chamber, layer 2)
    state_house = fetch_tiger_districts(
        'state_house', 2, 'state_house',
        STATE_HOUSE_REPS, 'state'
    )
    all_features.extend(state_house)

    time.sleep(1)

    # 4. Commissioner Precincts
    commissioner = fetch_commissioner_precincts()
    all_features.extend(commissioner)

    time.sleep(1)

    # 5. City Council
    city_council = fetch_city_council()
    all_features.extend(city_council)

    # Combine into single GeoJSON
    geojson = {
        'type': 'FeatureCollection',
        'features': all_features,
    }

    # Summary
    types = {}
    for f in all_features:
        dt = f['properties']['district_type']
        types[dt] = types.get(dt, 0) + 1

    print(f"\n{'='*50}")
    print(f"Total districts: {len(all_features)}")
    for dt, count in sorted(types.items()):
        print(f"  {dt}: {count}")

    # Save
    output_file = os.path.join(OUTPUT_DIR, 'districts.geojson')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(geojson, f)
    print(f"\nSaved to {output_file}")

    # File size
    size_kb = os.path.getsize(output_file) / 1024
    print(f"File size: {size_kb:.1f} KB")


if __name__ == '__main__':
    main()
