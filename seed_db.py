"""
Seed the SQLite database from all four ODS source files.
Tables loaded:
  - Table 10 (Data_Billing)  -> council_tax_record (billing authorities, 2 years)
  - Table 8a  -> precepting_record (London boroughs, met districts, unitaries)
  - Table 8b  -> precepting_record (shire counties)
  - Table 8c  -> precepting_record (shire districts)
  - Table 8d  -> precepting_record (police)
  - Table 8e  -> precepting_record (fire)
  - Table 8f  -> precepting_record (combined authorities)
  - Table 9   -> band_record (per-authority Band A-H breakdown)
  - Table 3   -> england_trend (national Band D history 2011-2027)
  - Table 7   -> regional_trend (area Band D by authority type, 5 years)
"""
import sqlite3, os, re
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "council_tax.db")
DATA_DIR = os.path.join(BASE_DIR, "data")

REGION_NAMES = {
    "SE":"South East","E":"East of England","EE":"East of England",
    "EM":"East Midlands","NW":"North West","L":"London",
    "WM":"West Midlands","SW":"South West","YH":"Yorkshire and the Humber",
    "NE":"North East","[z]":"Not Applicable",
}
CLASS_NAMES = {
    "SD":"Shire District","UA":"Unitary Authority",
    "MD":"Metropolitan District","OLB":"Outer London Borough",
    "ILB":"Inner London Borough","SC":"Shire County",
    "PCC":"Police and Crime Commissioner","FRA":"Fire and Rescue Authority",
    "CA":"Combined Authority",
}

PRECEPT_TYPES = {
    "8a": "London / Metropolitan / Unitary",
    "8b": "Shire County",
    "8c": "Shire District",
    "8d": "Police and Crime Commissioner",
    "8e": "Fire and Rescue Authority",
    "8f": "Combined Authority",
}

def flt(v):
    try:
        f = float(v)
        return None if f != f else round(f, 2)
    except: return None

def clean_year(y):
    """Strip notes like [r], [note x] from year strings."""
    return re.sub(r'\s*\[.*?\]', '', str(y)).strip()

# ── Schema ────────────────────────────────────────────────────────────────────
DDL = """
CREATE TABLE IF NOT EXISTS region (
    code TEXT PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authority_class (
    code TEXT PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authority (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ecode       TEXT NOT NULL UNIQUE,
    ons_code    TEXT NOT NULL,
    name        TEXT NOT NULL,
    region_code TEXT NOT NULL REFERENCES region(code),
    class_code  TEXT NOT NULL REFERENCES authority_class(code)
);
CREATE TABLE IF NOT EXISTS council_tax_record (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    authority_id    INTEGER NOT NULL REFERENCES authority(id),
    year            TEXT NOT NULL,
    ct_requirement  REAL, parish_precept REAL, taxbase REAL,
    collection_rate REAL, band_d_billing REAL, band_d_area REAL,
    asc_precept     REAL, band_d_prev    REAL, pct_change REAL
);
CREATE TABLE IF NOT EXISTS precepting_record (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    authority_id    INTEGER NOT NULL REFERENCES authority(id),
    precept_type    TEXT NOT NULL,
    year            TEXT NOT NULL,
    band_d          REAL,
    band_d_prev     REAL,
    pct_change      REAL,
    asc_element     REAL
);
CREATE TABLE IF NOT EXISTS band_record (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    authority_id INTEGER NOT NULL REFERENCES authority(id),
    year         TEXT NOT NULL,
    band_a REAL, band_b REAL, band_c REAL, band_d REAL,
    band_e REAL, band_f REAL, band_g REAL, band_h REAL
);
CREATE TABLE IF NOT EXISTS england_trend (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    year_label TEXT NOT NULL UNIQUE,
    band_d     REAL,
    pct_change REAL
);
CREATE TABLE IF NOT EXISTS regional_trend (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    year_label   TEXT NOT NULL,
    england      REAL, england_chg   REAL,
    london       REAL, london_chg    REAL,
    metro        REAL, metro_chg     REAL,
    unitary      REAL, unitary_chg   REAL,
    shire        REAL, shire_chg     REAL
);
CREATE INDEX IF NOT EXISTS idx_ctr_auth ON council_tax_record(authority_id);
CREATE INDEX IF NOT EXISTS idx_ctr_year ON council_tax_record(year);
CREATE INDEX IF NOT EXISTS idx_pr_auth  ON precepting_record(authority_id);
CREATE INDEX IF NOT EXISTS idx_pr_year  ON precepting_record(year);
CREATE INDEX IF NOT EXISTS idx_br_auth  ON band_record(authority_id);
CREATE INDEX IF NOT EXISTS idx_auth_reg ON authority(region_code);
CREATE INDEX IF NOT EXISTS idx_auth_cls ON authority(class_code);
"""

# ── Helper: get or insert authority ──────────────────────────────────────────
_auth_cache = {}

def get_or_create_auth(conn, ecode, ons, name, region, cls_code):
    if ecode in _auth_cache:
        return _auth_cache[ecode]
    row = conn.execute("SELECT id FROM authority WHERE ecode=?", (ecode,)).fetchone()
    if row:
        _auth_cache[ecode] = row[0]; return row[0]
    # Normalise region code
    rcode = region.strip() if region.strip() in REGION_NAMES else "[z]"
    if rcode == "EE": rcode = "E"   # 2026-27 uses EE for East of England
    conn.execute(
        "INSERT OR IGNORE INTO authority (ecode,ons_code,name,region_code,class_code) VALUES (?,?,?,?,?)",
        (ecode, ons, name, rcode, cls_code))
    row = conn.execute("SELECT id FROM authority WHERE ecode=?", (ecode,)).fetchone()
    _auth_cache[ecode] = row[0]; return row[0]

# ── Table 10 – billing authorities ───────────────────────────────────────────
def load_billing(conn, fname, year):
    df = pd.read_excel(fname, engine="odf", sheet_name="Data_Billing", header=4)
    mask = df["E-code"].apply(
        lambda x: len(str(x))>4 and str(x) not in
        ["TE","ILB","OLB","MD","UA","SD","SC","CC","CB","Eng","nan"])
    df = df[mask].copy()
    cols = df.columns
    n = 0
    for _, r in df.iterrows():
        eid = get_or_create_auth(conn, str(r["E-code"]).strip(),
            str(r["ONS Code"]).strip(), str(r["Authority"]).strip(),
            str(r["Region"]).strip(), str(r["Class"]).strip())
        bd_curr = flt(r[cols[25]]); bd_prev = flt(r[cols[24]])
        pct = round((bd_curr-bd_prev)/bd_prev*100,2) if bd_curr and bd_prev and bd_prev>0 else None
        conn.execute(
            "INSERT INTO council_tax_record (authority_id,year,ct_requirement,parish_precept,"
            "taxbase,collection_rate,band_d_billing,band_d_area,asc_precept,band_d_prev,pct_change)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (eid,year,flt(r[cols[7]]),flt(r[cols[11]]),flt(r[cols[17]]),
             flt(r[cols[19]]),bd_curr,flt(r[cols[37]]),flt(r[cols[29]]),bd_prev,pct))
        n += 1
    return n

# ── Tables 8a/8b/8c/8d/8e/8f – precepting authorities ────────────────────────
def load_precepting(conn, fname, year, sheet, ptype, cls_code):
    df = pd.read_excel(fname, engine="odf", sheet_name=sheet, header=2)
    ecol = "E-code" if "E-code" in df.columns else "E Code"
    # drop summary / blank rows
    df = df[df[ecol].notna() & (df[ecol].astype(str).str.len() > 3)].copy()
    cols = df.columns
    n = 0
    for _, r in df.iterrows():
        ecode = str(r[ecol]).strip()
        if not ecode or ecode.startswith("nan"): continue
        ons = str(r.get("ONS Code","[z]")).strip()
        name = str(r.get("Authority","")).strip()
        region = str(r.get("Region","[z]")).strip()
        if region == "EE": region = "E"

        eid = get_or_create_auth(conn, ecode, ons, name, region, cls_code)

        # band_d is always col index 4 for 8b/8d/8e/8f, need to handle 8a/8c separately
        band_d = flt(r[cols[4]]) if len(cols) > 4 else None
        pct    = flt(r[cols[5]]) if len(cols) > 5 else None
        asc    = flt(r[cols[10]]) if len(cols) > 10 else None

        conn.execute(
            "INSERT INTO precepting_record (authority_id,precept_type,year,band_d,pct_change,asc_element)"
            " VALUES (?,?,?,?,?,?)",
            (eid, ptype, year, band_d, pct, asc))
        n += 1
    return n

# ── Table 9 – band breakdown ──────────────────────────────────────────────────
def load_bands(conn, fname, year):
    df = pd.read_excel(fname, engine="odf", sheet_name="Table_9", header=2)
    ecol = "E Code" if "E Code" in df.columns else "E-code"
    df = df[df[ecol].notna() & (df[ecol].astype(str).str.len() > 3)].copy()
    n = 0
    for _, r in df.iterrows():
        ecode = str(r[ecol]).strip()
        ons   = str(r.get("ONS Code","")).strip()
        name  = str(r.get("Authority","")).strip()
        region= str(r.get("Region","[z]")).strip()
        cls   = str(r.get("Class","UA")).strip()
        if region == "EE": region = "E"
        eid = get_or_create_auth(conn, ecode, ons, name, region, cls)
        conn.execute(
            "INSERT INTO band_record (authority_id,year,band_a,band_b,band_c,band_d,"
            "band_e,band_f,band_g,band_h) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (eid, year,
             flt(r.get("Band A")), flt(r.get("Band B")), flt(r.get("Band C")),
             flt(r.get("Band D")), flt(r.get("Band E")), flt(r.get("Band F")),
             flt(r.get("Band G ") or r.get("Band G")), flt(r.get("Band H"))))
        n += 1
    return n

# ── Table 3 – England historical trend ───────────────────────────────────────
def load_england_trend(conn, fname):
    df = pd.read_excel(fname, engine="odf", sheet_name="Table_3", header=2)
    n = 0
    for _, r in df.iterrows():
        yr = clean_year(r.get("Year",""))
        if not yr or yr in ("Year","nan"): continue
        bd = flt(r.get("Pounds £")); pct = flt(r.get("Percentage Change %"))
        conn.execute(
            "INSERT OR IGNORE INTO england_trend (year_label,band_d,pct_change) VALUES (?,?,?)",
            (yr, bd, pct))
        n += 1
    return n

# ── Table 7 – regional trend ──────────────────────────────────────────────────
def load_regional_trend(conn, fname):
    df = pd.read_excel(fname, engine="odf", sheet_name="Table_7", header=2)
    cols = list(df.columns)
    n = 0
    for _, r in df.iterrows():
        yr = clean_year(r[cols[0]])
        if not yr or yr in ("Year","nan"): continue
        conn.execute(
            "INSERT INTO regional_trend (year_label,england,england_chg,london,london_chg,"
            "metro,metro_chg,unitary,unitary_chg,shire,shire_chg) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (yr,
             flt(r[cols[1]]) if len(cols)>1 else None,
             flt(r[cols[2]]) if len(cols)>2 else None,
             flt(r[cols[3]]) if len(cols)>3 else None,
             flt(r[cols[4]]) if len(cols)>4 else None,
             flt(r[cols[5]]) if len(cols)>5 else None,
             flt(r[cols[6]]) if len(cols)>6 else None,
             flt(r[cols[7]]) if len(cols)>7 else None,
             flt(r[cols[8]]) if len(cols)>8 else None,
             flt(r[cols[9]]) if len(cols)>9 else None,
             flt(r[cols[10]]) if len(cols)>10 else None,
            ))
        n += 1
    return n

# ── Main ──────────────────────────────────────────────────────────────────────
def seed():
    global _auth_cache
    _auth_cache = {}

    if os.path.exists(DB_PATH): os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)

    for code, name in REGION_NAMES.items():
        conn.execute("INSERT OR IGNORE INTO region VALUES (?,?)", (code,name))
    for code, name in CLASS_NAMES.items():
        conn.execute("INSERT OR IGNORE INTO authority_class VALUES (?,?)", (code,name))

    f25 = os.path.join(DATA_DIR,"Table_10_2025-26.ods")
    f26 = os.path.join(DATA_DIR,"Table_10_2026-27.ods")
    g25 = os.path.join(DATA_DIR,"Tables_1-9_2025-26.ods")
    g26 = os.path.join(DATA_DIR,"Tables_1-9_2026-27.ods")

    totals = {}
    totals["billing_25"]    = load_billing(conn, f25, "2025-26")
    totals["billing_26"]    = load_billing(conn, f26, "2026-27")

    for sheet, ptype, cls in [
        ("Table_8a","London / Metropolitan / Unitary","UA"),
        ("Table_8b","Shire County","SC"),
        ("Table_8c","Shire District","SD"),
        ("Table_8d","Police and Crime Commissioner","PCC"),
        ("Table_8e","Fire and Rescue Authority","FRA"),
        ("Table_8f","Combined Authority","CA"),
    ]:
        totals[f"{sheet}_25"] = load_precepting(conn, g25, "2025-26", sheet, ptype, cls)
        totals[f"{sheet}_26"] = load_precepting(conn, g26, "2026-27", sheet, ptype, cls)

    totals["bands_25"] = load_bands(conn, g25, "2025-26")
    totals["bands_26"] = load_bands(conn, g26, "2026-27")
    totals["trend"]    = load_england_trend(conn, g25)
    load_england_trend(conn, g26)   # adds 2026-27 row idempotently
    totals["regional_25"] = load_regional_trend(conn, g25)
    totals["regional_26"] = load_regional_trend(conn, g26)

    conn.commit()

    auths      = conn.execute("SELECT COUNT(*) FROM authority").fetchone()[0]
    ctr        = conn.execute("SELECT COUNT(*) FROM council_tax_record").fetchone()[0]
    prec       = conn.execute("SELECT COUNT(*) FROM precepting_record").fetchone()[0]
    bands      = conn.execute("SELECT COUNT(*) FROM band_record").fetchone()[0]
    trend      = conn.execute("SELECT COUNT(*) FROM england_trend").fetchone()[0]
    reg_trend  = conn.execute("SELECT COUNT(*) FROM regional_trend").fetchone()[0]
    total      = ctr + prec + bands + trend + reg_trend

    print(f"Authorities:         {auths}")
    print(f"Billing records:     {ctr}  (Table 10, 2 years)")
    print(f"Precepting records:  {prec}  (Tables 8a-8f, 2 years)")
    print(f"Band records:        {bands}  (Table 9, 2 years)")
    print(f"England trend rows:  {trend}  (Table 3)")
    print(f"Regional trend rows: {reg_trend}  (Table 7, 2 years)")
    print(f"─────────────────────────────────")
    print(f"TOTAL RECORDS:       {total}")
    conn.close()
    return total

if __name__ == "__main__":
    seed()
