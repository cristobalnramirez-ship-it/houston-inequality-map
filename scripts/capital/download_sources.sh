#!/usr/bin/env bash
# Download the raw inputs for the lending and ownership layers into data/raw/.
# Run from the repo root on a machine with normal internet access.
# Sizes are approximate.
set -euo pipefail
mkdir -p data/raw

HMDA="https://ffiec.cfpb.gov/v2/data-browser-api/view/csv"
YEARS="2023,2024,2025"

# HMDA home-purchase applications (originated, approved-not-accepted, denied), 2023-2025.
# The API returns only the first year when several are requested, so fetch one year at a time.
for county in 48201 48061; do   # Harris, Cameron
  rm -f data/raw/hmda_$county.csv
  for y in ${YEARS//,/ }; do
    curl -L --fail -o data/raw/hmda_${county}_$y.csv "$HMDA?years=$y&counties=$county&loan_purposes=1&actions_taken=1,2,3"
    if [ -f data/raw/hmda_$county.csv ]; then tail -n +2 data/raw/hmda_${county}_$y.csv >> data/raw/hmda_$county.csv
    else cp data/raw/hmda_${county}_$y.csv data/raw/hmda_$county.csv; fi
  done
done

# Cameron Appraisal District parcels with owner data (~63 MB zipped)
curl -L --fail -o data/raw/cameron_parcels_public.zip "https://www.cameroncad.org/cad/exports/GIS/parcels_public.zip"

# HCAD Real_acct_owner.zip (~210 MB; listed at https://hcad.org/pdata/pdata-property-downloads.html)
curl -L --fail -o data/raw/Real_acct_owner.zip "https://download.hcad.org/data/CAMA/2026/Real_acct_owner.zip"
echo "Done. Next:"
echo "  python scripts/capital/build_hmda_tracts.py --csv data/raw/hmda_48201.csv --tracts data/census/income_2020.geojson --out data/capital/hmda_tracts.geojson"
echo "  python scripts/capital/build_ownership.py --source hcad --input data/raw/Real_acct_owner.zip --out data/capital/ownership_zip.json --label \"HCAD 2026 certified roll\""
echo "  python scripts/build_capital_flow.py"
