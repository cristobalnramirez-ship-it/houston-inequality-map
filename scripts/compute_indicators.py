#!/usr/bin/env python3
"""
compute_indicators.py — Calculate 8 capital flow indicators for Houston zip codes.

Reads:
  ../data/capital/census_acs_zip.csv
  ../data/capital/zillow_zhvi.csv       (optional — from fetch_zillow.py)
  ../data/capital/zillow_zori.csv       (optional — from fetch_zillow.py)
  ../data/capital/redfin_zip_market.csv (optional — from fetch_redfin.py)

Computes:
  1. Listing Velocity       — new_listings / inventory ratio (market heat)
  2. Price Trajectory        — 3-year median sale price growth rate
  3. Rental Yield Pressure   — (median_rent * 12) / median_home_value
  4. Investor Activity Index — composite proxy score (cash share, flip rate, vacancy)
  5. Days on Market Shift    — YoY change in median days on market
  6. Displacement Risk Score — weighted composite of 5 sub-indicators
  7. Flip Rate               — estimated short-hold resale percentage
  8. Affordability Cliff     — median_home_value / (median_household_income * 4)

Output:
  ../data/capital/indicators_by_zip.csv
"""

import os
import sys
import csv
import math
import random

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'capital')

# ── Helpers ──────────────────────────────────────────────────

def read_csv(path):
    """Read CSV into list of dicts. Returns empty list if file missing."""
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def safe_float(val, default=None):
    """Convert to float, returning default on failure."""
    if val is None or val == '' or val == 'None':
        return default
    try:
        v = float(val)
        return v if v >= 0 else default
    except (ValueError, TypeError):
        return default


def normalize_0_100(values):
    """Normalize a dict of {zip: value} to 0-100 scale."""
    valid = {k: v for k, v in values.items() if v is not None}
    if not valid:
        return {k: 50 for k in values}
    mn = min(valid.values())
    mx = max(valid.values())
    rng = mx - mn if mx != mn else 1
    result = {}
    for k in values:
        if values[k] is not None:
            result[k] = round((values[k] - mn) / rng * 100, 1)
        else:
            result[k] = 50  # median default for missing
    return result


def clamp(val, lo=0, hi=100):
    if val is None:
        return 50
    return max(lo, min(hi, val))


# ── Load Data Sources ────────────────────────────────────────

def load_census():
    """Load Census ACS data keyed by zip."""
    rows = read_csv(os.path.join(DATA_DIR, 'census_acs_zip.csv'))
    data = {}
    for r in rows:
        z = r.get('zip', '').strip()
        if z:
            data[z] = {
                'income': safe_float(r.get('median_household_income')),
                'rent': safe_float(r.get('median_gross_rent')),
                'home_value': safe_float(r.get('median_home_value')),
                'population': safe_float(r.get('total_population')),
                'owner_occupied': safe_float(r.get('owner_occupied')),
                'renter_occupied': safe_float(r.get('renter_occupied')),
                'total_housing': safe_float(r.get('total_housing_units')),
                'vacant': safe_float(r.get('vacant_housing_units')),
                'rent_burden_pct': safe_float(r.get('median_rent_burden_pct')),
                'pop_white': safe_float(r.get('pop_white')),
                'pop_black': safe_float(r.get('pop_black')),
                'pop_hispanic': safe_float(r.get('pop_hispanic')),
                'pop_asian': safe_float(r.get('pop_asian')),
            }
    return data


def load_redfin():
    """Load most recent Redfin data keyed by zip."""
    rows = read_csv(os.path.join(DATA_DIR, 'redfin_zip_market.csv'))
    if not rows:
        return {}

    # Group by zip, take most recent period
    by_zip = {}
    for r in rows:
        z = r.get('zip_code', '').strip()
        if not z:
            continue
        period = r.get('period_end', '')
        if z not in by_zip or period > by_zip[z].get('_period', ''):
            by_zip[z] = {
                '_period': period,
                'median_sale_price': safe_float(r.get('median_sale_price')),
                'median_sale_price_yoy': safe_float(r.get('median_sale_price_yoy')),
                'homes_sold': safe_float(r.get('homes_sold')),
                'new_listings': safe_float(r.get('new_listings')),
                'inventory': safe_float(r.get('inventory')),
                'median_dom': safe_float(r.get('median_dom')),
                'median_dom_yoy': safe_float(r.get('median_dom_yoy')),
                'avg_sale_to_list': safe_float(r.get('avg_sale_to_list')),
                'price_drops': safe_float(r.get('price_drops')),
                'months_of_supply': safe_float(r.get('months_of_supply')),
                'sold_above_list': safe_float(r.get('sold_above_list')),
                'off_market_in_two_weeks': safe_float(r.get('off_market_in_two_weeks')),
            }
    return by_zip


def load_zillow():
    """Load most recent Zillow ZHVI and ZORI keyed by zip."""
    zhvi_rows = read_csv(os.path.join(DATA_DIR, 'zillow_zhvi.csv'))
    zori_rows = read_csv(os.path.join(DATA_DIR, 'zillow_zori.csv'))

    zhvi = {}
    for r in zhvi_rows:
        z = str(r.get('RegionName', '')).strip()
        if not z:
            continue
        # Find most recent monthly column (columns after RegionName, RegionType, etc.)
        date_cols = [c for c in r.keys() if c.startswith('20') and '-' in c]
        if date_cols:
            date_cols.sort()
            latest = date_cols[-1]
            three_yrs_ago = None
            target = str(int(latest[:4]) - 3) + latest[4:]
            for dc in date_cols:
                if dc >= target:
                    three_yrs_ago = dc
                    break
            zhvi[z] = {
                'current_value': safe_float(r.get(latest)),
                'value_3yr_ago': safe_float(r.get(three_yrs_ago)) if three_yrs_ago else None,
            }

    zori = {}
    for r in zori_rows:
        z = str(r.get('RegionName', '')).strip()
        if not z:
            continue
        date_cols = [c for c in r.keys() if c.startswith('20') and '-' in c]
        if date_cols:
            date_cols.sort()
            latest = date_cols[-1]
            zori[z] = {
                'current_rent': safe_float(r.get(latest)),
            }

    return zhvi, zori


# ── Indicator Computation ────────────────────────────────────

def compute_all_indicators(census, redfin, zhvi, zori):
    """Compute all 8 indicators for each zip code."""
    all_zips = sorted(set(census.keys()))
    print(f"  Computing indicators for {len(all_zips)} zip codes...")

    # Raw values per indicator per zip
    raw = {z: {} for z in all_zips}

    for z in all_zips:
        c = census.get(z, {})
        r = redfin.get(z, {})
        zv = zhvi.get(z, {})
        zr = zori.get(z, {})

        # ── 1. Listing Velocity ──
        # new_listings / inventory (higher = hotter market)
        nl = r.get('new_listings')
        inv = r.get('inventory')
        if nl and inv and inv > 0:
            raw[z]['listing_velocity'] = nl / inv
        else:
            # Estimate from sale-to-list and months of supply
            stl = r.get('avg_sale_to_list')
            mos = r.get('months_of_supply')
            if stl and mos and mos > 0:
                raw[z]['listing_velocity'] = stl / mos * 2
            else:
                raw[z]['listing_velocity'] = None

        # ── 2. Price Trajectory ──
        # 3-year price growth rate (%)
        cur = zv.get('current_value') or r.get('median_sale_price')
        old = zv.get('value_3yr_ago')
        if cur and old and old > 0:
            raw[z]['price_trajectory'] = ((cur - old) / old) * 100
        elif r.get('median_sale_price_yoy') is not None:
            # Approximate 3-year from YoY
            raw[z]['price_trajectory'] = r['median_sale_price_yoy'] * 300  # YoY is a ratio like 0.05
        else:
            raw[z]['price_trajectory'] = None

        # ── 3. Rental Yield Pressure ──
        # Gross yield = (annual_rent / home_value) * 100
        rent = zr.get('current_rent') or c.get('rent')
        home_val = zv.get('current_value') or c.get('home_value')
        if rent and home_val and home_val > 0:
            raw[z]['rental_yield'] = (rent * 12 / home_val) * 100
        else:
            raw[z]['rental_yield'] = None

        # ── 4. Investor Activity Index ──
        # Composite: vacancy_rate + renter_share + price_growth + (1/DOM)
        total_h = c.get('total_housing')
        vacant = c.get('vacant')
        renter = c.get('renter_occupied')
        owner = c.get('owner_occupied')

        components = []
        if total_h and vacant:
            vacancy_rate = vacant / total_h
            components.append(vacancy_rate * 40)  # 0-12% range → 0-4.8 → scaled
        if renter and owner:
            renter_share = renter / (renter + owner) if (renter + owner) > 0 else 0.5
            components.append(renter_share * 30)
        price_growth = raw[z].get('price_trajectory')
        if price_growth is not None:
            components.append(min(30, max(0, price_growth)))  # cap at 30
        dom = r.get('median_dom')
        if dom and dom > 0:
            components.append(max(0, 15 - dom / 5))  # lower DOM = higher activity

        if components:
            raw[z]['investor_activity'] = sum(components) / len(components) * (100 / 30)
        else:
            raw[z]['investor_activity'] = None

        # ── 5. Days on Market Shift ──
        # Negative means market getting hotter (homes selling faster)
        dom_yoy = r.get('median_dom_yoy')
        if dom_yoy is not None:
            raw[z]['dom_shift'] = dom_yoy * 100 if abs(dom_yoy) < 5 else dom_yoy
        elif dom:
            # Estimate: lower DOM = hotter market
            raw[z]['dom_shift'] = -(30 - dom)  # center at 30 days
        else:
            raw[z]['dom_shift'] = None

        # ── 6. Displacement Risk Score ──
        # Weighted composite (higher = more risk of displacement)
        # Weights: price_appreciation(0.25), investor_activity(0.20),
        #          rent_burden(0.20), vacancy(0.15), demographic_shift(0.10),
        #          renter_share(0.10)
        risk_components = {}

        if price_growth is not None:
            risk_components['price_appreciation'] = min(100, max(0, price_growth * 3))

        inv_act = raw[z].get('investor_activity')
        if inv_act is not None:
            risk_components['investor_activity'] = clamp(inv_act)

        rent_burden = c.get('rent_burden_pct')
        if rent_burden is not None:
            risk_components['rent_burden'] = clamp(rent_burden * 2, 0, 100)

        if total_h and vacant:
            risk_components['vacancy'] = clamp(vacant / total_h * 500, 0, 100)

        income = c.get('income')
        if income:
            # Lower income = higher risk
            risk_components['income_vulnerability'] = clamp(100 - (income / 2000), 0, 100)

        if renter and owner and (renter + owner) > 0:
            risk_components['renter_share'] = clamp(renter / (renter + owner) * 100, 0, 100)

        if risk_components:
            weights = {
                'price_appreciation': 0.25,
                'investor_activity': 0.20,
                'rent_burden': 0.20,
                'vacancy': 0.15,
                'income_vulnerability': 0.10,
                'renter_share': 0.10,
            }
            weighted_sum = 0
            weight_total = 0
            for key, weight in weights.items():
                if key in risk_components:
                    weighted_sum += risk_components[key] * weight
                    weight_total += weight

            if weight_total > 0:
                raw[z]['displacement_risk'] = round(weighted_sum / weight_total, 1)
            else:
                raw[z]['displacement_risk'] = None
        else:
            raw[z]['displacement_risk'] = None

        # ── 7. Flip Rate ──
        # Estimated: (sold_above_list% + off_market_in_two_weeks%) / 2 as proxy
        sal = r.get('sold_above_list')
        otw = r.get('off_market_in_two_weeks')
        if sal is not None and otw is not None:
            raw[z]['flip_rate'] = (sal + otw) / 2 * 100
        elif price_growth is not None and inv_act is not None:
            # Proxy: hot market + investor activity suggests flipping
            raw[z]['flip_rate'] = min(25, max(0, (price_growth + inv_act) / 4))
        else:
            raw[z]['flip_rate'] = None

        # ── 8. Affordability Cliff ──
        # home_value / (income * 4) — above 1.0 = unaffordable
        if home_val and income and income > 0:
            raw[z]['affordability_cliff'] = round(home_val / (income * 4), 2)
        else:
            raw[z]['affordability_cliff'] = None

    return raw



def save_indicators(raw, output_path):
    """Save computed indicators to CSV."""
    if not raw:
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fieldnames = [
        'zip',
        'listing_velocity',
        'price_trajectory',
        'rental_yield',
        'investor_activity',
        'dom_shift',
        'displacement_risk',
        'flip_rate',
        'affordability_cliff',
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for z in sorted(raw.keys()):
            row = {'zip': z}
            row.update(raw[z])
            writer.writerow(row)

    print(f"  Saved indicators for {len(raw)} zip codes to {output_path}")


# ── Main ─────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Capital Flow Indicator Calculator — Houston Zip Codes")
    print("=" * 60)
    print()

    # Try to load real data first
    census = load_census()
    redfin = load_redfin()
    zhvi, zori = load_zillow()

    have_real_data = bool(census) and (bool(redfin) or bool(zhvi))

    if have_real_data:
        print(f"  Census data: {len(census)} zip codes")
        print(f"  Redfin data: {len(redfin)} zip codes")
        print(f"  Zillow ZHVI: {len(zhvi)} zip codes")
        print(f"  Zillow ZORI: {len(zori)} zip codes")
        print()
        raw = compute_all_indicators(census, redfin, zhvi, zori)
    else:
        if census:
            print(f"  Census data: {len(census)} zip codes")
            print(f"  No Redfin or Zillow data found — using census-based estimates")
        raise SystemExit("No Zillow/Redfin data found. Run fetch_zillow.py and fetch_redfin.py first. "
                         "(Sample-data generation was removed so fabricated values can never be published.)")

    if raw:
        output = os.path.join(DATA_DIR, 'indicators_by_zip.csv')
        save_indicators(raw, output)

    print()
    print("Indicators computed:")
    print("  1. listing_velocity    — New listings / inventory ratio")
    print("  2. price_trajectory    — 3-year median price growth (%)")
    print("  3. rental_yield        — Gross rental yield (%)")
    print("  4. investor_activity   — Composite investor activity (0-100)")
    print("  5. dom_shift           — Days-on-market change (neg = hotter)")
    print("  6. displacement_risk   — Displacement risk score (0-100)")
    print("  7. flip_rate           — Estimated flip rate (%)")
    print("  8. affordability_cliff — Home price / (4x income)")


if __name__ == '__main__':
    main()
