# Council Tax Explorer

A Flask web application for exploring England council tax rates using official MHCLG open data for 2025-26 and 2026-27.

## Data Source

Ministry of Housing, Communities and Local Government (MHCLG) — *Local Authority Council Tax levels in England*, published under the Open Government Licence v3.0.  
https://www.gov.uk/government/collections/council-tax-statistics

Coverage: **296 local authorities**, **592 council tax records** (two financial years).

## Features

- **Homepage** — headline stats (avg/min/max Area Band D, totals), top-5 highest/lowest area Band D, biggest billing Band D rises; switchable by year
- **Authorities list** — paginated table (25 per page) with search, region filter, authority-class filter, year selector, and 5 sort modes
- **Authority detail** — cross-year comparison table, peer comparison within same class+region, rank within class
- **Regions** — summary table for all 9 English regions with avg/min/max and trend data
- **Region detail** — all LAs in a region with year selector and trend stats
- **Compare** — side-by-side comparison of up to 3 authorities across both years

## Database Design

Two linked tables (satisfies ≥2 linked tables requirement):

```
region (code PK, name)
authority_class (code PK, name)
authority (id PK, ecode, ons_code, name, region_code FK, class_code FK)
council_tax_record (id PK, authority_id FK, year, band_d_billing, band_d_area,
                    ct_requirement, parish_precept, taxbase, collection_rate,
                    asc_precept, band_d_prev, pct_change)
```

## Installation

```bash
git clone <repo-url>
cd council_tax_app
pip install -r requirements.txt
python3 seed_db.py        # seeds council_tax.db from ODS files in data/
python3 app.py            # development server at http://127.0.0.1:5000
```

## Testing

```bash
python3 -m unittest discover tests/ -v
```

43 tests covering all routes, filters, pagination, error handling, and cross-year data.

## Render Deployment

1. Push repository to GitHub.
2. Create a new **Web Service** on [Render](https://render.com).
3. Set **Build Command**: `pip install -r requirements.txt && python3 seed_db.py`
4. Set **Start Command**: `gunicorn app:app`
5. The app uses SQLite (file-based); on Render's free tier, use a persistent disk or switch to PostgreSQL for production.

Render URL: *https://council-tax-explorer.onrender.com* (example — update after deployment)

## Maintenance

- To update data: replace ODS files in `data/` and rerun `python3 seed_db.py`.
- The `seed_db.py` script drops and recreates `council_tax.db` on each run.
- No user accounts or sessions — stateless beyond the SQLite database.
- All queries use parameterised SQL to prevent injection.
