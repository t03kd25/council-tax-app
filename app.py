"""Council Tax Explorer – Flask application entry point."""
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, abort, g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "council_tax.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")


# ── Database helpers ──────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv


# ── Context processor – pass lookup tables to every template ──────────────────

@app.context_processor
def inject_globals():
    regions = query("SELECT code, name FROM region WHERE code != '[z]' ORDER BY name")
    classes = query("SELECT code, name FROM authority_class ORDER BY name")
    return dict(nav_regions=regions, nav_classes=classes)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Homepage: national summary stats for both years."""
    stats = {}
    for year in ("2025-26", "2026-27"):
        row = query(
            """SELECT
                COUNT(DISTINCT a.id)            AS total_authorities,
                AVG(r.band_d_area)              AS avg_band_d_area,
                AVG(r.band_d_billing)           AS avg_band_d_billing,
                AVG(r.pct_change)               AS avg_pct_change,
                MIN(r.band_d_area)              AS min_band_d,
                MAX(r.band_d_area)              AS max_band_d,
                SUM(r.ct_requirement)           AS total_ct_requirement
            FROM council_tax_record r
            JOIN authority a ON a.id = r.authority_id
            WHERE r.year = ?""",
            (year,), one=True
        )
        stats[year] = row

    # Top 5 highest / lowest band-D areas in 2026-27
    highest = query(
        """SELECT a.name, a.region_code, r.band_d_area, r.pct_change
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE r.year='2026-27' AND r.band_d_area IS NOT NULL
           ORDER BY r.band_d_area DESC LIMIT 5"""
    )
    lowest = query(
        """SELECT a.name, a.region_code, r.band_d_area, r.pct_change
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE r.year='2026-27' AND r.band_d_area IS NOT NULL
           ORDER BY r.band_d_area ASC LIMIT 5"""
    )
    biggest_rises = query(
        """SELECT a.name, a.region_code, r.band_d_billing, r.pct_change
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE r.year='2026-27' AND r.pct_change IS NOT NULL
           ORDER BY r.pct_change DESC LIMIT 5"""
    )
    return render_template(
        "index.html",
        stats=stats,
        highest=highest,
        lowest=lowest,
        biggest_rises=biggest_rises,
    )


@app.route("/authorities")
def authority_list():
    """Paginated, filterable list of all billing authorities."""
    page      = max(1, request.args.get("page", 1, type=int))
    per_page  = 25
    year      = request.args.get("year", "2026-27")
    region    = request.args.get("region", "")
    cls       = request.args.get("class", "")
    search    = request.args.get("q", "").strip()
    sort      = request.args.get("sort", "name")

    allowed_sorts = {
        "name": "a.name",
        "band_d":  "r.band_d_billing",
        "area_d":  "r.band_d_area",
        "change":  "r.pct_change",
        "taxbase": "r.taxbase",
    }
    order_col = allowed_sorts.get(sort, "a.name")

    where = ["r.year = ?"]
    params = [year]
    if region:
        where.append("a.region_code = ?")
        params.append(region)
    if cls:
        where.append("a.class_code = ?")
        params.append(cls)
    if search:
        where.append("a.name LIKE ?")
        params.append(f"%{search}%")

    where_sql = " AND ".join(where)

    total_row = query(
        f"""SELECT COUNT(*) AS n
            FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
            WHERE {where_sql}""",
        params, one=True
    )
    total = total_row["n"] if total_row else 0
    pages = max(1, (total + per_page - 1) // per_page)
    page  = min(page, pages)
    offset = (page - 1) * per_page

    authorities = query(
        f"""SELECT a.id, a.name, a.region_code, a.class_code,
                   r.band_d_billing, r.band_d_area, r.pct_change,
                   r.taxbase, r.ct_requirement
            FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
            WHERE {where_sql}
            ORDER BY {order_col}
            LIMIT ? OFFSET ?""",
        params + [per_page, offset]
    )

    return render_template(
        "authority_list.html",
        authorities=authorities,
        page=page, pages=pages, total=total,
        year=year, region=region, cls=cls, search=search, sort=sort,
    )


@app.route("/authority/<int:auth_id>")
def authority_detail(auth_id):
    """Detail page for a single billing authority."""
    authority = query(
        """SELECT a.*, rc.name AS class_name, rg.name AS region_name
           FROM authority a
           JOIN authority_class rc ON rc.code = a.class_code
           JOIN region rg ON rg.code = a.region_code
           WHERE a.id = ?""",
        (auth_id,), one=True
    )
    if not authority:
        abort(404)

    records = query(
        """SELECT * FROM council_tax_record WHERE authority_id = ? ORDER BY year""",
        (auth_id,)
    )
    # Regional averages for comparison
    region_avgs = {}
    for year in ("2025-26", "2026-27"):
        row = query(
            """SELECT AVG(r.band_d_billing) AS avg_billing, AVG(r.band_d_area) AS avg_area,
                      AVG(r.pct_change) AS avg_change, COUNT(*) AS n
               FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
               WHERE r.year=? AND a.region_code=?""",
            (year, authority["region_code"]), one=True
        )
        region_avgs[year] = row

    # Class averages
    class_avgs = {}
    for year in ("2025-26", "2026-27"):
        row = query(
            """SELECT AVG(r.band_d_billing) AS avg_billing, AVG(r.band_d_area) AS avg_area,
                      AVG(r.pct_change) AS avg_change, COUNT(*) AS n
               FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
               WHERE r.year=? AND a.class_code=?""",
            (year, authority["class_code"]), one=True
        )
        class_avgs[year] = row

    # National rank for 2026-27 band_d_area
    rank_row = query(
        """SELECT COUNT(*) + 1 AS rank FROM council_tax_record r2
           JOIN authority a2 ON a2.id=r2.authority_id
           WHERE r2.year='2026-27'
             AND r2.band_d_area > (
               SELECT band_d_area FROM council_tax_record r3
               WHERE r3.authority_id=? AND r3.year='2026-27'
             )""",
        (auth_id,), one=True
    )
    national_rank = rank_row["rank"] if rank_row else None

    # Similar authorities (same class, nearby band_d)
    this_band_d = None
    for rec in records:
        if rec["year"] == "2026-27":
            this_band_d = rec["band_d_billing"]

    similar = []
    if this_band_d:
        similar = query(
            """SELECT a.id, a.name, r.band_d_billing, r.pct_change
               FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
               WHERE r.year='2026-27' AND a.class_code=? AND a.id != ?
                 AND r.band_d_billing IS NOT NULL
               ORDER BY ABS(r.band_d_billing - ?) ASC LIMIT 5""",
            (authority["class_code"], auth_id, this_band_d)
        )

    return render_template(
        "authority_detail.html",
        authority=authority,
        records={r["year"]: r for r in records},
        region_avgs=region_avgs,
        class_avgs=class_avgs,
        national_rank=national_rank,
        similar=similar,
    )


@app.route("/compare")
def compare():
    """Side-by-side comparison of up to 3 authorities."""
    ids_raw = request.args.getlist("id")
    try:
        ids = [int(i) for i in ids_raw if i][:3]
    except ValueError:
        abort(400)

    authorities = []
    for aid in ids:
        auth = query(
            """SELECT a.*, rc.name AS class_name, rg.name AS region_name
               FROM authority a
               JOIN authority_class rc ON rc.code=a.class_code
               JOIN region rg ON rg.code=a.region_code
               WHERE a.id=?""",
            (aid,), one=True
        )
        if auth:
            records = query(
                "SELECT * FROM council_tax_record WHERE authority_id=? ORDER BY year",
                (aid,)
            )
            authorities.append({"auth": auth, "records": {r["year"]: r for r in records}})

    # Search suggestions
    q = request.args.get("q", "").strip()
    suggestions = []
    if q:
        suggestions = query(
            "SELECT id, name, region_code, class_code FROM authority WHERE name LIKE ? ORDER BY name LIMIT 10",
            (f"%{q}%",)
        )

    return render_template(
        "compare.html",
        authorities=authorities,
        selected_ids=ids,
        q=q,
        suggestions=suggestions,
    )


@app.route("/regions")
def regions():
    """Regional overview page."""
    year = request.args.get("year", "2026-27")
    data = query(
        """SELECT rg.code, rg.name,
                  COUNT(DISTINCT a.id)    AS authority_count,
                  AVG(r.band_d_billing)   AS avg_billing,
                  AVG(r.band_d_area)      AS avg_area,
                  AVG(r.pct_change)       AS avg_change,
                  MIN(r.band_d_billing)   AS min_billing,
                  MAX(r.band_d_billing)   AS max_billing
           FROM region rg
           JOIN authority a  ON a.region_code=rg.code
           JOIN council_tax_record r ON r.authority_id=a.id
           WHERE r.year=? AND rg.code != '[z]'
           GROUP BY rg.code, rg.name
           ORDER BY avg_area DESC""",
        (year,)
    )
    return render_template("regions.html", regions=data, year=year)


@app.route("/region/<region_code>")
def region_detail(region_code):
    """All authorities in a region."""
    year = request.args.get("year", "2026-27")
    region = query("SELECT * FROM region WHERE code=?", (region_code,), one=True)
    if not region:
        abort(404)

    authorities = query(
        """SELECT a.id, a.name, a.class_code,
                  r.band_d_billing, r.band_d_area, r.pct_change, r.taxbase
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE r.year=? AND a.region_code=?
           ORDER BY r.band_d_billing DESC""",
        (year, region_code)
    )

    summary = query(
        """SELECT AVG(r.band_d_billing) AS avg_billing, AVG(r.band_d_area) AS avg_area,
                  AVG(r.pct_change) AS avg_change, MIN(r.band_d_billing) AS min_b,
                  MAX(r.band_d_billing) AS max_b, COUNT(*) AS n
           FROM council_tax_record r JOIN authority a ON a.id=r.authority_id
           WHERE r.year=? AND a.region_code=?""",
        (year, region_code), one=True
    )

    return render_template(
        "region_detail.html",
        region=region, authorities=authorities, summary=summary, year=year
    )


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("authority_list"))
    results = query(
        """SELECT a.id, a.name, a.region_code, a.class_code,
                  r.band_d_billing, r.band_d_area, r.pct_change
           FROM authority a
           JOIN council_tax_record r ON r.authority_id=a.id
           WHERE a.name LIKE ? AND r.year='2026-27'
           ORDER BY a.name LIMIT 50""",
        (f"%{q}%",)
    )
    return render_template("search.html", results=results, q=q)


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template("errors/400.html"), 400


@app.errorhandler(500)
def server_error(e):
    return render_template("errors/500.html"), 500


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("Database not found – run seed_db.py first.")
    else:
        app.run(debug=True)
