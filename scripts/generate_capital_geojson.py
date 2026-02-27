#!/usr/bin/env python3
"""
generate_capital_geojson.py — Generate houston_capital.geojson for the Capital Flow layer.

Merges:
  - Houston zip code polygon boundaries (approximate or from TIGER/Line)
  - Census ACS socioeconomic data
  - Computed capital flow indicators (8 metrics)

Output:
  ../data/capital/houston_capital.geojson

Each Feature has properties:
  zip, name, neighborhood,
  median_household_income, median_gross_rent, median_home_value,
  total_population, renter_pct, rent_burden_pct,
  listing_velocity, price_trajectory, rental_yield,
  investor_activity, dom_shift, displacement_risk,
  flip_rate, affordability_cliff
"""

import os
import sys
import csv
import json
import math

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'capital')

# ── Houston Zip Code Centroids & Neighborhood Names ──────────
# Approximate centroids for Houston zip codes (lat, lng)
# Used to generate polygon boundaries when TIGER data isn't available

ZIP_INFO = {
    '77002': {'lat': 29.7545, 'lng': -95.3600, 'name': 'Downtown', 'size': 0.018},
    '77003': {'lat': 29.7511, 'lng': -95.3420, 'name': 'East Downtown / EaDo', 'size': 0.022},
    '77004': {'lat': 29.7230, 'lng': -95.3580, 'name': 'Third Ward / Midtown S', 'size': 0.028},
    '77005': {'lat': 29.7170, 'lng': -95.4170, 'name': 'West University', 'size': 0.020},
    '77006': {'lat': 29.7380, 'lng': -95.3870, 'name': 'Montrose', 'size': 0.022},
    '77007': {'lat': 29.7710, 'lng': -95.4080, 'name': 'Heights East', 'size': 0.025},
    '77008': {'lat': 29.7900, 'lng': -95.4180, 'name': 'Heights West', 'size': 0.028},
    '77009': {'lat': 29.7890, 'lng': -95.3550, 'name': 'Northside / Near Northside', 'size': 0.028},
    '77010': {'lat': 29.7480, 'lng': -95.3650, 'name': 'Downtown Core', 'size': 0.012},
    '77011': {'lat': 29.7380, 'lng': -95.3150, 'name': 'Magnolia Park / Harrisburg', 'size': 0.025},
    '77012': {'lat': 29.7140, 'lng': -95.2970, 'name': 'Gulfgate / Park Place', 'size': 0.028},
    '77016': {'lat': 29.8350, 'lng': -95.3050, 'name': 'Kashmere Gardens / Trinity', 'size': 0.040},
    '77017': {'lat': 29.6850, 'lng': -95.2670, 'name': 'Park Place / Edgebrook', 'size': 0.030},
    '77018': {'lat': 29.8110, 'lng': -95.4480, 'name': 'Oak Forest / Garden Oaks', 'size': 0.028},
    '77019': {'lat': 29.7560, 'lng': -95.4050, 'name': 'River Oaks / Montrose N', 'size': 0.022},
    '77020': {'lat': 29.7640, 'lng': -95.3130, 'name': 'Denver Harbor / Fifth Ward', 'size': 0.028},
    '77021': {'lat': 29.7000, 'lng': -95.3500, 'name': 'Riverside Terrace / Sunnyside N', 'size': 0.030},
    '77022': {'lat': 29.8130, 'lng': -95.3700, 'name': 'Lindale Park / Moody Park', 'size': 0.025},
    '77023': {'lat': 29.7210, 'lng': -95.3200, 'name': 'Second Ward / Eastwood', 'size': 0.028},
    '77024': {'lat': 29.7740, 'lng': -95.4880, 'name': 'Memorial / Piney Point', 'size': 0.040},
    '77025': {'lat': 29.6930, 'lng': -95.4220, 'name': 'Braeswood / Meyerland N', 'size': 0.025},
    '77026': {'lat': 29.7820, 'lng': -95.3290, 'name': 'Fifth Ward / Lyons Ave', 'size': 0.025},
    '77027': {'lat': 29.7410, 'lng': -95.4330, 'name': 'Galleria / River Oaks S', 'size': 0.018},
    '77028': {'lat': 29.8080, 'lng': -95.2980, 'name': 'Settegast / Pleasantville', 'size': 0.028},
    '77029': {'lat': 29.7600, 'lng': -95.2600, 'name': 'Channelview / Cloverleaf W', 'size': 0.035},
    '77030': {'lat': 29.7060, 'lng': -95.3970, 'name': 'Texas Medical Center', 'size': 0.022},
    '77031': {'lat': 29.6720, 'lng': -95.5170, 'name': 'Alief East / Sharpstown S', 'size': 0.030},
    '77033': {'lat': 29.6700, 'lng': -95.3300, 'name': 'South Acres / Crestmont', 'size': 0.030},
    '77034': {'lat': 29.6310, 'lng': -95.2250, 'name': 'Ellington / South Belt W', 'size': 0.035},
    '77035': {'lat': 29.6700, 'lng': -95.4670, 'name': 'Meyerland / Willowbend', 'size': 0.028},
    '77036': {'lat': 29.6950, 'lng': -95.5260, 'name': 'Sharpstown / Chinatown', 'size': 0.030},
    '77037': {'lat': 29.8710, 'lng': -95.3780, 'name': 'Acres Homes N', 'size': 0.030},
    '77038': {'lat': 29.9050, 'lng': -95.4070, 'name': 'Greenspoint W', 'size': 0.035},
    '77039': {'lat': 29.9120, 'lng': -95.3400, 'name': 'Aldine / Eastex', 'size': 0.035},
    '77040': {'lat': 29.8480, 'lng': -95.5200, 'name': 'Northwest Crossing', 'size': 0.035},
    '77041': {'lat': 29.8570, 'lng': -95.5650, 'name': 'Jersey Village S', 'size': 0.035},
    '77042': {'lat': 29.7270, 'lng': -95.5540, 'name': 'Westchase / Briar Forest S', 'size': 0.030},
    '77043': {'lat': 29.7790, 'lng': -95.5380, 'name': 'Spring Branch N', 'size': 0.030},
    '77044': {'lat': 29.8530, 'lng': -95.1900, 'name': 'Atascocita / Generation Park', 'size': 0.045},
    '77045': {'lat': 29.6470, 'lng': -95.4170, 'name': 'South Main / Hiram Clarke', 'size': 0.032},
    '77046': {'lat': 29.7380, 'lng': -95.4180, 'name': 'Upper Kirby / Greenway', 'size': 0.015},
    '77047': {'lat': 29.6200, 'lng': -95.3750, 'name': 'Sunnyside / Reed Rd', 'size': 0.035},
    '77048': {'lat': 29.6050, 'lng': -95.3200, 'name': 'Hobby Area / South Houston W', 'size': 0.035},
    '77049': {'lat': 29.8010, 'lng': -95.1600, 'name': 'Sheldon / Channelview E', 'size': 0.045},
    '77050': {'lat': 29.8800, 'lng': -95.2850, 'name': 'IAH South / Aldine E', 'size': 0.035},
    '77051': {'lat': 29.6580, 'lng': -95.3700, 'name': 'Sunnyside / South Park', 'size': 0.028},
    '77053': {'lat': 29.5950, 'lng': -95.4900, 'name': 'Fort Bend / Missouri City N', 'size': 0.040},
    '77054': {'lat': 29.6920, 'lng': -95.3980, 'name': 'South Main / Astrodome', 'size': 0.020},
    '77055': {'lat': 29.7900, 'lng': -95.4720, 'name': 'Spring Branch S', 'size': 0.028},
    '77056': {'lat': 29.7480, 'lng': -95.4650, 'name': 'Tanglewood / Galleria W', 'size': 0.020},
    '77057': {'lat': 29.7460, 'lng': -95.4900, 'name': 'Westheimer / Uptown E', 'size': 0.022},
    '77058': {'lat': 29.5650, 'lng': -95.1000, 'name': 'Clear Lake / NASA', 'size': 0.035},
    '77059': {'lat': 29.5870, 'lng': -95.1200, 'name': 'Clear Lake S / Bay Area', 'size': 0.035},
    '77060': {'lat': 29.8930, 'lng': -95.3750, 'name': 'Greenspoint', 'size': 0.030},
    '77061': {'lat': 29.6650, 'lng': -95.2880, 'name': 'Gulfgate S / Telephone Rd', 'size': 0.025},
    '77062': {'lat': 29.5700, 'lng': -95.1350, 'name': 'Clear Lake N / El Lago', 'size': 0.030},
    '77063': {'lat': 29.7270, 'lng': -95.5040, 'name': 'Sharpstown N / Tanglewilde', 'size': 0.025},
    '77064': {'lat': 29.8990, 'lng': -95.5350, 'name': 'Willowbrook S', 'size': 0.035},
    '77065': {'lat': 29.9200, 'lng': -95.5700, 'name': 'Cypress Creek S', 'size': 0.035},
    '77066': {'lat': 29.9200, 'lng': -95.4750, 'name': 'Champions W', 'size': 0.032},
    '77067': {'lat': 29.9080, 'lng': -95.4350, 'name': 'FM 1960 / Champions S', 'size': 0.030},
    '77068': {'lat': 29.9350, 'lng': -95.4670, 'name': 'Champions Forest', 'size': 0.030},
    '77069': {'lat': 29.9500, 'lng': -95.4800, 'name': 'Champions N / Louetta', 'size': 0.030},
    '77070': {'lat': 29.9400, 'lng': -95.5300, 'name': 'Willowbrook / Lakewood Forest', 'size': 0.035},
    '77071': {'lat': 29.6650, 'lng': -95.4890, 'name': 'Westwood / Fondren SW', 'size': 0.028},
    '77072': {'lat': 29.6890, 'lng': -95.5550, 'name': 'Alief / Bissonnet W', 'size': 0.030},
    '77073': {'lat': 29.9400, 'lng': -95.3600, 'name': 'IAH / North Houston', 'size': 0.035},
    '77074': {'lat': 29.6930, 'lng': -95.4880, 'name': 'Gulfton / Bellaire SW', 'size': 0.025},
    '77075': {'lat': 29.6440, 'lng': -95.2520, 'name': 'Sagemont / Beverly Hills', 'size': 0.030},
    '77076': {'lat': 29.8380, 'lng': -95.3550, 'name': 'Acres Homes E / Bordersville', 'size': 0.028},
    '77077': {'lat': 29.7450, 'lng': -95.5800, 'name': 'Energy Corridor / Memorial W', 'size': 0.035},
    '77078': {'lat': 29.8250, 'lng': -95.2450, 'name': 'Cloverleaf / Jacinto City N', 'size': 0.035},
    '77079': {'lat': 29.7650, 'lng': -95.5700, 'name': 'Memorial / Bunker Hill', 'size': 0.030},
    '77080': {'lat': 29.8100, 'lng': -95.5000, 'name': 'Spring Branch', 'size': 0.028},
    '77081': {'lat': 29.7120, 'lng': -95.4850, 'name': 'Bellaire / Maplewood S', 'size': 0.020},
    '77082': {'lat': 29.7230, 'lng': -95.5850, 'name': 'Westchase S / Mission Bend N', 'size': 0.035},
    '77083': {'lat': 29.6900, 'lng': -95.6200, 'name': 'Mission Bend / Alief W', 'size': 0.038},
    '77084': {'lat': 29.8100, 'lng': -95.6400, 'name': 'Addicks / Bear Creek', 'size': 0.045},
    '77085': {'lat': 29.6300, 'lng': -95.4400, 'name': 'Fondren / South Post Oak', 'size': 0.030},
    '77086': {'lat': 29.8800, 'lng': -95.4450, 'name': 'North Houston / Veterans Memorial', 'size': 0.030},
    '77087': {'lat': 29.6850, 'lng': -95.3130, 'name': 'OST / South Union / Pecan Park', 'size': 0.028},
    '77088': {'lat': 29.8520, 'lng': -95.3950, 'name': 'Acres Homes / Inwood', 'size': 0.030},
    '77089': {'lat': 29.5900, 'lng': -95.2250, 'name': 'South Belt / Ellington S', 'size': 0.035},
    '77090': {'lat': 29.9350, 'lng': -95.4150, 'name': 'FM 1960 E / North Champions', 'size': 0.030},
    '77091': {'lat': 29.8350, 'lng': -95.4200, 'name': 'Acres Homes W / Candlelight', 'size': 0.025},
    '77092': {'lat': 29.8200, 'lng': -95.4650, 'name': 'Garden Oaks W / Mangum', 'size': 0.025},
    '77093': {'lat': 29.8550, 'lng': -95.3200, 'name': 'Aldine S / Homestead', 'size': 0.035},
    '77094': {'lat': 29.7700, 'lng': -95.6500, 'name': 'Cinco Ranch / Katy E', 'size': 0.040},
    '77095': {'lat': 29.8800, 'lng': -95.6200, 'name': 'Copperfield / Bear Creek N', 'size': 0.040},
    '77096': {'lat': 29.6720, 'lng': -95.4650, 'name': 'Fondren / Braeburn Glen', 'size': 0.025},
    '77098': {'lat': 29.7350, 'lng': -95.4110, 'name': 'Upper Kirby / Montrose S', 'size': 0.018},
    '77099': {'lat': 29.6680, 'lng': -95.5400, 'name': 'Westwood / Alief S', 'size': 0.030},
}


def generate_hex_polygon(lat, lng, size):
    """Generate a hexagonal polygon approximation for a zip code area."""
    coords = []
    for i in range(6):
        angle = math.pi / 3 * i + math.pi / 6  # start rotated 30 degrees
        dx = size * math.cos(angle) * 1.2  # wider for longitude
        dy = size * math.sin(angle)
        coords.append([round(lng + dx, 6), round(lat + dy, 6)])
    coords.append(coords[0])  # close the polygon
    return [coords]


def load_indicators():
    """Load computed indicators keyed by zip."""
    path = os.path.join(DATA_DIR, 'indicators_by_zip.csv')
    rows = read_csv(path)
    data = {}
    for r in rows:
        z = r.get('zip', '').strip()
        if z:
            data[z] = {k: safe_float(v) for k, v in r.items() if k != 'zip'}
    return data


def load_census():
    """Load census data keyed by zip."""
    path = os.path.join(DATA_DIR, 'census_acs_zip.csv')
    rows = read_csv(path)
    data = {}
    for r in rows:
        z = r.get('zip', '').strip()
        if z:
            data[z] = {k: safe_float(v) for k, v in r.items() if k not in ('zip', 'name')}
    return data


def read_csv(path):
    """Read CSV into list of dicts."""
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def safe_float(val, default=None):
    if val is None or val == '' or val == 'None':
        return default
    try:
        v = float(val)
        return v if not math.isnan(v) else default
    except (ValueError, TypeError):
        return default


def build_geojson():
    """Build the complete GeoJSON FeatureCollection."""
    indicators = load_indicators()
    census = load_census()

    if not indicators:
        print("  ERROR: No indicator data found. Run compute_indicators.py first.")
        return None

    features = []

    for zip_code, info in sorted(ZIP_INFO.items()):
        ind = indicators.get(zip_code, {})
        cen = census.get(zip_code, {})

        if not ind:
            continue  # skip zips with no indicator data

        # Build polygon
        polygon = generate_hex_polygon(info['lat'], info['lng'], info['size'])

        # Merge all properties
        properties = {
            'zip': zip_code,
            'name': info['name'],
            # Census fields
            'median_household_income': cen.get('median_household_income'),
            'median_gross_rent': cen.get('median_gross_rent'),
            'median_home_value': cen.get('median_home_value'),
            'total_population': cen.get('total_population'),
            'renter_pct': None,
            'rent_burden_pct': cen.get('median_rent_burden_pct'),
            # Indicator fields
            'listing_velocity': ind.get('listing_velocity'),
            'price_trajectory': ind.get('price_trajectory'),
            'rental_yield': ind.get('rental_yield'),
            'investor_activity': ind.get('investor_activity'),
            'dom_shift': ind.get('dom_shift'),
            'displacement_risk': ind.get('displacement_risk'),
            'flip_rate': ind.get('flip_rate'),
            'affordability_cliff': ind.get('affordability_cliff'),
            # Metadata
            'is_sample_data': True,
        }

        # Compute renter percentage
        renter = cen.get('renter_occupied')
        owner = cen.get('owner_occupied')
        if renter is not None and owner is not None and (renter + owner) > 0:
            properties['renter_pct'] = round(renter / (renter + owner) * 100, 1)

        # Clean None values to null-safe format
        for k, v in properties.items():
            if isinstance(v, float) and math.isnan(v):
                properties[k] = None

        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Polygon',
                'coordinates': polygon,
            },
            'properties': properties,
        }
        features.append(feature)

    geojson = {
        'type': 'FeatureCollection',
        'metadata': {
            'title': 'Houston Capital Flow Indicators by Zip Code',
            'description': 'Capital flow and displacement risk indicators for Houston zip codes',
            'generated': '2026-02',
            'indicators': [
                {'id': 'listing_velocity', 'label': 'Listing Velocity', 'unit': 'ratio', 'description': 'New listings / inventory ratio (higher = hotter market)'},
                {'id': 'price_trajectory', 'label': 'Price Trajectory', 'unit': '%', 'description': '3-year median price growth rate'},
                {'id': 'rental_yield', 'label': 'Rental Yield', 'unit': '%', 'description': 'Gross rental yield (annual rent / home value)'},
                {'id': 'investor_activity', 'label': 'Investor Activity', 'unit': '0-100', 'description': 'Composite investor activity index'},
                {'id': 'dom_shift', 'label': 'DOM Shift', 'unit': 'days', 'description': 'Days-on-market change (negative = faster sales)'},
                {'id': 'displacement_risk', 'label': 'Displacement Risk', 'unit': '0-100', 'description': 'Weighted displacement risk score'},
                {'id': 'flip_rate', 'label': 'Flip Rate', 'unit': '%', 'description': 'Estimated short-hold resale percentage'},
                {'id': 'affordability_cliff', 'label': 'Affordability Cliff', 'unit': 'ratio', 'description': 'Home price / (4x median income) — above 1.0 = unaffordable'},
            ],
        },
        'features': features,
    }

    return geojson


def main():
    print("=" * 60)
    print("Capital Flow GeoJSON Generator — Houston Zip Codes")
    print("=" * 60)
    print()

    geojson = build_geojson()
    if not geojson:
        return

    output_path = os.path.join(DATA_DIR, 'houston_capital.geojson')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=None, separators=(',', ':'))

    feature_count = len(geojson['features'])
    file_size = os.path.getsize(output_path)

    print(f"  Generated {feature_count} zip code features")
    print(f"  File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    print(f"  Saved to: {output_path}")
    print()
    print("Properties per feature:")
    if geojson['features']:
        for k in sorted(geojson['features'][0]['properties'].keys()):
            print(f"  - {k}")


if __name__ == '__main__':
    main()
