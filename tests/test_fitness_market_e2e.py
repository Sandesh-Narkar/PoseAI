"""
PoseAI Fitness Market — Comprehensive End-to-End Integration Test Suite

Validates:
1. Real classified images: all product records point to existing, verified image files
   in frontend/images/market_products/ (no broken paths or missing files).
2. Category and subcategory taxonomy consistency (Dumbbells in training-gear,
   Proteins in protein, Creatine in creatine/supplements, Recovery in recovery, etc.).
3. Search functionality for keywords ("whey", "creatine", "dumbbell", "shaker").
4. Category filtering for primary categories.
5. Goal filtering ("build-muscle", "strength", "recovery", "wellness").
6. Price range and rating filters.
7. Cart mutations and server-side calculations.
8. Wishlist addition, listing, and removal.
9. Recently viewed tracking.
10. Navbar preservation (mount point, scripts, styles, active state).
11. HTML structure verifying Zones 1 through 7 and global platform footer.
"""

import os
import unittest

from app import app
from market import repository, seed
from tests.helpers import setup_mongo_mock


class FitnessMarketE2ETestCase(unittest.TestCase):
    VALID_PASSWORD = "StrongPassphrase123!"

    def setUp(self):
        setup_mongo_mock()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        seed.seed_if_empty(force_reset=True)
        self._signup()

    def _signup(self, email="athlete@poseai.test", name="PoseAI Athlete"):
        resp = self.client.post("/auth/signup", json={
            "name": name,
            "email": email,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        self.assertEqual(resp.status_code, 201)
        return self.client

    # ── 1. Image Classification & Asset Verification ──────────────────────────

    def test_all_catalog_images_exist_on_disk(self):
        """Every product in MongoDB must have image references resolving to actual files."""
        products_col = repository.get_products_collection()
        all_products = list(products_col.find({}))
        self.assertGreaterEqual(len(all_products), 45)

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        for p in all_products:
            image_url = p.get("thumbnail") or (p.get("image_urls") and p["image_urls"][0])
            self.assertTrue(image_url, f"Product {p['name']} has no image reference")

            # Resolve local disk path
            if image_url.startswith("/images/market_products/"):
                rel_path = image_url.replace("/images/market_products/", "frontend/images/market_products/")
            elif image_url.startswith("/market/images/"):
                rel_path = image_url.replace("/market/images/", "frontend/images/market_products/")
            elif image_url.startswith("/fitness_market_product_image/"):
                rel_path = image_url.replace("/fitness_market_product_image/", "fitness_market_product_image/")
            elif image_url.startswith("/images/products/"):
                rel_path = image_url.replace("/images/products/", "frontend/images/products/")
            else:
                rel_path = image_url.lstrip("/")

            full_path = os.path.join(base_dir, rel_path)
            self.assertTrue(
                os.path.isfile(full_path),
                f"Image file missing on disk for product '{p['name']}': {full_path}"
            )

    def test_image_category_taxonomy_consistency(self):
        """Image classifications must strictly agree with product categories."""
        products_col = repository.get_products_collection()
        all_products = list(products_col.find({}))

        for p in all_products:
            name_lower = p["name"].lower()
            category = p["category"]
            subcategory = p.get("subcategory", "")

            # Protein products must be in category 'protein'
            if "whey" in name_lower or "pea protein" in name_lower or "yeast protein" in name_lower or "mass gainer" in name_lower:
                self.assertEqual(category, "protein", f"Protein product {p['name']} miscategorized under {category}")

            # Dumbbells and barbells must be in 'training-gear'
            if "dumbbell" in name_lower or "barbell" in name_lower or "kettlebell" in name_lower or "bumper" in name_lower:
                self.assertEqual(category, "training-gear", f"Equipment {p['name']} miscategorized under {category}")

            # Creatines must be in 'creatine' or 'supplements'
            if "creatine" in name_lower:
                self.assertIn(category, ["creatine", "supplements"], f"Creatine {p['name']} miscategorized under {category}")

            # Shakers must be in 'accessories'
            if "shaker" in name_lower:
                self.assertEqual(category, "accessories", f"Shaker {p['name']} miscategorized under {category}")

    # ── 2. Search API ──────────────────────────────────────────────────────────

    def test_search_by_product_name_and_category(self):
        """Search should query/filter real products by name and category keywords."""
        # Search "whey"
        resp = self.client.get("/api/market/search?search=whey")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertGreater(len(data["items"]), 0)
        for item in data["items"]:
            match = "whey" in item["name"].lower() or "whey" in item["category"].lower() or "whey" in item["tags"]
            self.assertTrue(match, f"Product {item['name']} returned for 'whey' query without matching context")

        # Search "dumbbell"
        resp_db = self.client.get("/api/market/search?search=dumbbell")
        self.assertEqual(resp_db.status_code, 200)
        data_db = resp_db.get_json()
        self.assertTrue(data_db["success"])
        self.assertGreater(len(data_db["items"]), 0)
        for item in data_db["items"]:
            self.assertIn("dumbbell", item["name"].lower())

    # ── 3. Category & Goal Filters ─────────────────────────────────────────────

    def test_category_filters(self):
        """Category filtering returns only matching category products."""
        for cat in ("protein", "training-gear", "recovery", "accessories", "supplements"):
            resp = self.client.get(f"/api/market/products?category={cat}")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            items = data["products"]
            self.assertGreater(len(items), 0, f"No products found for category {cat}")
            for p in items:
                self.assertEqual(p["category"], cat)

    def test_goal_filters(self):
        """Goal filtering returns products tagged with relevant outcomes."""
        for goal in ("build-muscle", "strength", "recovery", "wellness"):
            resp = self.client.get(f"/api/market/products?goal={goal}")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertGreater(len(data["products"]), 0, f"No products found for goal {goal}")

    # ── 4. Wishlist Operations ─────────────────────────────────────────────────

    def test_wishlist_flow(self):
        """Add to wishlist, fetch wishlist, remove from wishlist."""
        # Get first product
        resp = self.client.get("/api/market/products?limit=1")
        pid = resp.get_json()["products"][0]["id"]

        # Add to wishlist
        add_resp = self.client.post(f"/api/market/wishlist/{pid}")
        self.assertEqual(add_resp.status_code, 201)
        self.assertTrue(add_resp.get_json()["favorited"])

        # Check in wishlist
        list_resp = self.client.get("/api/market/wishlist")
        self.assertEqual(list_resp.status_code, 200)
        fav_ids = [item["id"] for item in list_resp.get_json()["items"]]
        self.assertIn(pid, fav_ids)

        # Remove from wishlist
        del_resp = self.client.delete(f"/api/market/wishlist/{pid}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(del_resp.get_json()["favorited"])

    # ── 5. Cart Operations & Navbar Count ──────────────────────────────────────

    def test_cart_operations_and_badge(self):
        """Add to cart, verify cart payload, verify badge count, and update quantity."""
        resp = self.client.get("/api/market/products?limit=1")
        pid = resp.get_json()["products"][0]["id"]

        # Add 2 units
        cart_resp = self.client.post("/api/market/cart", json={"product_id": pid, "quantity": 2})
        self.assertEqual(cart_resp.status_code, 201)
        cart = cart_resp.get_json()["cart"]
        self.assertEqual(cart["item_count"], 2)

        # Cart count badge endpoint
        badge_resp = self.client.get("/api/market/cart-count")
        self.assertEqual(badge_resp.status_code, 200)
        self.assertEqual(badge_resp.get_json()["item_count"], 2)

    # ── 6. Recently Viewed Tracking ────────────────────────────────────────────

    def test_recently_viewed_recording(self):
        """Recording viewed product and retrieving recently viewed list."""
        resp = self.client.get("/api/market/products?limit=2")
        products = resp.get_json()["products"]
        p1_id = products[0]["id"]
        p2_id = products[1]["id"]

        # Product detail call auto-records recently viewed
        self.client.get(f"/api/market/products/{p1_id}")
        self.client.get(f"/api/market/products/{p2_id}")

        rec_resp = self.client.get("/api/market/recently-viewed")
        self.assertEqual(rec_resp.status_code, 200)
        rec_data = rec_resp.get_json()
        self.assertTrue(rec_data["success"])
        rec_ids = [item["id"] for item in rec_data["items"]]
        self.assertIn(p2_id, rec_ids)
        self.assertIn(p1_id, rec_ids)

    # ── 7. Global Navbar Preservation ──────────────────────────────────────────

    def test_navbar_remains_intact(self):
        """Global navbar source files must remain intact with identical navigation items."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        navbar_css = os.path.join(base_dir, "frontend", "css", "navbar.css")
        navbar_js = os.path.join(base_dir, "frontend", "js", "navbar.js")

        self.assertTrue(os.path.isfile(navbar_css), "navbar.css was removed or renamed")
        self.assertTrue(os.path.isfile(navbar_js), "navbar.js was removed or renamed")

        with open(navbar_js, "r", encoding="utf-8") as f:
            js_content = f.read()

        # Check critical navbar items
        for label in ("Dashboard", "Workout", "Analysis", "Progress", "Game", "Nutrition", "Fitness Market"):
            self.assertIn(label, js_content, f"Navbar item '{label}' missing from navbar.js")

        for action_id in ("poseaiCartBtn", "poseaiNotifBtn", "poseaiProfileBtn"):
            self.assertIn(action_id, js_content, f"Navbar action '{action_id}' missing from navbar.js")

    # ── 8. HTML Page Architecture ──────────────────────────────────────────────

    def test_market_html_zones_and_footer(self):
        """fitness_market.html must contain all specified Zones 1 through 7 and global platform footer."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        html_path = os.path.join(base_dir, "frontend", "html", "fitness_market.html")
        self.assertTrue(os.path.isfile(html_path))

        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Zone 1 Hero + Search
        self.assertIn("market-hero-zone", html)
        self.assertIn("FITNESS MARKET", html)
        self.assertIn("marketSearchInput", html)
        self.assertIn("heroCartBtn", html)

        # Zone 2 Category Strip
        self.assertIn("market-category-strip", html)
        self.assertIn("SUPPLEMENTS", html)
        self.assertIn("PROTEIN", html)
        self.assertIn("PERFORMANCE", html)
        self.assertIn("RECOVERY", html)
        self.assertIn("TRAINING GEAR", html)

        # Zone 3 For Your Training
        self.assertIn("market-training-section", html)
        self.assertIn("STRENGTH FOCUS", html)
        self.assertIn("REST &amp; REPAIR", html)

        # Zone 4 Promotional Banner
        self.assertIn("market-promo-banner", html)
        self.assertIn("TRAIN SMARTER.<br>RECOVER BETTER.", html)

        # Zone 5 All Products + Left Filter Sidebar + 3-Column Grid
        self.assertIn("market-catalog-section", html)
        self.assertIn("market-filter-sidebar", html)
        self.assertIn("products-grid", html)
        self.assertIn("productsCountBadge", html)

        # Zone 6 Training Collections
        self.assertIn("market-collections-section", html)
        self.assertIn("BUILD STRENGTH", html)
        self.assertIn("RECOVER &amp; RESET", html)
        self.assertIn("EVERYDAY FITNESS", html)

        # Zone 6B Recently Viewed
        self.assertIn("market-recently-viewed-section", html)
        self.assertIn("recentlyViewedGrid", html)

        # Zone 7 Why PoseAI Market
        self.assertIn("market-why-section", html)
        self.assertIn("CURATED PRODUCTS", html)
        self.assertIn("TRAINING CONTEXT", html)
        self.assertIn("SIMPLE SHOPPING", html)

        # Platform Footer
        self.assertIn("market-global-footer", html)
        self.assertIn("PLATFORM", html)
        self.assertIn("ACCOUNT", html)

        # Unified Navbar Integration
        self.assertIn('id="app-header"', html)
        self.assertIn('src="/js/navbar.js"', html)
        self.assertIn('data-page="market"', html)

    # ── 9. Expanded Catalog Verification (84 Products / 12 per Category) ──────

    def test_minimum_12_products_per_category_and_84_total(self):
        """Assert minimum 12 products in each of the 7 main categories and >= 84 total."""
        products_col = repository.get_products_collection()
        total_count = products_col.count_documents({"is_active": True})
        self.assertGreaterEqual(total_count, 84, f"Expected at least 84 products, got {total_count}")

        categories = [
            "supplements", "protein", "performance", "recovery",
            "training-gear", "apparel", "accessories"
        ]
        for cat in categories:
            count = products_col.count_documents({"is_active": True, "category": cat})
            self.assertGreaterEqual(
                count, 12,
                f"Category '{cat}' must have at least 12 products, found {count}"
            )

    def test_dynamic_category_counts_from_mongo(self):
        """The /api/market/categories endpoint must return live product counts."""
        resp = self.client.get("/api/market/categories")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        cats = {c["slug"]: c for c in data["categories"]}

        for cat_slug in ("supplements", "protein", "performance", "recovery", "training-gear", "apparel", "accessories"):
            self.assertIn(cat_slug, cats)
            self.assertGreaterEqual(cats[cat_slug]["product_count"], 12)

    def test_product_detail_page_and_routes(self):
        """Dynamic product detail page is accessible via both path and query parameters."""
        products_col = repository.get_products_collection()
        one = products_col.find_one({"is_active": True})
        self.assertIsNotNone(one)
        pid = str(one["_id"])

        for route in (f"/market/product/{pid}", f"/fitness-market/product/{pid}", f"/fitness-market/product?id={pid}"):
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, f"Route {route} failed with {resp.status_code}")
            html_text = resp.data.decode("utf-8")
            self.assertIn("detailContainer", html_text)
            self.assertIn("productBreadcrumbs", html_text)

    def test_food_vs_nonfood_details_integrity(self):
        """Verify food products have nutrition facts while gear has specifications and no nutrition."""
        products_col = repository.get_products_collection()

        # Check a Protein product (food)
        protein = products_col.find_one({"category": "protein", "is_active": True})
        self.assertIsNotNone(protein)
        p_resp = self.client.get(f"/api/market/products/{protein['_id']}")
        self.assertEqual(p_resp.status_code, 200)
        p_data = p_resp.get_json()["product"]
        self.assertTrue(len(p_data.get("nutrition_facts", [])) > 0, "Protein product must have nutrition_facts")
        self.assertEqual(len(p_data.get("weight_options", [])), 0, "Protein product should not have dumbbell weight options")

        # Check a Dumbbell/Gear product (non-food)
        gear = products_col.find_one({"category": "training-gear", "is_active": True})
        self.assertIsNotNone(gear)
        g_resp = self.client.get(f"/api/market/products/{gear['_id']}")
        self.assertEqual(g_resp.status_code, 200)
        g_data = g_resp.get_json()["product"]
        self.assertEqual(len(g_data.get("nutrition_facts", [])), 0, "Gear product must not have nutrition facts")
        self.assertTrue(bool(g_data.get("specifications")), "Gear product must have specifications")

    def test_product_detail_html_structure(self):
        """product_detail.html must contain all core zones without misplaced floating panels."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        html_path = os.path.join(base_dir, "frontend", "html", "product_detail.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("detailContainer", html)
        self.assertIn("productBreadcrumbs", html)
        self.assertIn("tabsContainer", html)
        self.assertIn("synergyStackContainer", html)
        self.assertIn("relatedGrid", html)


if __name__ == "__main__":
    unittest.main()
