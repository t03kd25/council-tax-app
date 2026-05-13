"""Council Tax Explorer – Flask application using MHCLG open data."""
import sqlite3
import os
from flask import Flask, render_template, request, abort, g

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "council_tax.db")

YEARS = ["2025-26", "2026-27"]

REGION_LABELS = {
    "SE": "South East", "E": "East of England", "EM": "East Midlands",
    "NW": "North West", "L": "London", "WM": "West Midlands",
    "SW": "South West", "YH": "Yorkshire and the Humber", "NE": "North East",
}

CLASS_LABELS = {
    "SD": "Shire District", "UA": "Unitary Authority",
    "MD": "Metropolitan District", "OLB": "Outer London Borough",
    "ILB": "Inner London Borough",
}


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def _to_dict(row):
    return dict(row) if row else None


def query(sql, params=()):
    rows = get_db().execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def query_one(sql, params=()):
    row = get_db().execute(sql, params).fetchone()
    return dict(row) if row else None


@app.route("/")
def index():
    year = request.args.get("year", "2026-27")
    if year not in YEARS:
        year = "2026-27"
    stats = query_one(
        """SELECT AVG(r.band_d_area) AS avg_area_band_d,
                  AVG(r.band_d_billing) AS avg_billing_band_d,
                  MIN(r.band_d_area) AS min_area, MAX(r.band_d_area) AS max_area,
                  COUNT(*) AS total_las
           FROM council_tax_record r WHERE r.year=?""", (year,))
    highest = query(
        """SELECT a.name, a.region_code, r.band_d_area, r.band_d_billing, r.pct_change, a.id
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE r.year=? AND r.band_d_area IS NOT NULL
           ORDER BY r.band_d_area DESC LIMIT 5""", (year,))
    lowest = query(
        """SELECT a.name, a.region_code, r.band_d_area, r.band_d_billing, r.pct_change, a.id
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE r.year=? AND r.band_d_area IS NOT NULL
           ORDER BY r.band_d_area ASC LIMIT 5""", (year,))
    biggest_rises = query(
        """SELECT a.name, a.region_code, r.band_d_billing, r.pct_change, a.id
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE r.year=? AND r.pct_change IS NOT NULL
           ORDER BY r.pct_change DESC LIMIT 5""", (year,))
    return render_template("index.html", year=year, years=YEARS, stats=stats,
                           highest=highest, lowest=lowest, biggest_rises=biggest_rises,
                           region_labels=REGION_LABELS)


@app.route("/authorities")
def authorities():
    year = request.args.get("year", "2026-27")
    region = request.args.get("region", "")
    cls = request.args.get("cls", "")
    search = request.args.get("q", "").strip()
    sort = request.args.get("sort", "name")
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = 25
    if year not in YEARS:
        year = "2026-27"
    valid_sorts = {
        "name": "a.name ASC", "band_d_desc": "r.band_d_area DESC",
        "band_d_asc": "r.band_d_area ASC", "change_desc": "r.pct_change DESC",
        "change_asc": "r.pct_change ASC",
    }
    order_clause = valid_sorts.get(sort, "a.name ASC")
    filters = ["r.year = ?"]
    params = [year]
    if region:
        filters.append("a.region_code = ?"); params.append(region)
    if cls:
        filters.append("a.class_code = ?"); params.append(cls)
    if search:
        filters.append("a.name LIKE ?"); params.append(f"%{search}%")
    where = " AND ".join(filters)
    total_row = query_one(
        f"SELECT COUNT(*) AS cnt FROM council_tax_record r JOIN authority a ON a.id=r.authority_id WHERE {where}",
        params)
    total = total_row["cnt"] if total_row else 0
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    rows = query(
        f"""SELECT a.id, a.name, a.region_code, a.class_code,
                   r.band_d_billing, r.band_d_area, r.pct_change, r.taxbase
            FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
            WHERE {where} ORDER BY {order_clause} LIMIT ? OFFSET ?""",
        params + [per_page, offset])
    regions_list = query("SELECT code, name FROM region ORDER BY name")
    classes_list = query("SELECT code, name FROM authority_class ORDER BY name")
    return render_template("authorities.html", rows=rows, year=year, years=YEARS,
                           region=region, cls=cls, search=search, sort=sort,
                           page=page, total_pages=total_pages, total=total,
                           regions=regions_list, classes=classes_list,
                           region_labels=REGION_LABELS, class_labels=CLASS_LABELS)


@app.route("/authority/<int:auth_id>")
def authority_detail(auth_id):
    auth = query_one("SELECT * FROM authority WHERE id=?", (auth_id,))
    if not auth:
        abort(404)
    records = query("SELECT * FROM council_tax_record WHERE authority_id=? ORDER BY year",
                    (auth_id,))
    peers = query(
        """SELECT a.id, a.name, r.band_d_billing, r.band_d_area, r.pct_change
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE a.class_code=? AND a.region_code=? AND r.year='2026-27' AND a.id!=?
           ORDER BY r.band_d_area""",
        (auth["class_code"], auth["region_code"], auth_id))
    rank_row = query_one(
        """SELECT COUNT(*)+1 AS rnk FROM council_tax_record r
           JOIN authority a ON a.id=r.authority_id
           WHERE a.class_code=(SELECT class_code FROM authority WHERE id=?)
             AND r.year='2026-27'
             AND r.band_d_area < (SELECT band_d_area FROM council_tax_record
                                  WHERE authority_id=? AND year='2026-27')""",
        (auth_id, auth_id))
    class_size = query_one(
        """SELECT COUNT(*) AS cnt FROM council_tax_record r
           JOIN authority a ON a.id=r.authority_id
           WHERE a.class_code=(SELECT class_code FROM authority WHERE id=?)
             AND r.year='2026-27'""", (auth_id,))
    return render_template("authority_detail.html", auth=auth, records=records, peers=peers,
                           rank=rank_row["rnk"] if rank_row else None,
                           class_size=class_size["cnt"] if class_size else None,
                           region_labels=REGION_LABELS, class_labels=CLASS_LABELS)


@app.route("/compare")
def compare():
    ids_raw = request.args.getlist("id")
    try:
        ids = [int(i) for i in ids_raw if i][:3]
    except ValueError:
        ids = []
    authorities_data = []
    for aid in ids:
        auth = query_one("SELECT * FROM authority WHERE id=?", (aid,))
        if auth:
            recs = {r["year"]: r for r in query(
                "SELECT * FROM council_tax_record WHERE authority_id=?", (aid,))}
            authorities_data.append({"auth": auth, "records": recs})
    all_auths = query("SELECT id, name FROM authority ORDER BY name")
    return render_template("compare.html", authorities=authorities_data, years=YEARS,
                           all_auths=all_auths, ids=ids,
                           region_labels=REGION_LABELS, class_labels=CLASS_LABELS)


@app.route("/regions")
def regions():
    year = request.args.get("year", "2026-27")
    if year not in YEARS:
        year = "2026-27"
    rows = query(
        """SELECT a.region_code, COUNT(*) AS total_las,
                  AVG(r.band_d_area) AS avg_area_band_d,
                  MIN(r.band_d_area) AS min_area_band_d,
                  MAX(r.band_d_area) AS max_area_band_d,
                  AVG(r.pct_change)  AS avg_pct_change,
                  SUM(r.taxbase)     AS total_taxbase
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE r.year=? AND a.region_code NOT IN ('[z]','Eng')
           GROUP BY a.region_code ORDER BY avg_area_band_d DESC""", (year,))
    return render_template("regions.html", rows=rows, year=year, years=YEARS,
                           region_labels=REGION_LABELS)


@app.route("/region/<code>")
def region_detail(code):
    if code not in REGION_LABELS:
        abort(404)
    year = request.args.get("year", "2026-27")
    if year not in YEARS:
        year = "2026-27"
    las = query(
        """SELECT a.id, a.name, a.class_code, r.band_d_billing, r.band_d_area,
                  r.pct_change, r.taxbase, r.ct_requirement
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE a.region_code=? AND r.year=? ORDER BY r.band_d_area DESC""",
        (code, year))
    summary = query_one(
        """SELECT AVG(r.band_d_area) AS avg_area, AVG(r.pct_change) AS avg_change,
                  COUNT(*) AS total
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE a.region_code=? AND r.year=?""", (code, year))
    trend = query(
        """SELECT r.year, AVG(r.band_d_area) AS avg_area
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE a.region_code=? GROUP BY r.year ORDER BY r.year""", (code,))
    return render_template("region_detail.html", code=code,
                           region_name=REGION_LABELS[code], las=las,
                           summary=summary, trend=trend, year=year, years=YEARS,
                           class_labels=CLASS_LABELS)


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500,
                           message="An internal server error occurred."), 500


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400,
                           message="Bad request. Please check your input."), 400


if __name__ == "__main__":
    app.run(debug=True)
