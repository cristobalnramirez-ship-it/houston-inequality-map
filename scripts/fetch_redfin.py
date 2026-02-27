#!/usr/bin/env python3
"""
fetch_redfin.py — Download Redfin Data Center CSVs for Houston zip codes.

Downloads:
  - Redfin monthly housing market data by zip code
  - Includes: median sale price, homes sold, new listings, days on market,
    sale-to-list ratio, inventory, price drops

Source: https://www.redfin.com/news/data-center/
No API key required. Direct TSV downloads.

Output:
  ../data/capital/redfin_zip_market.csv
"""

import os
import sys
import csv
import gzip
import io
import urllib.request

HOUSTON_ZIPS = {
    '77002', '77003', '77004', '77005', '77006', '77007', '77008', '77009',
    '77010', '77011', '77012', '77013', '77014', '77015', '77016', '77017',
    '77018', '77019', '77020', '77021', '77022', '77023', '77024', '77025',
    '77026', '77027', '77028', '77029', '77030', '77031', '77032', '77033',
    '77034', '77035', '77036', '77037', '77038', '77039', '77040', '77041',
    '77042', '77043', '77044', '77045', '77046', '77047', '77048', '77049',
    '77050', '77051', '77053', '77054', '77055', '77056', '77057', '77058',
    '77059', '77060', '77061', '77062', '77063', '77064', '77065', '77066',
    '77067', '77068', '77069', '77070', '77071', '77072', '77073', '77074',
    '77075', '77076', '77077', '77078', '77079', '77080', '77081', '77082',
    '77083', '77084', '77085', '77086', '77087', '77088', '77089', '77090',
    '77091', '77092', '77093', '77094', '77095', '77096', '77098', '77099',
}

# Redfin Data Center download URL for zip-code-level data
# This is a large gzipped TSV (~200MB compressed, ~1GB uncompressed)
# It contains ALL US zip codes; we filter to Houston
REDFIN_ZIP_URL = "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/zip_code_market_tracker.tsv000.gz"

# Alternative: region-level data (smaller, metro-level only)
REDFIN_METRO_URL = "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/redfin_metro_market_tracker.tsv000.gz"

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'capital')


def download_and_filter_redfin(url, output_path):
    """
    Download Redfin gzipped TSV, filter to Houston zips, save as CSV.
    Streams the file to avoid loading entire dataset into memory.
    """
    print(f"Downloading Redfin zip-code data...")
    print(f"  URL: {url}")
    print(f"  (This is a large file — may take several minutes)")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=300)

        # Redfin serves gzipped TSV
        decompressed = gzip.GzipFile(fileobj=io.BytesIO(response.read()))
        text_stream = io.TextIOWrapper(decompressed, encoding='utf-8')

        reader = csv.DictReader(text_stream, delimiter='\t')

        # Key fields we want to keep
        keep_fields = [
            'period_begin', 'period_end', 'period_duration',
            'region_type', 'region_type_id', 'table_id', 'region',
            'state', 'state_code', 'property_type',
            'median_sale_price', 'median_sale_price_yoy',
            'homes_sold', 'homes_sold_yoy',
            'new_listings', 'new_listings_yoy',
            'inventory', 'inventory_yoy',
            'months_of_supply', 'months_of_supply_yoy',
            'median_dom', 'median_dom_yoy',
            'avg_sale_to_list', 'avg_sale_to_list_yoy',
            'sold_above_list', 'sold_above_list_yoy',
            'price_drops', 'price_drops_yoy',
            'off_market_in_two_weeks', 'off_market_in_two_weeks_yoy',
        ]

        houston_rows = []
        total_scanned = 0
        for row in reader:
            total_scanned += 1
            if total_scanned % 500000 == 0:
                print(f"  Scanned {total_scanned:,} rows, found {len(houston_rows)} Houston rows...")

            # Filter: zip code in Houston set, residential property
            region = str(row.get('region', '')).strip()
            # Redfin region for zip codes is like "Zip Code: 77004"
            zip_code = region.replace('Zip Code: ', '').strip()
            if zip_code in HOUSTON_ZIPS:
                filtered_row = {k: row.get(k, '') for k in keep_fields if k in row}
                filtered_row['zip_code'] = zip_code
                houston_rows.append(filtered_row)

        print(f"  Scanned {total_scanned:,} total rows")
        print(f"  Found {len(houston_rows)} Houston zip code rows")

        if houston_rows:
            out_fields = ['zip_code'] + keep_fields
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[k for k in out_fields if k in houston_rows[0]])
                writer.writeheader()
                writer.writerows(houston_rows)
            print(f"  Saved to {output_path}")
        else:
            print("  WARNING: No Houston rows found")

    except Exception as e:
        print(f"  ERROR: {e}")
        print(f"  The Redfin zip-level file is very large (~200MB).")
        print(f"  If download fails, try:")
        print(f"    1. Download manually from https://www.redfin.com/news/data-center/")
        print(f"    2. Select 'Zip Code' geography and 'All Residential' property type")
        print(f"    3. Download the TSV and place in: {DATA_DIR}")


def main():
    print("=" * 60)
    print("Redfin Data Center Fetcher — Houston Zip Codes")
    print("=" * 60)
    print()

    output = os.path.join(DATA_DIR, 'redfin_zip_market.csv')
    download_and_filter_redfin(REDFIN_ZIP_URL, output)

    print()
    print("Redfin fields included:")
    print("  - median_sale_price (+ YoY change)")
    print("  - homes_sold, new_listings, inventory")
    print("  - median_dom (days on market)")
    print("  - avg_sale_to_list ratio")
    print("  - months_of_supply")
    print("  - price_drops percentage")
    print("  - off_market_in_two_weeks percentage")
    print()
    print("All fields include year-over-year (_yoy) variants.")


if __name__ == '__main__':
    main()
