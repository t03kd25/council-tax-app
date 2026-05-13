"""Tests for the Council Tax Explorer Flask application.
Uses stdlib unittest only (no pytest dependency needed).
"""
import os, sys, unittest, sqlite3, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import app as application
from seed_db import create_tables, REGION_NAMES, CLASS_NAMES


def _build_test_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    for code, name in REGION_NAMES.items():
        conn.execute("INSERT OR IGNORE INTO region VALUES (?,?)", (code, name))
    for code, name in CLASS_NAMES.items():
        conn.execute("INSERT OR IGNORE INTO authority_class VALUES (?,?)", (code, name))
    conn.execute("INSERT INTO authority (ecode,ons_code,name,region_code,class_code) VALUES (?,?,?,?,?)",
                 ("E9999","E07000999","Test District","SE","SD"))
    auth_id = conn.execute("SELECT id FROM authority WHERE ecode='E9999'").fetchone()[0]
    for year, bd, area, pct in [("2025-26",350.0,2200.0,4.5),("2026-27",370.0,2350.0,5.7)]:
        conn.execute("""INSERT INTO council_tax_record
            (authority_id,year,ct_requirement,parish_precept,taxbase,collection_rate,
             band_d_billing,band_d_area,asc_precept,band_d_prev,pct_change)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (auth_id,year,5000000,100000,15000,0.98,bd,area,40.0,bd-15,pct))
    conn.commit(); conn.close()
    return auth_id


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_file = os.path.join(self.tmp,"test.db")
        self.auth_id = _build_test_db(self.db_file)
        application.app.config["TESTING"] = True
        application.DB_PATH = self.db_file
        self.client = application.app.test_client()
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def get(self,url): return self.client.get(url)


class TestHomepage(Base):
    def test_200(self): self.assertEqual(self.get("/").status_code, 200)
    def test_title(self): self.assertIn(b"Council Tax Explorer", self.get("/").data)
    def test_both_years(self):
        d = self.get("/").data
        self.assertIn(b"2025-26",d); self.assertIn(b"2026-27",d)

class TestAuthorityList(Base):
    def test_200(self): self.assertEqual(self.get("/authorities").status_code, 200)
    def test_shows_authority(self): self.assertIn(b"Test District", self.get("/authorities").data)
    def test_region_filter_match(self):
        r = self.get("/authorities?region=SE")
        self.assertEqual(r.status_code,200); self.assertIn(b"Test District",r.data)
    def test_region_filter_no_match(self):
        self.assertNotIn(b"Test District", self.get("/authorities?region=NW").data)
    def test_search(self): self.assertIn(b"Test District", self.get("/authorities?q=Test").data)
    def test_year(self): self.assertEqual(self.get("/authorities?year=2025-26").status_code, 200)
    def test_sort(self): self.assertEqual(self.get("/authorities?sort=band_d").status_code, 200)
    def test_page(self): self.assertEqual(self.get("/authorities?page=1").status_code, 200)

class TestAuthorityDetail(Base):
    def test_200(self): self.assertEqual(self.get(f"/authority/{self.auth_id}").status_code, 200)
    def test_name(self): self.assertIn(b"Test District", self.get(f"/authority/{self.auth_id}").data)
    def test_years(self):
        d = self.get(f"/authority/{self.auth_id}").data
        self.assertIn(b"2025-26",d); self.assertIn(b"2026-27",d)
    def test_band_d(self): self.assertIn(b"370", self.get(f"/authority/{self.auth_id}").data)
    def test_404(self): self.assertEqual(self.get("/authority/99999").status_code, 404)

class TestRegions(Base):
    def test_list_200(self): self.assertEqual(self.get("/regions").status_code, 200)
    def test_south_east(self): self.assertIn(b"South East", self.get("/regions").data)
    def test_detail_200(self): self.assertEqual(self.get("/region/SE").status_code, 200)
    def test_detail_authority(self): self.assertIn(b"Test District", self.get("/region/SE").data)
    def test_detail_404(self): self.assertEqual(self.get("/region/ZZZZ").status_code, 404)

class TestSearch(Base):
    def test_redirect_empty(self): self.assertEqual(self.get("/search").status_code, 302)
    def test_finds(self): self.assertIn(b"Test District", self.get("/search?q=Test").data)
    def test_no_results(self):
        r = self.get("/search?q=XYZDoesNotExist")
        self.assertEqual(r.status_code,200); self.assertNotIn(b"Test District",r.data)

class TestCompare(Base):
    def test_empty_200(self): self.assertEqual(self.get("/compare").status_code, 200)
    def test_with_authority(self):
        r = self.get(f"/compare?id={self.auth_id}")
        self.assertEqual(r.status_code,200); self.assertIn(b"Test District",r.data)
    def test_suggestions(self): self.assertIn(b"Test District", self.get("/compare?q=Test").data)

class TestErrors(Base):
    def test_404(self):
        r = self.get("/this-does-not-exist")
        self.assertEqual(r.status_code,404); self.assertIn(b"404",r.data)

class TestDatabase(Base):
    def _conn(self): return sqlite3.connect(self.db_file)
    def test_two_records(self):
        c=self._conn(); n=c.execute("SELECT COUNT(*) FROM council_tax_record").fetchone()[0]; c.close()
        self.assertEqual(n,2)
    def test_authority_region(self):
        c=self._conn(); row=c.execute("SELECT region_code FROM authority WHERE id=?",(self.auth_id,)).fetchone(); c.close()
        self.assertEqual(row[0],"SE")
    def test_regions_populated(self):
        c=self._conn(); n=c.execute("SELECT COUNT(*) FROM region").fetchone()[0]; c.close()
        self.assertEqual(n,len(REGION_NAMES))
    def test_classes_populated(self):
        c=self._conn(); n=c.execute("SELECT COUNT(*) FROM authority_class").fetchone()[0]; c.close()
        self.assertEqual(n,len(CLASS_NAMES))
    def test_band_d_stored(self):
        c=self._conn(); row=c.execute("SELECT band_d_billing FROM council_tax_record WHERE year='2026-27'").fetchone(); c.close()
        self.assertAlmostEqual(row[0],370.0)
    def test_pct_change(self):
        c=self._conn(); row=c.execute("SELECT pct_change FROM council_tax_record WHERE year='2026-27'").fetchone(); c.close()
        self.assertAlmostEqual(row[0],5.7)

if __name__ == "__main__":
    unittest.main(verbosity=2)
