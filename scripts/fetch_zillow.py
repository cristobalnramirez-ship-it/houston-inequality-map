#!/usr/bin/env python3
"""
fetch_zillow.py — Download Zillow Research Data for Houston zip codes.

Downloads:
  - ZHVI (Zillow Home Value Index) by zip code — monthly median home values
  - ZORI (Zillow Observed Rent Index) by zip code — monthly median rents

Source: https://www.zillow.com/research/data/
No API key required. Direct CSV downloads.

Output:
  ../data/capital/zillow_zhvi.csv
  ../data/capital/zillow_zori.csv
"""

import os
import sys
import csv
import urllib.request
import io

# Houston-area zip codes (Harris County + Fort Bend + Montgomery partial)
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

# Zillow data download URLs (these are the current public CSV endpoints)
ZHVI_URL = "https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
ZORI_URL = "https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uc_sfrcondomfr_sm_sa_month.csv"

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'capital')


def download_csv(url, label):
    """Download a CSV from URL and return as string."""
    print(f"Downloading {label}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read().decode('utf-8')
        print(f"  Downloaded {len(data):,} bytes")
        return data
    except Exception as e:
        print(f"  ERROR downloading {label}: {e}")
        print(f"  URL: {url}")
        print(f"  Try downloading manually from https://www.zillow.com/research/data/")
        return None


def filter_houston_rows(csv_text, zip_column='RegionName'):
    """Filter CSV rows to Houston-area zip codes only."""
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames
    rows = []
    for row in reader:
        zip_code = str(row.get(zip_column, '')).strip()
        # Zillow uses 5-digit zips
        if zip_code in HOUSTON_ZIPS:
            rows.append(row)
    return fieldnames, rows


def save_filtered(fieldnames, rows, output_path, label):
    """Save filtered rows to CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved {len(rows)} Houston zip codes to {output_path}")


def main():
    print("=" * 60)
    print("Zillow Research Data Fetcher — Houston Zip Codes")
    print("=" * 60)
    print()

    # ZHVI — Home Values
    zhvi_csv = download_csv(ZHVI_URL, "ZHVI (Home Values)")
    if zhvi_csv:
        fieldnames, rows = filter_houston_rows(zhvi_csv)
        if rows:
            save_filtered(fieldnames, rows, os.path.join(DATA_DIR, 'zillow_zhvi.csv'), "ZHVI")
        else:
            print("  WARNING: No Houston zip codes found in ZHVI data")
    print()

    # ZORI — Rents
    zori_csv = download_csv(ZORI_URL, "ZORI (Rents)")
    if zori_csv:
        fieldnames, rows = filter_houston_rows(zori_csv)
        if rows:
            save_filtered(fieldnames, rows, os.path.join(DATA_DIR, 'zillow_zori.csv'), "ZORI")
        else:
            print("  WARNING: No Houston zip codes found in ZORI data")
    print()

    print("Done. Output files in:", DATA_DIR)
    print()
    print("Notes:")
    print("  - ZHVI = Zillow Home Value Index (smoothed, seasonally adjusted)")
    print("  - ZORI = Zillow Observed Rent Index (smoothed, seasonally adjusted)")
    print("  - Both are monthly time series by zip code")
    print("  - If download fails, get CSVs manually from:")
    print("    https://www.zillow.com/research/data/")


if __name__ == '__main__':
    main()
