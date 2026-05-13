"""Seed the SQLite database from ODS source files."""
import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "council_tax.db")

REGION_NAMES = {
    "SE": "South East",
    "E": "East of England",
    "EM": "East Midlands",
    "NW": "North West",
    "L": "London",
    "WM": "West Midlands",
    "SW": "South West",
    "YH": "Yorkshire and the Humber",
    "NE": "North East",
    "[z]": "Not Applicable",
}

CLASS_NAMES = {
    "SD": "Shire District",
    "UA": "Unitary Authority",
    "MD": "Metropolitan District",
    "OLB": "Outer London Borough",
    "ILB": "Inner London Borough",
}


def to_float(val):
    try:
        f = float(val)
        if f != f:  # NaN
            return None
        return round(f, 2)
    except (TypeError, ValueError):
        return None


def load_billing(fname, year_label):
    df = pd.read_excel(fname, engine="odf", sheet_name="Data_Billing", header=4)
    mask = df["E-code"].apply(
        lambda x: len(str(x)) > 4
        and str(x) not in ["TE", "ILB", "OLB", "MD", "UA", "SD", "SC", "CC", "CB", "Eng", "nan"]
    )
    df = df[mask].copy()
    cols = df.columns
    rows = []
    for _, r in df.iterrows():
        bd_curr = to_float(r[cols[25]])
        bd_prev = to_float(r[cols[24]])
        pct_change = None
        if bd_curr is not None and bd_prev and bd_prev > 0:
            pct_change = round((bd_curr - bd_prev) / bd_prev * 100, 2)
        rows.append({
            "ecode": str(r["E-code"]).strip(),
            "ons_code": str(r["ONS Code"]).strip(),
            "authority": str(r["Authority"]).strip(),
            "region_code": str(r["Region"]).strip(),
            "class_code": str(r["Class"]).strip(),
            "year": year_label,
            "ct_requirement": to_float(r[cols[7]]),
            "parish_precept": to_float(r[cols[11]]),
            "taxbase": to_float(r[cols[17]]),
            "collection_rate": to_float(r[cols[19]]),
            "band_d_billing": bd_curr,
            "band_d_area": to_float(r[cols[37]]),
            "asc_precept": to_float(r[cols[29]]),
            "band_d_prev": bd_prev,
            "pct_change": pct_change,
        })
    return rows


def create_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS region (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS authority_class (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS authority (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ecode TEXT NOT NULL UNIQUE,
        ons_code TEXT NOT NULL,
        name TEXT NOT NULL,
        region_code TEXT NOT NULL REFERENCES region(code),
        class_code TEXT NOT NULL REFERENCES authority_class(code)
    );

    CREATE TABLE IF NOT EXISTS council_tax_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        authority_id INTEGER NOT NULL REFERENCES authority(id),
        year TEXT NOT NULL,
        ct_requirement REAL,
        parish_precept REAL,
        taxbase REAL,
        collection_rate REAL,
        band_d_billing REAL,
        band_d_area REAL,
        asc_precept REAL,
        band_d_prev REAL,
        pct_change REAL
    );

    CREATE INDEX IF NOT EXISTS idx_ctr_authority ON council_tax_record(authority_id);
    CREATE INDEX IF NOT EXISTS idx_ctr_year ON council_tax_record(year);
    CREATE INDEX IF NOT EXISTS idx_auth_region ON authority(region_code);
    CREATE INDEX IF NOT EXISTS idx_auth_class ON authority(class_code);
    """)


def seed(ods_25, ods_26):
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    for code, name in REGION_NAMES.items():
        conn.execute("INSERT OR IGNORE INTO region VALUES (?,?)", (code, name))
    for code, name in CLASS_NAMES.items():
        conn.execute("INSERT OR IGNORE INTO authority_class VALUES (?,?)", (code, name))

    rows_25 = load_billing(ods_25, "2025-26")
    rows_26 = load_billing(ods_26, "2026-27")
    all_rows = rows_25 + rows_26

    authority_map = {}
    for r in all_rows:
        key = r["ecode"]
        if key not in authority_map:
            conn.execute(
                "INSERT OR IGNORE INTO authority (ecode,ons_code,name,region_code,class_code)"
                " VALUES (?,?,?,?,?)",
                (r["ecode"], r["ons_code"], r["authority"], r["region_code"], r["class_code"]),
            )
            row = conn.execute("SELECT id FROM authority WHERE ecode=?", (key,)).fetchone()
            if row:
                authority_map[key] = row[0]

    for r in all_rows:
        auth_id = authority_map.get(r["ecode"])
        if auth_id:
            conn.execute(
                """INSERT INTO council_tax_record
                   (authority_id,year,ct_requirement,parish_precept,taxbase,collection_rate,
                    band_d_billing,band_d_area,asc_precept,band_d_prev,pct_change)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    auth_id, r["year"], r["ct_requirement"], r["parish_precept"],
                    r["taxbase"], r["collection_rate"], r["band_d_billing"],
                    r["band_d_area"], r["asc_precept"], r["band_d_prev"], r["pct_change"],
                ),
            )

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM council_tax_record").fetchone()[0]
    auth_count = conn.execute("SELECT COUNT(*) FROM authority").fetchone()[0]
    print(f"Seeded {auth_count} authorities, {total} council tax records.")
    conn.close()
    return auth_count, total


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    seed(
        os.path.join(base, "data", "Table_10_2025-26.ods"),
        os.path.join(base, "data", "Table_10_2026-27.ods"),
    )
