"""
Tests for the Council Tax Explorer Flask application.
Run with: python3 -m unittest discover tests/
"""
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
    def test_loads(self):
        self.assertEqual(self.get("/").status_code, 200)

    def test_contains_heading(self):
        self.assertIn(b"Council Tax", self.get("/").data)

    def test_default_year_is_2026_27(self):
        self.assertIn(b"2026-27", self.get("/").data)

    def test_year_switch_2025_26(self):
        rv = self.get("/?year=2025-26")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"2025-26", rv.data)

    def test_invalid_year_defaults(self):
        rv = self.get("/?year=1900-01")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"2026-27", rv.data)

    def test_stats_block_present(self):
        self.assertIn(b"stat-card", self.get("/").data)

    def test_highest_table_present(self):
        self.assertIn(b"Highest", self.get("/").data)

    def test_lowest_table_present(self):
        self.assertIn(b"Lowest", self.get("/").data)


class TestAuthorities(BaseTestCase):
    def test_list_loads(self):
        self.assertEqual(self.get("/authorities").status_code, 200)

    def test_search_birmingham(self):
        rv = self.get("/authorities?q=Birmingham")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"Birmingham", rv.data)

    def test_region_filter_london(self):
        rv = self.get("/authorities?region=L")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"London", rv.data)

    def test_class_filter_md(self):
        rv = self.get("/authorities?cls=MD")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"Metropolitan", rv.data)

    def test_sort_band_d_desc(self):
        self.assertEqual(self.get("/authorities?sort=band_d_desc").status_code, 200)

    def test_sort_band_d_asc(self):
        self.assertEqual(self.get("/authorities?sort=band_d_asc").status_code, 200)

    def test_sort_change_desc(self):
        self.assertEqual(self.get("/authorities?sort=change_desc").status_code, 200)

    def test_pagination_page2(self):
        self.assertEqual(self.get("/authorities?page=2").status_code, 200)

    def test_no_results_search(self):
        rv = self.get("/authorities?q=ZZZNOMATCH999")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"No authorities", rv.data)

    def test_year_2025_26(self):
        self.assertEqual(self.get("/authorities?year=2025-26").status_code, 200)

    def test_combined_filters(self):
        rv = self.get("/authorities?region=SE&cls=SD&sort=band_d_desc")
        self.assertEqual(rv.status_code, 200)


class TestAuthorityDetail(BaseTestCase):
    def test_valid_authority_1(self):
        self.assertEqual(self.get("/authority/1").status_code, 200)

    def test_valid_authority_10(self):
        self.assertEqual(self.get("/authority/10").status_code, 200)

    def test_cross_year_data_present(self):
        rv = self.get("/authority/1")
        self.assertIn(b"2025-26", rv.data)
        self.assertIn(b"2026-27", rv.data)

    def test_peers_section_present(self):
        rv = self.get("/authority/1")
        self.assertIn(b"Peers", rv.data)

    def test_invalid_id_returns_404(self):
        self.assertEqual(self.get("/authority/99999").status_code, 404)

    def test_zero_id_returns_404(self):
        self.assertEqual(self.get("/authority/0").status_code, 404)


class TestRegions(BaseTestCase):
    def test_regions_page_loads(self):
        self.assertEqual(self.get("/regions").status_code, 200)

    def test_south_east_listed(self):
        self.assertIn(b"South East", self.get("/regions").data)

    def test_north_west_listed(self):
        self.assertIn(b"North West", self.get("/regions").data)

    def test_year_switch(self):
        self.assertEqual(self.get("/regions?year=2025-26").status_code, 200)

    def test_region_se_detail(self):
        rv = self.get("/region/SE")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"South East", rv.data)

    def test_region_nw_detail(self):
        self.assertEqual(self.get("/region/NW").status_code, 200)

    def test_region_l_detail(self):
        rv = self.get("/region/L")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"London", rv.data)

    def test_region_invalid_404(self):
        self.assertEqual(self.get("/region/ZZ").status_code, 404)

    def test_region_year_param(self):
        self.assertEqual(self.get("/region/SE?year=2025-26").status_code, 200)


class TestCompare(BaseTestCase):
    def test_empty_compare(self):
        self.assertEqual(self.get("/compare").status_code, 200)

    def test_compare_one_authority(self):
        self.assertEqual(self.get("/compare?id=1").status_code, 200)

    def test_compare_two_authorities(self):
        self.assertEqual(self.get("/compare?id=1&id=2").status_code, 200)

    def test_compare_three_authorities(self):
        self.assertEqual(self.get("/compare?id=1&id=2&id=3").status_code, 200)

    def test_compare_capped_at_three(self):
        rv = self.get("/compare?id=1&id=2&id=3&id=4")
        self.assertEqual(rv.status_code, 200)

    def test_compare_invalid_id_graceful(self):
        self.assertEqual(self.get("/compare?id=99999").status_code, 200)


class TestErrors(BaseTestCase):
    def test_nonexistent_route_404(self):
        self.assertEqual(self.get("/nonexistent-xyz-route").status_code, 404)

    def test_404_page_has_home_link(self):
        rv = self.get("/nonexistent-xyz")
        self.assertIn(b"Home", rv.data)

    def test_404_page_shows_error_code(self):
        rv = self.get("/nonexistent-xyz")
        self.assertIn(b"404", rv.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
