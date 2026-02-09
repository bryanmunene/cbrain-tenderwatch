# Source-specific scoring bonuses
# Applied after keyword scoring to boost high-value sources

SOURCE_BIAS = {
    # International organizations (high-value, formal procurement)
    "undp": 10,
    "world bank": 8,
    "african development bank": 8,
    "afdb": 8,
    "ifc": 7,
    "un": 6,
    
    # Kenya sources (primary market - strong boost)
    "kenya": 10,
    "kaa": 12,  # Kenya Airports Authority
    "kra": 10,  # Kenya Revenue Authority
    "kebs": 10,  # Kenya Bureau of Standards
    "nhif": 10,  # National Hospital Insurance Fund
    "nssf": 10,  # National Social Security Fund
    "ntsa": 10,  # National Transport and Safety Authority
    "epra": 10,  # Energy and Petroleum Regulatory Authority
    "ca": 8,    # Communications Authority
    "kengen": 10,
    "kplc": 10,  # Kenya Power
    "kpc": 10,   # Kenya Pipeline Company
    "kcaa": 10,  # Kenya Civil Aviation Authority
    "kmtc": 10,  # Kenya Medical Training College
    "kicd": 10,  # Kenya Institute of Curriculum Development
    "ksg": 8,    # Kenya School of Government
    "ppra": 10,  # Public Procurement Regulatory Authority
    "tenders.go.ke": 10,
    "ifmis": 10,
    "mygov": 8,
    
    # East Africa (secondary market)
    "uganda": 5,
    "tanzania": 5,
    "rwanda": 5,
    "ethiopia": 5,
    
    # Other African countries
    "nigeria": 4,
    "ghana": 4,
    "south africa": 4,
    "ketraco": 10,  # Kenya Electricity Transmission Company
    "kemsa": 10,    # Kenya Medical Supplies Authority
    "kpa": 10,      # Kenya Ports Authority
    "nema": 10,     # National Environment Management Authority
    "cak": 10,      # Competition Authority of Kenya
    "ict authority": 10,
    "cbk": 10,      # Central Bank of Kenya
    "kenha": 10,    # Kenya National Highways Authority
    "kura": 10,     # Kenya Urban Roads Authority
    "knh": 10,      # Kenyatta National Hospital
    "mtrh": 10,     # Moi Teaching & Referral Hospital
    "uon": 10,      # University of Nairobi
    "ku": 10,       # Kenyatta University
    "jkuat": 10,    # Jomo Kenyatta University of Agriculture & Technology
    "moi university": 10,
    "nairobi county": 10,
    "mombasa county": 10,
    "kisumu county": 10,
    "nakuru county": 10,
    "kiambu county": 10,
}

# Country mapping for source name -> country
COUNTRY_MAP = {
    "kenya": "Kenya",
    "kaa": "Kenya",
    "kra": "Kenya",
    "kebs": "Kenya",
    "nhif": "Kenya",
    "nssf": "Kenya",
    "ntsa": "Kenya",
    "epra": "Kenya",
    "kengen": "Kenya",
    "kplc": "Kenya",
    "kpc": "Kenya",
    "kcaa": "Kenya",
    "kmtc": "Kenya",
    "kicd": "Kenya",
    "ksg": "Kenya",
    "ppra": "Kenya",
    "ifmis": "Kenya",
    "mygov": "Kenya",
    "tenders.go.ke": "Kenya",
    "uganda": "Uganda",
    "tanzania": "Tanzania",
    "rwanda": "Rwanda",
    "ethiopia": "Ethiopia",
    "nigeria": "Nigeria",
    "ghana": "Ghana",
    "south africa": "South Africa",
    "undp": "Global",
    "world bank": "Global",
    "afdb": "Global",
    "un": "Global",
}

COUNTRY_MAP.update({
    "ketraco": "Kenya",
    "kemsa": "Kenya",
    "kpa": "Kenya",
    "nema": "Kenya",
    "cak": "Kenya",
    "ict authority": "Kenya",
    "cbk": "Kenya",
    "kenha": "Kenya",
    "kura": "Kenya",
    "knh": "Kenya",
    "mtrh": "Kenya",
    "uon": "Kenya",
    "ku": "Kenya",
    "jkuat": "Kenya",
    "moi university": "Kenya",
    "nairobi county": "Kenya",
    "mombasa county": "Kenya",
    "kisumu county": "Kenya",
    "nakuru county": "Kenya",
    "kiambu county": "Kenya",
})
