# Lending and ownership layers: method and validation

Built 2026-09-29. Scripts in this folder; raw inputs go in `data/raw/` (not committed).

## Mortgage lending (by census tract)

**Source.** CFPB/FFIEC HMDA Data Browser, Harris County (48201), home-purchase loans (`loan_purpose=1`), actions 1–3 (originated, approved but not accepted, denied), 2023–2025. The API returns only the first year when several are requested, so each year is fetched separately. Rows: 53,949 (2023), 55,224 (2024), 54,854 (2025).

**Universe.** Site-built single-family (1–4 unit) homes. Manufactured homes are excluded.

**Measures** (`build_hmda_tracts.py`), pooled over the three years:

| Measure | Definition |
|---|---|
| `investor_share` | originated loans where the borrower declared the home an investment property (`occupancy_type=3`) ÷ all originated loans |
| `denial_rate` | owner-occupant applications denied ÷ owner-occupant applications (originated + approved-not-accepted + denied) |
| `hispanic_share`, `black_share` | owner-occupant originations to Hispanic or Latino / Black or African American borrowers (HMDA's derived fields) |

Shares are withheld when the denominator is under 20. 223 of 1,115 tracts fall under that for `investor_share`. Most are apartment-dominated or industrial tracts with few home sales.

**County benchmark, 2023–2025:** 127,262 purchase loans. Of these, 9.2% went to investors. 12.4% of owner-occupant applications were denied. Owner-occupant borrowers were 32.2% Hispanic and 13.1% Black.

**Limits.** HMDA covers only financed purchases. Cash buyers, who include many investors, are missing, so `investor_share` undercounts investor buying. Loans are placed at the property's census tract.

## Single-family ownership (by ZIP)

**Source.** Harris Central Appraisal District, `Real_acct_owner.zip`, 2026 certified roll (downloaded 2026-09-29 from https://download.hcad.org/data/CAMA/2026/Real_acct_owner.zip). The build uses `real_acct.txt` and `owners.txt`, first-listed owner.

**Universe.** Texas property class A1 (single-family residential), with a ZIP taken from the site address: 1,157,439 homes in 145 ZIPs.

**Owner types** (`owner_classes.py`) come from transparent keyword rules, applied in this order:

| Type | Includes | Homes |
|---|---|---|
| institutional | large rental operators | 8,553 |
| builder | homebuilders | 5,678 |
| public | government, churches, nonprofits | 412 |
| lender | banks, servicers, Fannie Mae, Freddie Mac, HUD | 519 |
| trust | trusts and estates | 17,072 |
| company | any other entity with an LLC/LP/Inc-type marker | 54,158 |
| individual | everything else | 1,071,047 |

**Large operators.** A home counts as an operator's in either of two ways:

1. The holding entity's name matches that operator's patterns (e.g. `FKH SFR PROPCO`, `PROGRESS RESIDENTIAL BORROWER`).
2. The owner is a company whose tax-bill address is that operator's own corporate office, confirmed from SEC filings or company pages. The addresses are listed in `OPERATOR_ADDRESSES`. This rule picks up legacy entities whose names don't say who owns them:
   - Starwood Waypoint and Colony Starwood entities now owned by Invitation Homes (SRP SUB LLC, SWAY 2014-1, CSH 2016-2, SWH 2017-1).
   - Tricon's SFR JV-1 and SFR JV-2 joint ventures.
   - Amherst's BAF Assets entities.
   - FirstKey's RM1 SFR Propco entities.

**Manager addresses are not ownership.** Progress Residential also manages homes for owners it doesn't own. For example, Harris County eviction filings name "Progress Residential as agent for Yamasa Co. Ltd.", a separate Japanese company. Company-owned homes billed to Progress's PO boxes that no name rule matches (1,189 homes) are therefore not credited to Pretium. Yamasa's own homes (about 330) are excluded from address matching.

**New construction.** Company-held homes whose improvement year (`yr_impr`) is within the last two years (2024+) are left out of `company_owned_pct`. There are 4,815 such homes. These are mostly small developers' unsold townhomes held in LLCs. In Acres Homes (77091), Sunnyside (77051) and South Acres (77048), a quarter to more than a third of company-held homes were built in 2024 or later. The same homes are left out of `recent_sales` and `recent_company_pct`, which therefore describe existing homes only.

**Recent sales.** `new_own_dt` (the appraisal record's date of the latest ownership change) falls on or after 2023-09-28. This also captures non-sale transfers such as inheritances and transfers into a family LLC.

**Map measures per ZIP.** Shares are withheld under 50 homes, or under 20 recent changes for `recent_company_pct`.

| Measure | Definition |
|---|---|
| `company_owned_pct` | company-owned plus operator-owned homes ÷ all homes (company-held new builds removed from the numerator) |
| `institutional_pct` | operator-owned homes ÷ all homes |
| `out_of_state_owner_pct` | homes whose owner's mailing state is not Texas |
| `absentee_pct` | homes whose owner's mailing address differs from the site address |
| `recent_company_pct` | share of recent ownership changes where the new owner is a company or operator |

## Validation against the Kinder Institute (Jan. 22, 2026)

Kinder's [Urban Edge analysis](https://kinder.rice.edu/urbanedge/are-corporate-buyers-hogging-single-family-homes-harris-county-heres-what-data-shows) used 2024 Harris County property records and Eric Seymour's keyword list; 370 owner names were linked to nine firms. It found about 11,000 homes, roughly 1% of the county. Kinder names five of the nine firms and gives counts for three.

| Operator | This build (2026 roll) | by name | + office address | Kinder (2024) |
|---|---|---|---|---|
| Pretium (Progress Residential) | 1,627 | 1,627 | 0 | ~3,300 |
| Cerberus (FirstKey Homes) | 1,880 | 1,760 | 120 | ~2,200 |
| Invitation Homes | 1,667 | 428 | 1,239 | ~1,900 (company SEC filing: 2,347 in Greater Houston) |
| Tricon (Blackstone since 2024) | 1,491 | 821 | 670 | not given (gained ~200 since 2021) |
| American Homes 4 Rent | 1,222 | 1,210 | 12 | not given (lost ~500 since 2021) |
| Amherst (Main Street Renewal) | 332 | 31 | 301 | not named |
| ResiCap | 167 | 167 | 0 | not named |
| Blackstone (Home Partners) | 161 | 106 | 55 | not named |
| Pathlight | 6 | 6 | 0 | not named |
| **Total** | **8,553** | | | **~11,000** |

Also counted but kept separate:

- **iBuyers:** 174 homes (Opendoor 159, Offerpad 15), counted as "company", not operator.
- **Managed by Progress for owners it doesn't own:** 1,189 homes billed to Progress's PO boxes and not matched to Pretium, plus about 330 Yamasa homes.

**Reading the gap.**

- *Pretium.* Pretium's own entities account for 1,627 homes. Adding the homes Progress manages for others gives about 3,150, close to Kinder's 3,300. The likeliest explanation is that Kinder's keyword approach credited Pretium with homes that Progress manages but doesn't own. This build does not.
- *Cerberus and Invitation Homes.* These fall 10–15% short of Kinder. Part of the gap may be real: the 2026 roll is two years later than Kinder's data, and portfolios change (Kinder reports AMH shrinking by about 500 homes between 2021 and 2024). Part is entities neither rule catches.
- *Overall.* The totals agree on the order of magnitude: under 1% of Harris County single-family homes belong to large national operators. The much larger share held by other companies (about 5% of homes countywide, around 10% in Third Ward, OST/South Union, Sunnyside and South Acres) is where local investor activity shows up.

**Caution.** "Company" is an approximation. Some families hold homes in LLCs, and some investors hold homes in their own names.
