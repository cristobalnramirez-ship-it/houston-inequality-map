# Data Pipeline Scripts

Python scripts that fetch the map's data from public sources. None of them generate sample or placeholder values: if a source can't be reached, they stop with an error.

## Scripts

| Script | Source | API Key? | Notes |
|--------|--------|----------|-------|
| `fetch_redlining.py` | Mapping Inequality census crosswalk | No | Downloads HOLC areas and dissolves tract-split pieces (needs `shapely`) |
| `fetch_tri.py` | EPA Envirofacts REST API | No | TRI toxic release facilities in Harris County |
| `fetch_census.py` | TIGERweb + Census ACS API | **Yes** (free) | Tract geometry + income/demographics |
| `fetch_flood_zones.py` | FEMA NFHL ArcGIS REST | No | Flood hazard areas (paginated, may be slow) |

## Quick Start

```bash
# No API key needed
python fetch_redlining.py
python fetch_tri.py

# Slow — FEMA API can take several minutes
python fetch_flood_zones.py

# Needs free Census API key
# Get one at: https://api.census.gov/data/key_signup.html
export CENSUS_API_KEY=your_key_here
python fetch_census.py
# Or pass as argument:
python fetch_census.py your_key_here
```

## Requirements

- Python 3.7+
- No external packages required (uses only `urllib`, `json`, `os`)

## Historical Data (Not Automated)

For historical census decades (1970-2000), data must be manually obtained from:

- **NHGIS** (National Historical GIS): https://www.nhgis.org/
  - Free account required
  - Download tract-level data for Harris County by decade
  - Variables: median income, race/ethnicity counts, population

- **Social Explorer**: https://www.socialexplorer.com/
  - University access often available
  - Good for historical tract boundaries that changed over time

## Output

All scripts write to the `../data/` directory. Freeway attributes (dates, neighborhoods, sources) are curated directly in `data/infrastructure/highways.geojson`.
