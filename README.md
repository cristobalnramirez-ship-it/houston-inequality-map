# Houston Inequality Map + Capital Flow Tracker

An interactive, animated map of Houston showing layered spatial history of inequality — redlining, highways, floods, pollution, demographics, and income — across decades from the 1940s to today. Now with a **Capital Flow Tracker** showing real-time housing market dynamics and displacement risk by zip code.

## Live Demo

Open `index.html` in any modern browser. No build step or server required.

For local development with proper CORS for data files, use any static server:

```bash
# Python
python -m http.server 8000

# Node
npx serve .

# Then open http://localhost:8000
```

## Features

- **HOLC Redlining (1940)** — Original A/B/C/D grades showing how federal policy marked Black and Hispanic neighborhoods as "hazardous"
- **Highways & Displacement** — Interstate construction routes with historical context on communities destroyed
- **Median Household Income** — Choropleth by census tract, viewable across decades (1970s–2020s)
- **Race & Ethnicity** — Dominant group choropleth showing demographic shifts over time
- **Flood Zones** — FEMA flood hazard areas and Hurricane Harvey (2017) extent
- **Toxic Release Sites** — EPA TRI facilities showing industrial pollution near residential areas
- **Timeline Slider** — Scrub from 1940s to 2020s; data-driven layers update per decade
- **Narrative Cards** — Historical context appears at key moments in the timeline
- **Click-to-Inspect** — Click any feature for detailed data in the info panel
- **Capital Flow Tracker** — 8 indicators of housing market dynamics by zip code:
  - **Displacement Risk Score** — Weighted composite of price growth, investor activity, and rent burden
  - **Price Trajectory** — 3-year median home price growth rate
  - **Listing Velocity** — New listings / inventory ratio (market heat)
  - **Rental Yield** — Gross rental yield (annual rent / home value)
  - **Investor Activity** — Composite investor activity index
  - **DOM Shift** — Days-on-market change (negative = selling faster)
  - **Flip Rate** — Estimated short-hold resale percentage
  - **Affordability Cliff** — Home price / (4x median income)
- **The Jarring View** — Toggle 1940 HOLC Redlining + 2026 Displacement Risk and watch them overlap

## Data

The project ships with **sample data** for demonstration. To replace with real data from official sources, see `scripts/README.md`.

| Layer | Sample Data | Real Source |
|-------|-------------|------------|
| Redlining | 26 HOLC zones | [Mapping Inequality](https://dsl.richmond.edu/panorama/redlining/) |
| Highways | 8 routes | TxDOT / manually curated |
| Income | 35 tracts | [Census ACS](https://data.census.gov/) |
| Demographics | 35 tracts | [Census ACS](https://data.census.gov/) |
| Flood Zones | 15 zones | [FEMA NFHL](https://www.fema.gov/flood-maps/national-flood-hazard-layer) |
| TRI Sites | 25 facilities | [EPA TRI](https://www.epa.gov/toxics-release-inventory-tri-program) |
| Capital Flow | 92 zip codes, 8 indicators | [Zillow](https://www.zillow.com/research/data/) + [Redfin](https://www.redfin.com/news/data-center/) + [Census ACS](https://data.census.gov/) |

## Tech Stack

- **[Leaflet.js](https://leafletjs.com/)** — Map rendering (via CDN)
- **[CartoDB Dark Matter](https://carto.com/basemaps/)** — Dark basemap tiles
- **[chroma.js](https://gka.github.io/chroma.js/)** — Color scales (via CDN)
- **[noUiSlider](https://refreshless.com/nouislider/)** — Timeline slider (via CDN)
- **Vanilla HTML/CSS/JS** — No framework, no build step
- **Inter** — UI font via Google Fonts

## Project Structure

```
houston-inequality-map/
  index.html              — Main page
  style.css               — Dark theme styles
  app.js                  — Map logic, layers, timeline, interactions
  data/
    redlining/            — HOLC redlining polygons
    census/               — Income and race/ethnicity by tract
    infrastructure/       — Highway routes
    environment/          — Flood zones, TRI toxic sites
    annotations/          — Timeline narrative events
  data/capital/               — Capital flow indicator data
    houston_capital.geojson   — Zip code polygons + all 8 indicators
    census_acs_zip.csv        — Census ACS by zip
    indicators_by_zip.csv     — Computed indicators
  scripts/
    fetch_redlining.py    — Download HOLC data
    fetch_tri.py          — Download EPA TRI data
    fetch_census.py       — Download Census ACS data
    fetch_flood_zones.py  — Download FEMA flood zones
    process_highways.py   — Generate highway GeoJSON
    fetch_zillow.py       — Download Zillow ZHVI/ZORI
    fetch_redfin.py       — Download Redfin market data
    fetch_census_acs.py   — Download Census ACS by zip code
    compute_indicators.py — Calculate all 8 capital indicators
    generate_capital_geojson.py — Build houston_capital.geojson
    METHODOLOGY.md        — Indicator methodology documentation
    README.md             — Script documentation
```

## Fetching Real Data

```bash
cd scripts

# These work without API keys
python fetch_redlining.py
python fetch_tri.py
python process_highways.py
python fetch_flood_zones.py    # Slow — FEMA API is paginated

# Census data needs a free API key
# Get one at: https://api.census.gov/data/key_signup.html
export CENSUS_API_KEY=your_key
python fetch_census.py
```

### Capital Flow Data Pipeline

```bash
cd scripts

# 1. Fetch data (Zillow + Redfin work without API keys)
python fetch_zillow.py                    # ~10MB download
python fetch_redfin.py                    # ~200MB download (large!)
python fetch_census_acs.py YOUR_API_KEY   # Or omit key for sample data

# 2. Compute indicators
python compute_indicators.py

# 3. Generate GeoJSON
python generate_capital_geojson.py
```

See `scripts/METHODOLOGY.md` for full details on how each indicator is calculated.

### Monthly Update Process

To refresh capital flow data with latest market conditions:
1. Re-run `fetch_zillow.py` and `fetch_redfin.py` (new data released monthly)
2. Re-run `compute_indicators.py` then `generate_capital_geojson.py`
3. The map will automatically pick up the new `houston_capital.geojson`

## Deploy

This is a static site. Deploy to any static host:

- **GitHub Pages** — Push to repo, enable Pages in settings
- **Netlify** — Drag and drop the folder, or connect to Git
- **Vercel** — `npx vercel` from the project root
- **Any web server** — Copy all files to your document root

## License

Data sources are public domain (US government) or openly licensed. See individual source links above for terms.
