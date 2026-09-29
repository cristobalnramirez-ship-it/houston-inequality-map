"""
Classify a property owner name into a small set of owner types.

The rules are deliberately transparent keyword rules, so anyone can audit
them. They err on the side of NOT calling an owner a company: a name is
"company" only if it carries an explicit entity marker (LLC, INC, LP ...).

Owner types
  institutional  one of the large single-family-rental operators listed below
  company        any other business entity (LLC, corporation, partnership ...)
  builder        homebuilders (new, unsold inventory - not investors)
  lender         banks, mortgage servicers, Fannie/Freddie/HUD (foreclosures)
  public         government, housing authorities, land banks, churches, nonprofits
  trust          trusts and estates (usually families, not investors)
  individual     everything else

Known limits: some families hold homes in LLCs, and some investors hold
homes in their own names, so "company" is an approximation of investor
ownership, not a measurement of it.
"""

import re

# Large single-family rental operators and their common holding-entity names.
# Parent company for each large operator, for checking totals against published counts
# (e.g. Kinder Institute, Jan 2026: nine institutional investors, ~11,000 Harris County homes in 2024).
# iBuyers (Opendoor, Offerpad) hold homes briefly for resale and are reported separately.
OPERATORS = [
    ('Invitation Homes', r'INVITATION HOMES|\bIH[2-6] PROPERTY|\bTHR PROPERTY|\bIH BORROWER|\bINVH\b'),
    ('American Homes 4 Rent (AMH)', r'AMERICAN HOMES 4 RENT|\bAMH\b|\bARP [0-9]|\bAH4R\b|AMERICAN RESIDENTIAL PROPERTIES'),
    ('Pretium (Progress Residential)', r'PROGRESS RESIDENTIAL|\bPROGRESS (AUSTIN|DALLAS|HOUSTON|SAN ANTONIO)|PRETIUM|FRONT YARD RESIDENTIAL'),
    ('Cerberus (FirstKey Homes)', r'\bFKH SFR|FIRSTKEY HOMES|CERBERUS SFR'),
    ('Tricon', r'\bTRICON\b|\bSFR JV-?\d|\bSFR [IVX]+ '),
    ('Amherst (Main Street Renewal)', r'MAIN STREET RENEWAL|\bMSR\b|AMHERST'),
    ('Blackstone (Home Partners)', r'HOME PARTNERS OF AMERICA|\bHPA (TEXAS|US|BORROWER|II|I)\b|\bBRE SELECT'),
    ('VineBrook', r'VINEBROOK'),
    ('Pathlight', r'PATHLIGHT'),
    ('ResiCap', r'RESICAP'),
    ('iBuyer: Opendoor', r'OPENDOOR'),
    ('iBuyer: Offerpad', r'OFFERPAD'),
]
INSTITUTIONAL = [p for label, p in OPERATORS if not label.startswith('iBuyer')]  # iBuyers count as 'company'

BUILDERS = [
    r'\bD ?R HORTON', r'\bLENNAR', r'PERRY HOMES', r'MERITAGE', r'\bKB HOME', r'TAYLOR MORRISON',
    r'\bPULTE', r'CENTEX', r'DAVID WEEKLEY', r'HIGHLAND HOMES', r'CHESMAR', r'CASTLEROCK COMMUNITIES',
    r'LGI HOMES', r'BEAZER', r'CENTURY COMMUNITIES', r'M/I HOMES', r'ASHTON WOODS', r'NEWMARK HOMES',
    r'TRENDMAKER', r'SAN JACINTO HOMES', r'CAMILLO', r'BRIGHTLAND', r'STARLIGHT HOMES', r'\bSHEA HOMES',
    r'TOLL BROTHERS', r'GEHAN', r'COVENTRY HOMES', r'PARTNERS IN BUILDING', r'CALATLANTIC',
]

LENDERS = [
    r'FEDERAL NATIONAL MORTGAGE', r'FANNIE MAE', r'FEDERAL HOME LOAN MORTGAGE', r'FREDDIE MAC',
    r'SECRETARY OF HOUSING', r'\bHUD\b', r'VETERANS AFFAIRS', r'\bBANK\b', r'MORTGAGE', r'LOAN SERVICING',
    r'NATIONSTAR', r'MR COOPER', r'WILMINGTON SAVINGS', r'\bU ?S BANK', r'DEUTSCHE BANK', r'BANK OF NEW YORK',
]

PUBLIC = [
    r'\bCITY OF\b', r'\bCOUNTY\b', r'\bSTATE OF\b', r'HOUSING AUTHORITY', r'\bISD\b', r'INDEPENDENT SCHOOL',
    r'LAND BANK', r'HOUSING (FINANCE )?CORP', r'REDEVELOPMENT AUTHORITY', r'\bTIRZ\b', r'\bMUD\b',
    r'MUNICIPAL UTILITY', r'CHURCH', r'MINISTR', r'HABITAT FOR HUMANITY', r'COMMUNITY LAND TRUST',
    r'\bCDC\b', r'COMMUNITY DEVELOPMENT', r'UNITED STATES', r'\bTXDOT\b', r'DEPARTMENT OF TRANSPORTATION',
    r'UNIVERSITY', r'COLLEGE', r'FLOOD CONTROL',
]

TRUST = [r'\bTRUST\b', r'\bTRUSTEE', r'\bTRS\b', r'\bESTATE OF\b', r'\bEST OF\b', r'LIVING TR\b', r'REVOCABLE']

COMPANY = [
    r'\bL ?L ?C\b', r'\bL ?L ?P\b', r'\bL ?P\b', r'\bLTD\b', r'\bINC\b', r'\bCORP', r'\bCO\b\.?$', r'\bCOMPANY\b',
    r'\bPARTNERS', r'\bPARTNERSHIP', r'\bHOLDINGS?\b', r'\bPROPERTIES\b', r'\bPROPERTY\b', r'\bINVESTMENTS?\b',
    r'\bINVESTORS?\b', r'\bCAPITAL\b', r'\bREALTY\b', r'\bREAL ESTATE\b', r'\bGROUP\b', r'\bVENTURES?\b',
    r'\bFUND\b', r'\bENTERPRISES?\b', r'\bMANAGEMENT\b', r'\bDEVELOPMENT\b', r'\bASSETS?\b', r'\bEQUITY\b',
    r'\bREIT\b', r'\bSERIES\b', r'\bRENTALS?\b', r'\bHOMES\b', r'\bRESIDENTIAL\b', r'\bBORROWER\b',
]

_compiled = {k: re.compile('|'.join(v)) for k, v in [
    ('institutional', INSTITUTIONAL), ('builder', BUILDERS), ('lender', LENDERS),
    ('public', PUBLIC), ('trust', TRUST), ('company', COMPANY)]}

ORDER = ['institutional', 'builder', 'public', 'lender', 'trust', 'company']


def normalize(name):
    return re.sub(r'[^A-Z0-9/& ]+', ' ', (name or '').upper()).strip()


def classify(name):
    n = ' ' + normalize(name) + ' '
    if not n.strip():
        return 'unknown'
    for k in ORDER:
        if _compiled[k].search(n):
            return k
    return 'individual'


INVESTOR_TYPES = {'institutional', 'company'}

_operators = [(n, re.compile(p)) for n, p in OPERATORS]


def operator(name):
    n = ' ' + normalize(name) + ' '
    return next((label for label, rx in _operators if rx.search(n)), None)


if __name__ == '__main__':
    tests = {
        'INVITATION HOMES REALTY LLC': 'institutional', 'IH6 PROPERTY TEXAS LP': 'institutional',
        'PROGRESS RESIDENTIAL BORROWER 12 LLC': 'institutional', 'AMERICAN HOMES 4 RENT PROPERTIES FOUR LLC': 'institutional',
        'SMITH JOHN & MARY': 'individual', 'GARCIA MARIA E': 'individual',
        'BLUE BAYOU PROPERTIES LLC': 'company', 'ACME HOLDINGS LTD': 'company',
        'D R HORTON - TEXAS LTD': 'builder', 'LENNAR HOMES OF TEXAS SALES & MARKETING LTD': 'builder',
        'FEDERAL NATIONAL MORTGAGE ASSOCIATION': 'lender', 'CITY OF HOUSTON': 'public',
        'HOUSTON LAND BANK': 'public', 'JONES FAMILY TRUST': 'trust', 'ESTATE OF LEE ROBERT': 'trust',
        'HOUSTON HOUSING AUTHORITY': 'public',
    }
    bad = {k: (classify(k), v) for k, v in tests.items() if classify(k) != v}
    # every institutional name should map to an operator, and vice versa
    for k, v in tests.items():
        if (v == 'institutional') != bool(operator(k)):
            bad[k] = ('operator', operator(k))
    print('all rules pass' if not bad else bad)
