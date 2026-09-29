#!/usr/bin/env bash
# Download the raw inputs for the lending and ownership layers into data/raw/.
# Run from the repo root on a machine with normal internet access.
# Sizes are approximate.
set -euo pipefail
mkdir -p data/raw

HMDA="https://ffiec.cfpb.gov/v2/data-browser-api/view/csv"
YEARS="2023,2024,2025"

# HMDA home-purchase applications (originated, approved-not-accepted, denied), 2023-2025
curl -L --fail -o data/raw/hmda_48201.csv "$HMDA?years=$YEARS&counties=48201&loan_purposes=1&actions_taken=1,2,3"   # Harris
curl -L --fail -o data/raw/hmda_48061.csv "$HMDA?years=$YEARS&counties=48061&loan_purposes=1&actions_taken=1,2,3"   # Cameron

# Cameron Appraisal District parcels with owner data (~63 MB zipped)
curl -L --fail -o data/raw/cameron_parcels_public.zip "https://www.cameroncad.org/cad/exports/GIS/parcels_public.zip"

# HCAD Real_acct_owner.zip: download manually from https://hcad.org/hcad-online-services/pdata/
# (Real Property -> Real_acct_owner.zip for the current year) and save as data/raw/Real_acct_owner.zip
echo "Done. Next:"
echo "  python scripts/capital/build_hmda_tracts.py --csv data/raw/hmda_48201.csv --tracts data/census/income_2020.geojson --out data/capital/hmda_tracts.geojson"
echo "  python scripts/capital/build_ownership.py --source hcad --input data/raw/Real_acct_owner.zip --out data/capital/ownership_zip.json"
echo "  python scripts/build_capital_flow.py"
echo "  then set LOAD_LENDING = true in app.js"
