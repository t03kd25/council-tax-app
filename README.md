# Council Tax Explorer

A Flask web application that lets users explore, compare, and analyse council tax data for all 296 billing authorities in England across the 2025-26 and 2026-27 financial years.

**Render URL:** `https://council-tax-explorer.onrender.com` *(update after deployment)*

---

## Data source

Open Government Licence data published by the Ministry of Housing, Communities and Local Government (MHCLG):
- *Council Tax levels: Local Authority Level data for 2025-26* (Table 10, revised April 2026)
- *Council Tax levels: Local Authority Level data for 2026-27* (Table 10, March 2026)

Available at: <https://www.gov.uk/government/collections/council-tax-statistics>

The two ODS workbooks provide **592 council tax records** (296 authorities × 2 years) covering Band D billing amounts, area Band D (including major precepts), taxbase, CT requirements, parish precepts, adult social care precept, and year-on-year percentage change.

---

## Features

| Page | Description |
|------|-------------|
| **Home** | National summary statistics, league tables for highest/lowest area Band D and biggest % rises |
| **Authorities** | Paginated, filterable, sortable list of all 296 billing authorities |
| **Authority detail** | Per-authority KPIs for both years, comparison vs regional and class averages, national rank, similar authorities |
| **Regions** | Overview cards for all 9 English regions with average Band D and range |
| **Region detail** | All authorities in a region sorted by Band D, with summary statistics |
| **Compare** | Side-by-side comparison of up to 3 authorities across both years |
| **Search** | Full-text name search across all authorities |

---

## Database schema

```
region (code PK, name)
authority_class (code PK, name)
authority (id PK, ecode UNIQUE, ons_code, name, region_code FK, class_code FK)
council_tax_record (id PK, authority_id FK, year, ct_requirement, parish_precept,
                    taxbase, collection_rate, band_d_billing, band_d_area,
                    asc_precept, band_d_prev, pct_change)
```

Two linked tables (`authority` → `council_tax_record`) satisfy the requirement for at least two linked tables.

---

## Installation and running locally

**Requirements:** Python 3.10+, pip

```bash
# 1. Clone the repository
git clone https://github.com/your-username/council-tax-explorer.git
cd council-tax-explorer

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Place the ODS data files in the data/ folder:
#    data/Table_10_2025-26.ods
#    data/Table_10_2026-27.ods

# 5. Seed the database
python3 seed_db.py

# 6. Run the development server
python3 app.py
```

Open <http://127.0.0.1:5000> in your browser.

---

## Running tests

The test suite uses Python's standard `unittest` library — no additional packages needed.

```bash
python3 -m unittest tests.test_app -v
```

34 tests cover: all route responses (200/404/302), filter/search/sort behaviour, compare page, error handlers, and database integrity.

---

## Deploying to Render

1. Push the repository to GitHub.
2. Create a new **Web Service** on [render.com](https://render.com).
3. Set:
   - **Build command:** `pip install -r requirements.txt && python seed_db.py`
   - **Start command:** `gunicorn app:app`
   - **Environment variable:** `SECRET_KEY` → a long random string
4. Upload the ODS data files to the `data/` directory (or add them to the repo).
5. Deploy — Render will build, seed the database, and serve the app.

> **Note:** Render's free tier uses an ephemeral filesystem; the SQLite database will be regenerated on each deploy. For persistence, use Render's managed PostgreSQL or store the `.db` file in a persistent disk.

---

## Maintenance

- **Updating data:** Replace the `.ods` files in `data/` and re-run `python3 seed_db.py`. The database is rebuilt from scratch each time.
- **Adding a new year:** Extend `seed_db.py` with a third `load_billing()` call and add the corresponding ODS file.
- **Styling:** Edit `static/css/style.css`.
- **Adding routes:** Add view functions to `app.py` and corresponding templates in `templates/`.

---

## Project structure

```
council_tax_app/
├── app.py              # Flask application and routes
├── seed_db.py          # Database seeding from ODS files
├── requirements.txt
├── council_tax.db      # SQLite database (generated, not committed)
├── data/
│   ├── Table_10_2025-26.ods
│   └── Table_10_2026-27.ods
├── static/
│   └── css/style.css
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── authority_list.html
│   ├── authority_detail.html
│   ├── regions.html
│   ├── region_detail.html
│   ├── compare.html
│   ├── search.html
│   └── errors/
│       ├── 400.html
│       ├── 404.html
│       └── 500.html
└── tests/
    └── test_app.py
```
