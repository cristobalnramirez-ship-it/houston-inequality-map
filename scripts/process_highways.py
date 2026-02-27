"""
Generate highway GeoJSON for Houston's major freeways.

This script creates a curated GeoJSON of Houston's major highways with
historical context about construction dates and neighborhood displacement.

Unlike other fetch scripts, this uses manually curated data since highway
centerlines need historical context not available from standard GIS sources.
The coordinates are simplified representations — for precise centerlines,
use TxDOT's Roadway Inventory or OpenStreetMap extracts.
"""

import json
import os
import math

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'infrastructure')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'highways.geojson')

# Houston highway data with historical context
HIGHWAYS = [
    {
        "name": "I-45 (Gulf Freeway)",
        "designation": "I-45 South",
        "construction_year": 1948,
        "completion_year": 1952,
        "decade": "1950s",
        "neighborhoods_displaced": ["South Houston", "South Park", "Gulfgate"],
        "description": "First freeway in Texas. Connected downtown Houston to Galveston, establishing the auto-centric development pattern that would define the city.",
        "path": [
            [-95.370, 29.760], [-95.365, 29.745], [-95.358, 29.730],
            [-95.350, 29.710], [-95.340, 29.690], [-95.330, 29.670],
            [-95.315, 29.650], [-95.300, 29.635], [-95.285, 29.620],
        ]
    },
    {
        "name": "I-45 (North Freeway)",
        "designation": "I-45 North",
        "construction_year": 1957,
        "completion_year": 1963,
        "decade": "1960s",
        "neighborhoods_displaced": ["Fifth Ward", "Kashmere Gardens", "Near Northside"],
        "description": "Cut through the heart of Fifth Ward and Near Northside, displacing thousands of Black and Hispanic residents. The freeway created a physical barrier isolating these communities.",
        "path": [
            [-95.370, 29.760], [-95.375, 29.775], [-95.378, 29.790],
            [-95.382, 29.805], [-95.385, 29.820], [-95.388, 29.835],
            [-95.390, 29.850], [-95.393, 29.865], [-95.395, 29.880],
        ]
    },
    {
        "name": "I-10 (Katy Freeway)",
        "designation": "I-10 West",
        "construction_year": 1960,
        "completion_year": 1968,
        "decade": "1960s",
        "neighborhoods_displaced": ["Fourth Ward"],
        "description": "Western segment demolished parts of Fourth Ward/Freedmen's Town, one of Houston's oldest Black communities. Later widened to 26 lanes, the widest freeway in the world.",
        "path": [
            [-95.370, 29.760], [-95.395, 29.765], [-95.420, 29.768],
            [-95.445, 29.770], [-95.470, 29.772], [-95.500, 29.774],
            [-95.530, 29.776], [-95.560, 29.778], [-95.590, 29.780],
        ]
    },
    {
        "name": "I-10 (East Freeway)",
        "designation": "I-10 East",
        "construction_year": 1953,
        "completion_year": 1958,
        "decade": "1950s",
        "neighborhoods_displaced": ["Second Ward", "Magnolia Park"],
        "description": "Routed through Second Ward's Mexican-American community, severing the neighborhood from the Ship Channel industrial jobs that sustained it.",
        "path": [
            [-95.370, 29.760], [-95.340, 29.762], [-95.310, 29.763],
            [-95.280, 29.762], [-95.250, 29.760], [-95.220, 29.758],
            [-95.200, 29.760],
        ]
    },
    {
        "name": "I-69/US-59 (Southwest Freeway)",
        "designation": "I-69/US-59 South",
        "construction_year": 1959,
        "completion_year": 1962,
        "decade": "1960s",
        "neighborhoods_displaced": ["Third Ward", "Midtown"],
        "description": "Tore through Third Ward, Houston's cultural center for Black life. Destroyed hundreds of homes and businesses, creating a barrier that accelerated the neighborhood's decline.",
        "path": [
            [-95.370, 29.760], [-95.380, 29.748], [-95.395, 29.735],
            [-95.410, 29.722], [-95.425, 29.708], [-95.445, 29.695],
            [-95.465, 29.680], [-95.490, 29.665], [-95.515, 29.650],
        ]
    },
    {
        "name": "I-69/US-59 (Eastex Freeway)",
        "designation": "I-69/US-59 North",
        "construction_year": 1955,
        "completion_year": 1960,
        "decade": "1960s",
        "neighborhoods_displaced": ["Fifth Ward", "Denver Harbor"],
        "description": "Northeast corridor that further isolated Fifth Ward, already bisected by I-45 North and rail lines. Combined with I-45, created a walled-off zone of disinvestment.",
        "path": [
            [-95.370, 29.760], [-95.355, 29.775], [-95.340, 29.790],
            [-95.325, 29.805], [-95.310, 29.820], [-95.295, 29.835],
            [-95.280, 29.850], [-95.265, 29.860],
        ]
    },
]


def make_loop(center_lon, center_lat, radius_lon, radius_lat, num_points=24):
    """Generate coordinates for a highway loop (I-610, Beltway 8)."""
    coords = []
    for i in range(num_points + 1):
        angle = 2 * math.pi * i / num_points
        lon = center_lon + radius_lon * math.cos(angle)
        lat = center_lat + radius_lat * math.sin(angle)
        coords.append([round(lon, 4), round(lat, 4)])
    return coords


def build_geojson():
    features = []

    # Linear highways
    for hw in HIGHWAYS:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": hw["path"]
            },
            "properties": {
                "name": hw["name"],
                "designation": hw["designation"],
                "construction_year": hw["construction_year"],
                "completion_year": hw["completion_year"],
                "decade": hw["decade"],
                "neighborhoods_displaced": hw["neighborhoods_displaced"],
                "description": hw["description"],
            }
        }
        features.append(feature)

    # I-610 Inner Loop
    features.append({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": make_loop(-95.370, 29.760, 0.055, 0.045, 24)
        },
        "properties": {
            "name": "I-610 (Inner Loop)",
            "designation": "I-610",
            "construction_year": 1955,
            "completion_year": 1970,
            "decade": "1960s",
            "neighborhoods_displaced": ["Independence Heights", "Eastwood"],
            "description": "38-mile loop that became Houston's defining boundary. Created an inside/outside divide that persists in property values, services, and identity.",
        }
    })

    # Beltway 8 / Sam Houston Tollway
    features.append({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": make_loop(-95.370, 29.760, 0.125, 0.105, 32)
        },
        "properties": {
            "name": "Beltway 8 / Sam Houston Tollway",
            "designation": "Beltway 8",
            "construction_year": 1983,
            "completion_year": 1994,
            "decade": "1980s",
            "neighborhoods_displaced": [],
            "description": "Outer beltway built through largely undeveloped land. Spurred massive suburban growth in Katy, Sugar Land, Clear Lake, and Kingwood — predominantly white, middle-class communities.",
        }
    })

    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "Manually curated from TxDOT records and Houston Public Library archives",
            "note": "Simplified centerlines for visualization. See TxDOT Roadway Inventory for precise geometry."
        },
        "features": features
    }


def main():
    geojson = build_geojson()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)

    print(f"Generated {len(geojson['features'])} highway features")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
