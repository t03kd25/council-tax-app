"""Tests for the Council Tax Explorer Flask application (extended dataset)."""
import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import app as flask_app

class BaseTestCase(unittest.TestCase):
    def setUp(self):
        flask_app.config["TESTING"] = True
        self.client = flask_app.test_client()
    def get(self, url):
        return self.client.get(url)

class TestIndex(BaseTestCase):
    def test_loads(self):                    self.assertEqual(self.get("/").status_code, 200)
    def test_contains_heading(self):         self.assertIn(b"Council Tax", self.get("/").data)
    def test_default_year(self):             self.assertIn(b"2026-27", self.get("/").data)
    def test_year_switch(self):              self.assertEqual(self.get("/?year=2025-26").status_code, 200)
    def test_invalid_year_defaults(self):    self.assertIn(b"2026-27", self.get("/?year=1900-01").data)
    def test_stats_block(self):              self.assertIn(b"stat-card", self.get("/").data)
    def test_highest_table(self):            self.assertIn(b"Highest", self.get("/").data)
    def test_trend_section(self):            self.assertIn(b"trend", self.get("/").data.lower())

class TestAuthorities(BaseTestCase):
    def test_list_loads(self):               self.assertEqual(self.get("/authorities").status_code, 200)
    def test_search_birmingham(self):
        rv = self.get("/authorities?q=Birmingham")
        self.assertEqual(rv.status_code, 200); self.assertIn(b"Birmingham", rv.data)
    def test_region_filter(self):            self.assertEqual(self.get("/authorities?region=L").status_code, 200)
    def test_class_filter(self):             self.assertEqual(self.get("/authorities?cls=MD").status_code, 200)
    def test_sort_band_d_desc(self):         self.assertEqual(self.get("/authorities?sort=band_d_desc").status_code, 200)
    def test_sort_band_d_asc(self):          self.assertEqual(self.get("/authorities?sort=band_d_asc").status_code, 200)
    def test_sort_change_desc(self):         self.assertEqual(self.get("/authorities?sort=change_desc").status_code, 200)
    def test_page2(self):                    self.assertEqual(self.get("/authorities?page=2").status_code, 200)
    def test_no_results(self):
        rv = self.get("/authorities?q=ZZZNOMATCH999")
        self.assertIn(b"No authorities", rv.data)
    def test_year_2025_26(self):             self.assertEqual(self.get("/authorities?year=2025-26").status_code, 200)
    def test_combined_filters(self):         self.assertEqual(self.get("/authorities?region=SE&cls=SD").status_code, 200)

class TestAuthorityDetail(BaseTestCase):
    def test_valid_1(self):                  self.assertEqual(self.get("/authority/1").status_code, 200)
    def test_valid_10(self):                 self.assertEqual(self.get("/authority/10").status_code, 200)
    def test_two_years_shown(self):
        rv = self.get("/authority/1")
        self.assertIn(b"2025-26", rv.data); self.assertIn(b"2026-27", rv.data)
    def test_band_section_shown(self):       self.assertIn(b"Band", self.get("/authority/1").data)
    def test_peers_shown(self):              self.assertIn(b"Peers", self.get("/authority/1").data)
    def test_invalid_404(self):              self.assertEqual(self.get("/authority/99999").status_code, 404)
    def test_zero_404(self):                 self.assertEqual(self.get("/authority/0").status_code, 404)

class TestPrecepting(BaseTestCase):
    def test_list_loads(self):               self.assertEqual(self.get("/precepting").status_code, 200)
    def test_year_switch(self):              self.assertEqual(self.get("/precepting?year=2025-26").status_code, 200)
    def test_filter_police(self):
        rv = self.get("/precepting?ptype=Police+and+Crime+Commissioner")
        self.assertEqual(rv.status_code, 200)
    def test_filter_fire(self):              self.assertEqual(self.get("/precepting?ptype=Fire+and+Rescue+Authority").status_code, 200)
    def test_filter_county(self):            self.assertEqual(self.get("/precepting?ptype=Shire+County").status_code, 200)
    def test_sort_band_d_desc(self):         self.assertEqual(self.get("/precepting?sort=band_d_desc").status_code, 200)
    def test_search(self):                   self.assertEqual(self.get("/precepting?q=Kent").status_code, 200)
    def test_no_results(self):
        rv = self.get("/precepting?q=ZZZNOMATCH")
        self.assertIn(b"No precepting", rv.data)

class TestRegions(BaseTestCase):
    def test_loads(self):                    self.assertEqual(self.get("/regions").status_code, 200)
    def test_south_east(self):               self.assertIn(b"South East", self.get("/regions").data)
    def test_north_west(self):               self.assertIn(b"North West", self.get("/regions").data)
    def test_year_switch(self):              self.assertEqual(self.get("/regions?year=2025-26").status_code, 200)
    def test_region_se(self):
        rv = self.get("/region/SE")
        self.assertEqual(rv.status_code, 200); self.assertIn(b"South East", rv.data)
    def test_region_nw(self):                self.assertEqual(self.get("/region/NW").status_code, 200)
    def test_region_l(self):                 self.assertIn(b"London", self.get("/region/L").data)
    def test_region_invalid_404(self):       self.assertEqual(self.get("/region/ZZ").status_code, 404)
    def test_region_year_param(self):        self.assertEqual(self.get("/region/SE?year=2025-26").status_code, 200)

class TestTrend(BaseTestCase):
    def test_loads(self):                    self.assertEqual(self.get("/trend").status_code, 200)
    def test_table3_present(self):           self.assertIn(b"Table 3", self.get("/trend").data)
    def test_table7_present(self):           self.assertIn(b"Table 7", self.get("/trend").data)
    def test_historical_years(self):         self.assertIn(b"2011", self.get("/trend").data)
    def test_2026_27_present(self):          self.assertIn(b"2026", self.get("/trend").data)

class TestCompare(BaseTestCase):
    def test_empty(self):                    self.assertEqual(self.get("/compare").status_code, 200)
    def test_one_authority(self):            self.assertEqual(self.get("/compare?id=1").status_code, 200)
    def test_two_authorities(self):          self.assertEqual(self.get("/compare?id=1&id=2").status_code, 200)
    def test_three_authorities(self):        self.assertEqual(self.get("/compare?id=1&id=2&id=3").status_code, 200)
    def test_capped_at_three(self):          self.assertEqual(self.get("/compare?id=1&id=2&id=3&id=4").status_code, 200)
    def test_invalid_id_graceful(self):      self.assertEqual(self.get("/compare?id=99999").status_code, 200)

class TestErrors(BaseTestCase):
    def test_404(self):                      self.assertEqual(self.get("/nonexistent-xyz").status_code, 404)
    def test_404_has_home_link(self):        self.assertIn(b"Home", self.get("/nonexistent-xyz").data)
    def test_404_shows_code(self):           self.assertIn(b"404", self.get("/nonexistent-xyz").data)

if __name__ == "__main__":
    unittest.main(verbosity=2)
