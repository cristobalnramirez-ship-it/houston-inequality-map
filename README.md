# Houston Inequality Map

An interactive map of Houston that layers the 1930s federal redlining grades with the freeways built through the city's Black and Mexican-American neighborhoods, FEMA floodplains, current Census income and race data, and today's political districts. A timeline (1930s–2020s) steps through sourced historical events and shows the freeway network as it was built.

## Run it

The map loads its data with `fetch()`, which browsers block for files opened directly from disk, so serve the folder:

```bash
python -m http.server 8000   # or: npx serve .
# then open http://localhost:8000
```

It deploys as-is to any static host (GitHub Pages, Netlify, Vercel).

## Layers and sources

| Layer | What it shows | Source | Vintage |
|---|---|---|---|
| HOLC Redlining | 47 graded areas (A–D) plus ungraded areas | Home Owners' Loan Corporation map of Houston, via [Mapping Inequality](https://dsl.richmond.edu/panorama/redlining/) (Nelson, Winling et al., CC BY-NC-SA 4.0) and its [census-tract crosswalk](https://github.com/americanpanorama/mapping-inequality-census-crosswalk), dissolved back to one polygon per area | Map dated 1937 ([BTAA catalog](https://geo.btaa.org/catalog/0b2e8605-b35c-40f6-afba-26c7b9d0c8e9)) |
| Freeways | Eight freeways, drawn by decade; dates and affected neighborhoods on click | [Baker Institute](https://www.bakerinstitute.org/research/houstons-freeways-who-was-displaced-and-why), Houston Freeways, AARoads, TxDOT history (links on each feature) | 1946–2011 |
| Median household income, poverty | By census tract | U.S. Census Bureau ACS 5-year | 2018–2022 |
| Race and ethnicity | Majority group by tract | U.S. Census Bureau ACS 5-year | 2018–2022 |
| Flood zones | FEMA 1% and 0.2% annual-chance zones | FEMA National Flood Hazard Layer (extract) | Current effective FIRMs |
| Capital Flow | Home-value and rent change, typical values, value-to-income, rent burden, renter share — by ZIP | [Zillow Research](https://www.zillow.com/research/data/) ZHVI and ZORI; Census ACS via [Census Reporter](https://censusreporter.org) | Zillow through Aug 2026; ACS 2020–24 |
| Mortgage lending | Investor share of purchase mortgages, owner-occupant denial rate, Hispanic and Black borrower shares — by census tract | [CFPB HMDA Data Browser](https://ffiec.cfpb.gov/data-browser/) | 2023–2025 |
| Home ownership (in Capital Flow) | Company-owned, large-operator-owned and out-of-state-owned single-family homes; share of recent buyers that are companies — by ZIP | [Harris Central Appraisal District](https://hcad.org/pdata/pdata-property-downloads.html) owner records; method and a check against the Kinder Institute's count in [`scripts/capital/METHOD.md`](scripts/capital/METHOD.md) | 2026 certified roll |
| Political districts | U.S. House, Texas Senate/House, Harris County commissioners, Houston City Council | Census TIGERweb, Harris County, City of Houston; officeholders in `data/political/officeholders.json` | Officeholders as of 2026-09-27 |
| Timeline | 21 sourced events | Source link on each card | 1937–2022 |

Census layers show one recent period and do not change with the timeline. Estimates the Census Bureau suppresses are shown as "No data".

### Not included (and why)

- **Historical census decades (1970–2010).** An earlier version displayed modeled values for these decades. They were removed because they were not real data. To add them, download tract data from [NHGIS](https://www.nhgis.org/), harmonize to 2010 tracts (e.g., with the [LTDB](https://s4.ad.brown.edu/projects/diversity/researcher/bridging.htm)), and inflation-adjust incomes.
- **Toxic release sites.** An earlier version showed sample facilities. The layer is off until real data exists: run `scripts/fetch_tri.py` to write `data/environment/tri_sites.geojson`, then set `LOAD_TRI = true` in `app.js`.
- **A composite "displacement risk" score.** The Capital Flow layer shows descriptive measures only. A risk score should come from a published method (e.g., the Urban Displacement Project typology), not invented weights.
- **SH-288** (which cut through Third Ward) is described in the timeline and freeway notes but not yet drawn.

## Updating data

```bash
cd scripts
pip install shapely
python fetch_redlining.py          # Mapping Inequality → data/redlining/houston_holc.geojson
python fetch_census.py YOUR_KEY    # ACS tract geometry + values (free key: api.census.gov/data/key_signup.html)
python build_floods.py             # FEMA NFHL, paginated
python fetch_tri.py                # EPA TRI facilities (optional layer)
python fetch_political.py          # boundaries; names/parties come from data/political/officeholders.json
python build_capital_flow.py --zhvi Zip_zhvi_....csv --zori Zip_zori_....csv   # after downloading Zillow's ZIP files
cd .. && bash scripts/capital/download_sources.sh   # HMDA + HCAD raw files into data/raw/, then prints the build commands
```

Update `data/political/officeholders.json` whenever a seat changes.

## Credits and license

Redlining polygons: Robert K. Nelson, LaDale Winling, et al., *Mapping Inequality: Redlining in New Deal America*, Digital Scholarship Lab, University of Richmond — CC BY-NC-SA 4.0 (credit shown on the map). Basemap © OpenStreetMap contributors © CARTO. Census, FEMA and EPA data are U.S. government works.

Built with Leaflet, chroma.js and noUiSlider.
