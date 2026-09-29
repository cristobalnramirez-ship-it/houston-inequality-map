# Capital Flow Tracker — Indicator Methodology

> **Status: superseded.** This document describes the original sample-data design, which was never published. The live Capital Flow layer is built by `build_capital_flow.py` from real Zillow ZHVI/ZORI and Census ACS data and shows descriptive measures only (value and rent change, typical value and rent, value-to-income, rent burden, renter share). It has no composite score; the "displacement risk" and "flip rate" definitions below were dropped (as defined, "flip rate" measured market competitiveness, not flipping).


## Overview

The Capital Flow Tracker computes 8 indicators for each Houston zip code, measuring housing market dynamics and displacement risk. Data is sourced from Zillow, Redfin, and the US Census Bureau.

## Data Sources

| Source | Data | Update Frequency | Access |
|--------|------|-----------------|--------|
| **Zillow ZHVI** | Median home values by zip | Monthly | Free CSV download |
| **Zillow ZORI** | Median rents by zip | Monthly | Free CSV download |
| **Redfin Data Center** | Sale prices, listings, DOM, inventory | Monthly | Free TSV download |
| **Census ACS 5-Year** | Income, rent burden, demographics, housing tenure | Annual | Free API (key required) |

## Indicator Definitions

### 1. Listing Velocity (ratio)

**What it measures:** How quickly homes are turning over in the market. Higher values indicate a hotter, more competitive market.

**Formula:**
```
listing_velocity = new_listings / active_inventory
```

**Interpretation:**
- < 0.5: Very slow market (buyer's market)
- 0.5 - 1.0: Balanced market
- 1.0 - 2.0: Active market
- > 2.0: Very hot market (seller's market)

**Source:** Redfin `new_listings` and `inventory` fields.

---

### 2. Price Trajectory (%)

**What it measures:** The 3-year growth rate in median home prices. Captures sustained price appreciation trends, not just short-term fluctuations.

**Formula:**
```
price_trajectory = ((current_median_value - value_3yr_ago) / value_3yr_ago) * 100
```

**Interpretation:**
- < 0%: Price decline
- 0 - 15%: Normal appreciation (~5%/year)
- 15 - 35%: Above-average growth
- > 35%: Rapid appreciation (potential gentrification signal)

**Source:** Zillow ZHVI time series, with Redfin `median_sale_price_yoy` as fallback.

---

### 3. Rental Yield Pressure (%)

**What it measures:** Gross rental yield — how much rental income a property generates relative to its value. High yields attract investors; low yields suggest owner-occupant pricing.

**Formula:**
```
rental_yield = (median_monthly_rent * 12) / median_home_value * 100
```

**Interpretation:**
- < 4%: Low yield (expensive relative to rents — appreciation play)
- 4 - 6%: Moderate yield
- 6 - 8%: Attractive to investors
- > 8%: High yield (strong investor incentive — often in lower-income areas)

**Source:** Zillow ZORI for rents, Zillow ZHVI for home values, Census ACS as fallback.

---

### 4. Investor Activity Index (0-100)

**What it measures:** Composite proxy for institutional and investor presence in the housing market. Higher values indicate more investment activity.

**Components:**
```
investor_activity = normalize(
    vacancy_rate * 40 +
    renter_share * 30 +
    price_growth (capped at 30) +
    speed_factor (15 - DOM/5)
) / num_components * (100/30)
```

**Interpretation:**
- < 25: Low investor activity (owner-occupant dominant)
- 25 - 50: Moderate investor presence
- 50 - 75: High investor activity
- > 75: Very high (potential institutional buying)

**Source:** Census ACS (vacancy, tenure), Redfin (DOM, price growth).

---

### 5. Days on Market Shift (days)

**What it measures:** Year-over-year change in median days on market. Negative values mean homes are selling faster than last year.

**Formula:**
```
dom_shift = median_dom_current - median_dom_year_ago
```

**Interpretation:**
- < -10: Rapidly accelerating market
- -10 to 0: Market heating up
- 0 to +10: Market cooling
- > +10: Significant slowdown

**Source:** Redfin `median_dom_yoy` field.

---

### 6. Displacement Risk Score (0-100)

**What it measures:** Weighted composite of factors that predict displacement of existing residents. The signature metric of this tracker.

**Formula:**
```
displacement_risk = (
    0.25 * normalize(price_appreciation_rate) +
    0.20 * normalize(investor_activity) +
    0.20 * normalize(rent_burden) +
    0.15 * normalize(vacancy_rate) +
    0.10 * normalize(income_vulnerability) +
    0.10 * normalize(renter_share)
)
```

**Component weights and rationale:**
| Component | Weight | Rationale |
|-----------|--------|-----------|
| Price appreciation | 0.25 | Strongest displacement signal — rising prices push out existing residents |
| Investor activity | 0.20 | Investors purchasing properties often leads to rent increases or conversion |
| Rent burden | 0.20 | Residents already spending >30% on rent are most vulnerable |
| Vacancy rate | 0.15 | High vacancy + price growth suggests speculative holding |
| Income vulnerability | 0.10 | Lower-income areas have less financial resilience |
| Renter share | 0.10 | Renters face eviction risk; owners have more stability |

**Interpretation:**
- < 30: Lower risk
- 30 - 60: Moderate risk — worth monitoring
- 60 - 80: High risk — active displacement likely occurring
- > 80: Critical — rapid neighborhood transformation underway

**"The Jarring View":** Enable both the HOLC Redlining layer (1940) and the Capital Flow layer (Displacement Risk). Areas graded "D — Hazardous" in 1940 often show the highest displacement risk scores in 2026, revealing how historical disinvestment created the conditions for current gentrification.

---

### 7. Flip Rate (%)

**What it measures:** Estimated percentage of home sales that are "flips" — properties purchased and resold within a short holding period. Higher rates indicate speculative activity.

**Formula:**
```
flip_rate = (sold_above_list% + off_market_in_two_weeks%) / 2 * 100
```

**Fallback (when Redfin data unavailable):**
```
flip_rate = min(25, (price_trajectory + investor_activity) / 4)
```

**Interpretation:**
- < 5%: Normal market activity
- 5 - 10%: Moderate flipping
- 10 - 15%: High flip rate — active speculative investment
- > 15%: Very high — significant market transformation

**Source:** Redfin `sold_above_list` and `off_market_in_two_weeks` as proxies.

---

### 8. Affordability Cliff (ratio)

**What it measures:** How affordable housing is relative to local incomes. A ratio of 1.0 means the median home costs exactly 4x the median income (a common affordability benchmark).

**Formula:**
```
affordability_cliff = median_home_value / (median_household_income * 4)
```

**Interpretation:**
- < 0.75: Very affordable (home costs < 3x income)
- 0.75 - 1.0: Affordable (within traditional lending guidelines)
- 1.0 - 1.5: Stretched affordability
- 1.5 - 2.5: Unaffordable for median-income residents
- > 2.5: Severely unaffordable

**Source:** Census ACS `median_home_value` and `median_household_income`.

## Normalization

All indicators that feed into composite scores are normalized to a 0-100 scale using min-max normalization across all Houston zip codes:

```
normalized = (value - min) / (max - min) * 100
```

Missing values default to 50 (median) to avoid biasing composite scores.

## Limitations

1. **Sample data:** The default installation uses simulated data. Run the full pipeline with real API data for production use.
2. **ZCTA vs ZIP:** Census data uses Zip Code Tabulation Areas (ZCTAs), which approximate but don't exactly match USPS zip codes.
3. **Temporal lag:** Census ACS 5-year estimates average over 5 years, masking recent changes. Zillow/Redfin data is more current.
4. **Investor proxy:** True investor activity data (cash purchases, LLC ownership) is not publicly available at zip level. Our index uses proxy indicators.
5. **Permit data:** Building permit data (a key gentrification signal) is not yet integrated. Future versions will scrape City of Houston permit records.
6. **Polygon approximation:** When Census TIGER/Line shapefiles are unavailable, zip code boundaries are approximated as hexagons centered on zip code centroids.

## Update Schedule

For best results, refresh data monthly:
- **Zillow/Redfin:** New data published monthly
- **Census ACS:** Updated annually (new 5-year estimates each December)
- **Indicators:** Recompute after any data source update
