"""
PoseAI — Fitness Market Test Suite

Validates the market REST API against an in-memory mongomock database:
  * Authentication guards (pages redirect, API 401 envelopes)
  * Catalog seeding, search/filter/sort/paginate
  * Error codes: INVALID_ID, PRODUCT_NOT_FOUND, INVALID_QUANTITY,
    OUT_OF_STOCK, INSUFFICIENT_STOCK
  * Server-authoritative cart math (never trusts client prices)
  * Cart mutations (add/update/remove/clear) + per-user isolation
"""

import unittest

from app import app
from market import repository, seed
from tests.helpers import setup_mongo_mock


class MarketSuite(unittest.TestCase):
    VALID_PASSWORD = "StrongPassphrase123!"

    def setUp(self):
        setup_mongo_mock()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        seed.seed_if_empty()
        self._signup()

    def _signup(self, email="shopper@poseai.test", name="Market Shopper"):
        resp = self.client.post("/auth/signup", json={
            "name": name,
            "email": email,
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        self.assertEqual(resp.status_code, 201)
        return self.client

    def _product_by_slug(self, slug):
        doc = repository.find_product_by_slug(slug)
        self.assertIsNotNone(doc, "seed product missing: {0}".format(slug))
        return str(doc["_id"])

    @classmethod
    def _first(cls, items):
        return items[0]

    # ── Auth guards ────────────────────────────────────────────────

    def test_market_pages_redirect_unauthenticated(self):
        anon = app.test_client()
        for path in ("/fitness-market", "/cart"):
            resp = anon.get(path)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/login", resp.headers.get("Location", ""))

    def test_market_api_unauthenticated_401(self):
        anon = app.test_client()
        for path in ("/api/market/products", "/api/market/cart", "/api/market/categories"):
            resp = anon.get(path)
            self.assertEqual(resp.status_code, 401)
            error = resp.get_json()["error"]
            self.assertEqual(error["code"], "UNAUTHENTICATED")

    def test_market_api_mutation_unauthenticated_401(self):
        anon = app.test_client()
        resp = anon.post("/api/market/cart", json={"product_id": "f" * 24, "quantity": 1})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["error"]["code"], "UNAUTHENTICATED")

    # ── Catalog ────────────────────────────────────────────────────

    def test_categories_seeded(self):
        resp = self.client.get("/api/market/categories")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        slugs = [c["slug"] for c in data["categories"]]
        self.assertGreaterEqual(len(slugs), 10)
        self.assertIn("protein", slugs)
        self.assertIn("deals", slugs)

    def test_products_listing_paginates(self):
        resp = self.client.get("/api/market/products?limit=10&page=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertLessEqual(len(data["products"]), 10)
        self.assertEqual(data["pagination"]["total"], 84)
        self.assertEqual(data["pagination"]["total_pages"], 9)
        self.assertEqual(data["pagination"]["page"], 2)

    def test_search_filters_products(self):
        resp = self.client.get("/api/market/products", query_string={"search": "Whey"})
        payload = resp.get_json()
        self.assertTrue(payload["success"])
        self.assertGreater(len(payload["products"]), 0)
        for p in payload["products"]:
            self.assertIn("whey", p["name"].lower())

    def test_category_filter(self):
        resp = self.client.get("/api/market/products", query_string={"category": "protein"})
        payload = resp.get_json()
        for p in payload["products"]:
            self.assertEqual(p["category"], "protein")

    def test_price_filter(self):
        resp = self.client.get(
            "/api/market/products", query_string={"min_price": 2000, "max_price": 3500}
        )
        payload = resp.get_json()
        self.assertGreater(len(payload["products"]), 0)
        for p in payload["products"]:
            self.assertGreaterEqual(p["price"], 2000)
            self.assertLessEqual(p["price"], 3500)

    def test_sort_price_asc(self):
        resp = self.client.get("/api/market/products", query_string={"sort": "price_asc", "limit": 50})
        prices = [p["price"] for p in resp.get_json()["products"]]
        self.assertEqual(prices, sorted(prices))

    def test_brand_filter(self):
        resp = self.client.get("/api/market/products", query_string={"brand": "FlexLine"})
        payload = resp.get_json()
        self.assertGreater(len(payload["products"]), 0)
        for p in payload["products"]:
            self.assertEqual(p["brand"], "FlexLine")

    def test_in_stock_filter_excludes_out_of_stock(self):
        resp = self.client.get("/api/market/products", query_string={"in_stock": "1", "limit": 50})
        for p in resp.get_json()["products"]:
            self.assertGreater(p["stock_quantity"], 0)
            self.assertTrue(p["in_stock"])

    def test_deals_virtual_category(self):
        resp = self.client.get("/api/market/products", query_string={"category": "deals"})
        payload = resp.get_json()
        self.assertGreater(len(payload["products"]), 0)
        for p in payload["products"]:
            self.assertTrue(p["is_deal"])

    def test_out_of_stock_products_returned_with_label(self):
        oid = self._product_by_slug("micronized-creatine-500g")
        resp = self.client.get("/api/market/products/{0}".format(oid))
        self.assertEqual(resp.status_code, 200)
        product = resp.get_json()["product"]
        self.assertEqual(product["stock_quantity"], 0)
        self.assertFalse(product["in_stock"])
        self.assertIn("Out of Stock", product["stock_label"])

    # ── Error codes ────────────────────────────────────────────────

    def test_invalid_object_id(self):
        for bad in ("abc", "nothex" * 4, "z" * 24):
            resp = self.client.get("/api/market/products/{0}".format(bad))
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.get_json()["error"]["code"], "INVALID_ID")

    def test_product_not_found(self):
        resp = self.client.get("/api/market/products/{0}".format("f" * 24))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"]["code"], "PRODUCT_NOT_FOUND")

    def test_product_detail_shape(self):
        oid = self._product_by_slug("creatine-monohydrate-250g")
        resp = self.client.get("/api/market/products/{0}".format(oid))
        product = resp.get_json()["product"]
        self.assertEqual(product["price"], 799)
        self.assertEqual(product["original_price"], 999)
        self.assertEqual(product["discount_percentage"], 20)
        self.assertEqual(product["currency"] if "currency" in product else None, None)
        self.assertIsInstance(product["image_urls"], list)
        self.assertIsInstance(product["rating"], float)
        self.assertEqual(product["in_stock"], True)

    # ── Cart math (server-authoritative) ───────────────────────────

    def test_add_to_cart_money_is_server_derived(self):
        oid = self._product_by_slug("creatine-monohydrate-250g")  # price 799, mrp 999
        resp = self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 2})
        self.assertEqual(resp.status_code, 201)
        cart = resp.get_json()["cart"]
        self.assertEqual(cart["item_count"], 2)
        self.assertEqual(cart["subtotal"], 1998)
        self.assertEqual(cart["discount"], 400)
        self.assertEqual(cart["total"], 1598)
        self.assertEqual(cart["currency"], "INR")
        self.assertEqual(cart["cart_money_total"], cart["total"])
        line = cart["items"][0]
        self.assertEqual(line["quantity"], 2)
        self.assertEqual(line["line_total"], 1598)
        self.assertEqual(line["line_mrp"], 1998)
        self.assertEqual(line["line_discount"], 400)
        # The cart collection must never store a price.
        stored = repository.get_cart_doc(repository_cart_user())
        self.assertEqual(list(stored["items"][0].keys()), ["product_id", "quantity"])

    def test_add_duplicate_product_replaces_quantity(self):
        oid = self._product_by_slug("creatine-monohydrate-250g")
        self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 1})
        resp = self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 3})
        cart = resp.get_json()["cart"]
        self.assertEqual(len(cart["items"]), 1)
        self.assertEqual(cart["items"][0]["quantity"], 3)
        self.assertEqual(cart["item_count"], 3)

    def test_invalid_quantity_rejected(self):
        oid = self._product_by_slug("creatine-monohydrate-250g")
        for bad in (0, -1, 1.5, "abc", "2.5", True, None, ""):
            resp = self.client.post("/api/market/cart", json={"product_id": oid, "quantity": bad})
            self.assertEqual(resp.status_code, 422, "expected 422 for {0!r}".format(bad))
            self.assertEqual(resp.get_json()["error"]["code"], "INVALID_QUANTITY")

    def test_quantity_missing_validation_error(self):
        resp = self.client.post("/api/market/cart", json={"product_id": "f" * 24})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], "VALIDATION_ERROR")

    def test_patch_updates_quantity(self):
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 1})
        resp = self.client.patch(
            "/api/market/cart/{0}".format(oid), json={"quantity": 4}
        )
        cart = resp.get_json()["cart"]
        self.assertEqual(cart["items"][0]["quantity"], 4)
        self.assertEqual(cart["total"], cart["items"][0]["line_total"])

    def test_patch_above_stock_insufficient_stock(self):
        oid = self._product_by_slug("creatine-monohydrate-250g")  # stock 60
        resp = self.client.patch("/api/market/cart/{0}".format(oid), json={"quantity": 61})
        self.assertEqual(resp.status_code, 409)
        error = resp.get_json()["error"]
        self.assertEqual(error["code"], "INSUFFICIENT_STOCK")
        self.assertEqual(error["available_quantity"], 60)

    def test_out_of_stock_rejected(self):
        oid = self._product_by_slug("micronized-creatine-500g")  # stock 0
        resp = self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 1})
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.get_json()["error"]["code"], "OUT_OF_STOCK")

    def test_delete_removes_line(self):
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 2})
        resp = self.client.delete("/api/market/cart/{0}".format(oid))
        cart = resp.get_json()["cart"]
        self.assertEqual(cart["items"], [])
        self.assertEqual(cart["item_count"], 0)
        self.assertEqual(cart["total"], 0)

    def test_stock_label_low_stock(self):
        oid = self._product_by_slug("vitamin-d3-plus-k2-60ct")  # stock 3
        resp = self.client.get("/api/market/products/{0}".format(oid))
        self.assertIn("Only 3 left", resp.get_json()["product"]["stock_label"])

    def test_clear_cart(self):
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 1})
        resp = self.client.post("/api/market/cart/clear")
        cart = resp.get_json()["cart"]
        self.assertEqual(cart["items"], [])
        self.assertEqual(cart["total"], 0)

    def test_cart_count_badge(self):
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 3})
        resp = self.client.get("/api/market/cart-count")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["item_count"], 3)

    def test_cart_user_isolation(self):
        client_a = self.client
        client_b = app.test_client()
        client_b.post("/auth/signup", json={
            "name": "Second Shopper",
            "email": "shopper2@poseai.test",
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        client_a.post("/api/market/cart", json={"product_id": oid, "quantity": 1})

        cart_a = client_a.get("/api/market/cart").get_json()["cart"]
        cart_b = client_b.get("/api/market/cart").get_json()["cart"]
        self.assertEqual(cart_a["item_count"], 1)
        self.assertEqual(cart_b["item_count"], 0)

    def test_cart_detail_matches_products(self):
        """The listing and the cart must report identical live prices."""
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        detail = self.client.get("/api/market/products/{0}".format(oid)).get_json()["product"]
        self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 1})
        line = self.client.get("/api/market/cart").get_json()["cart"]["items"][0]
        self.assertEqual(line["price"], detail["price"])
        self.assertEqual(line["original_price"], detail["original_price"])

    # ── Rating / discount filters + custom sorts ───────────────────

    def test_rating_filter(self):
        resp = self.client.get("/api/market/products", query_string={"rating": "4.5", "limit": 50})
        payload = resp.get_json()
        self.assertGreater(len(payload["products"]), 0)
        for p in payload["products"]:
            self.assertGreaterEqual(p["rating"], 4.5)

    def test_discount_filter(self):
        resp = self.client.get("/api/market/products", query_string={"discount": "20", "limit": 50})
        payload = resp.get_json()
        self.assertGreater(len(payload["products"]), 0)
        for p in payload["products"]:
            self.assertGreaterEqual(p["discount_percentage"], 20)

    def test_invalid_rating_and_discount_filters(self):
        for qs in ({"rating": "5.5"}, {"rating": "abc"}, {"discount": "-1"}, {"discount": "150"}):
            resp = self.client.get("/api/market/products", query_string=qs)
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.get_json()["error"]["code"], "VALIDATION_ERROR")

    def test_sort_rating_desc(self):
        resp = self.client.get("/api/market/products", query_string={"sort": "rating_desc", "limit": 50})
        ratings = [p["rating"] for p in resp.get_json()["products"]]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_sort_discount_desc(self):
        resp = self.client.get("/api/market/products", query_string={"sort": "discount_desc", "limit": 50})
        discounts = [p["discount_percentage"] for p in resp.get_json()["products"]]
        self.assertEqual(discounts, sorted(discounts, reverse=True))

    # ── Cart delivery fee + grand total (server-authoritative) ─────

    def test_delivery_fee_below_threshold(self):
        oid = self._product_by_slug("creatine-monohydrate-250g")  # price 799 < threshold
        self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 1})
        cart = self.client.get("/api/market/cart").get_json()["cart"]
        self.assertEqual(cart["subtotal"], 999)
        self.assertEqual(cart["total"], 799)
        self.assertEqual(cart["delivery_fee"], 99)
        self.assertEqual(cart["grand_total"], 898)
        self.assertEqual(cart["grand_total"], cart["total"] + cart["delivery_fee"])

    def test_free_delivery_at_or_above_threshold(self):
        oid = self._product_by_slug("creatine-monohydrate-250g")
        self.client.post("/api/market/cart", json={"product_id": oid, "quantity": 2})  # total 1598
        cart = self.client.get("/api/market/cart").get_json()["cart"]
        self.assertEqual(cart["total"], 1598)
        self.assertEqual(cart["delivery_fee"], 0)
        self.assertEqual(cart["grand_total"], 1598)
        self.assertEqual(cart["free_delivery_threshold"], 999)

    def test_empty_cart_delivery_is_zero(self):
        cart = self.client.get("/api/market/cart").get_json()["cart"]
        self.assertEqual(cart["delivery_fee"], 0)
        self.assertEqual(cart["grand_total"], 0)

    # ── Favorites ──────────────────────────────────────────────────

    def test_favorites_add_list_remove(self):
        oid = self._product_by_slug("creatine-monohydrate-250g")
        resp = self.client.post("/api/market/favorites/{0}".format(oid))
        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertTrue(body["success"])
        self.assertTrue(body["favorited"])
        self.assertEqual(body["product_id"], oid)
        self.assertEqual(body["count"], 1)

        listing = self.client.get("/api/market/favorites").get_json()
        self.assertTrue(listing["success"])
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["products"][0]["id"], oid)
        self.assertTrue(listing["products"][0]["is_favorite"])

        resp = self.client.delete("/api/market/favorites/{0}".format(oid))
        self.assertEqual(resp.get_json()["favorited"], False)
        self.assertEqual(resp.get_json()["count"], 0)
        self.assertEqual(self.client.get("/api/market/favorites").get_json()["count"], 0)

    def test_favorite_duplicate_is_idempotent(self):
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        self.client.post("/api/market/favorites/{0}".format(oid))
        resp = self.client.post("/api/market/favorites/{0}".format(oid))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["count"], 1)  # still one row (unique index)

    def test_favorites_user_isolation(self):
        client_b = app.test_client()
        client_b.post("/auth/signup", json={
            "name": "Fav Shopper",
            "email": "shopper3@poseai.test",
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        oid = self._product_by_slug("steel-shaker-bottle-700ml")
        self.client.post("/api/market/favorites/{0}".format(oid))
        self.assertEqual(self.client.get("/api/market/favorites").get_json()["count"], 1)
        self.assertEqual(client_b.get("/api/market/favorites").get_json()["count"], 0)

    def test_favorite_invalid_id_and_missing_product(self):
        resp = self.client.post("/api/market/favorites/{0}".format("zz" * 12))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], "INVALID_ID")

        resp = self.client.post("/api/market/favorites/{0}".format("f" * 24))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"]["code"], "PRODUCT_NOT_FOUND")

    def test_favorites_unauthenticated_401(self):
        anon = app.test_client()
        for method, path in (
            ("GET", "/api/market/favorites"),
            ("POST", "/api/market/favorites/{0}".format("f" * 24)),
        ):
            resp = getattr(anon, method.lower())(path)
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(resp.get_json()["error"]["code"], "UNAUTHENTICATED")

    def test_listing_carries_favorite_flag(self):
        oid = self._product_by_slug("creatine-monohydrate-250g")
        self.client.post("/api/market/favorites/{0}".format(oid))
        resp = self.client.get("/api/market/products", query_string={"category": "creatine", "limit": 50})
        flagged = [p for p in resp.get_json()["products"] if p["id"] == oid]
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0]["is_favorite"])

    def test_detail_carries_favorite_flag(self):
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        self.client.post("/api/market/favorites/{0}".format(oid))
        detail = self.client.get("/api/market/products/{0}".format(oid)).get_json()["product"]
        self.assertTrue(detail["is_favorite"])

    def test_no_favorite_flag_when_no_favorites(self):
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        detail = self.client.get("/api/market/products/{0}".format(oid)).get_json()["product"]
        self.assertFalse(detail["is_favorite"])

    # ── Landing / home ─────────────────────────────────────────────

    def test_home_shapes_all_sections(self):
        resp = self.client.get("/api/market/home")
        self.assertEqual(resp.status_code, 200)
        home = resp.get_json()["home"]
        self.assertGreaterEqual(len(home["categories"]), 10)
        self.assertGreaterEqual(len(home["goals"]), 5)
        self.assertGreaterEqual(len(home["deals"]), 4)
        self.assertTrue(all(p["is_deal"] for p in home["deals"]))
        self.assertGreaterEqual(len(home["best_sellers"]), 6)
        self.assertGreaterEqual(len(home["new_arrivals"]), 6)
        self.assertGreaterEqual(len(home["essentials"]), 4)
        self.assertTrue(all(p["category"] == "accessories" for p in home["essentials"]))
        self.assertEqual(home["recommended"]["basis"], "best-sellers")
        self.assertTrue(home["recommended"]["items"])

    def test_home_carries_favorite_flags(self):
        oid = self._product_by_slug("whey-protein-isolate-2kg")
        self.client.post("/api/market/favorites/{0}".format(oid))
        home = self.client.get("/api/market/home").get_json()["home"]
        flagged = [p for p in home["best_sellers"] if p["id"] == oid]
        self.assertTrue(flagged and flagged[0]["is_favorite"])

    def test_home_goal_stats_have_counts(self):
        home = self.client.get("/api/market/home").get_json()["home"]
        counts = {goal["key"]: goal["count"] for goal in home["goals"]}
        self.assertGreater(counts["build-muscle"], 0)
        self.assertGreater(counts["recovery"], 0)
        self.assertGreater(counts["wellness"], 0)

    # ── Shop-by-goal filter ───────────────────────────────────────

    def test_products_goal_filter(self):
        from market import service

        resp = self.client.get("/api/market/products", query_string={"goal": "recovery", "limit": 50})
        self.assertEqual(resp.status_code, 200)
        products = resp.get_json()["products"]
        self.assertTrue(products)
        goal_tags = set(service.GOAL_TAG_MAP["recovery"])
        for product in products:
            self.assertTrue(set(product["tags"]) & goal_tags)

    def test_products_goal_invalid_400(self):
        resp = self.client.get("/api/market/products", query_string={"goal": "get-ripped"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], "VALIDATION_ERROR")

    # ── Orders ─────────────────────────────────────────────────────

    _ADDRESS = {
        "full_name": "Market Shopper",
        "phone": "9876543210",
        "line1": "42 Lift Street",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560001",
    }

    def _add_creatine(self, quantity=1):
        oid = self._product_by_slug("creatine-monohydrate-250g")
        resp = self.client.post("/api/market/cart", json={"product_id": oid, "quantity": quantity})
        self.assertEqual(resp.status_code, 201)
        return self.client.get("/api/market/cart").get_json()["cart"]

    def _place_order(self, address=None):
        body = {"address": address or self._ADDRESS}
        return self.client.post("/api/market/orders", json=body)

    def test_order_requires_cart(self):
        resp = self._place_order()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], "VALIDATION_ERROR")

    def test_order_requires_valid_address(self):
        self._add_creatine()
        resp = self._place_order({"full_name": "X"})
        self.assertEqual(resp.status_code, 400)
        resp = self._place_order({**self._ADDRESS, "phone": "12345"})
        self.assertEqual(resp.status_code, 400)
        resp = self._place_order({**self._ADDRESS, "pincode": "56000"})
        self.assertEqual(resp.status_code, 400)

    def test_order_create_clears_cart_and_marks_payment_pending(self):
        self._add_creatine(2)  # 1598 >= 999 -> free delivery
        resp = self._place_order()
        self.assertEqual(resp.status_code, 201)
        order = resp.get_json()["order"]
        self.assertEqual(order["status"], "PENDING")
        self.assertEqual(order["payment_status"], "PENDING")
        self.assertEqual(order["delivery_fee"], 0)
        self.assertEqual(order["total"], 1598)
        self.assertEqual(order["item_count"], 2)
        self.assertEqual(order["shipping_address"]["pincode"], "560001")
        self.assertTrue(order["order_number"].startswith("POM-"))
        self.assertEqual(self.client.get("/api/market/cart").get_json()["cart"]["item_count"], 0)

    def test_order_delivery_fee_applied_below_threshold(self):
        self._add_creatine(1)  # 799 < 999 -> 99 delivery
        order = self._place_order().get_json()["order"]
        self.assertEqual(order["delivery_fee"], 99)
        self.assertEqual(order["total"], 898)

    def test_orders_list_and_detail(self):
        self._add_creatine()
        order = self._place_order().get_json()["order"]
        listing = self.client.get("/api/market/orders").get_json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["orders"][0]["order_number"], order["order_number"])
        detail = self.client.get("/api/market/orders/{0}".format(order["id"])).get_json()["order"]
        self.assertEqual(detail["id"], order["id"])
        self.assertEqual(detail["items"][0]["product_id"], self._product_by_slug("creatine-monohydrate-250g"))

    def test_orders_user_isolation(self):
        self._add_creatine()
        order = self._place_order().get_json()["order"]
        other = app.test_client()
        other.post("/auth/signup", json={
            "name": "Other",
            "email": "other-shopper@poseai.test",
            "password": self.VALID_PASSWORD,
            "confirm_password": self.VALID_PASSWORD,
        })
        resp = other.get("/api/market/orders/{0}".format(order["id"]))
        self.assertEqual(resp.status_code, 404)
        listing = other.get("/api/market/orders").get_json()
        self.assertEqual(listing["count"], 0)

    def test_order_invalid_id_and_unknown(self):
        resp = self.client.get("/api/market/orders/{0}".format("zz" * 12))
        self.assertEqual(resp.status_code, 400)
        resp = self.client.get("/api/market/orders/{0}".format("f" * 24))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"]["code"], "ORDER_NOT_FOUND")

    def test_orders_unauthenticated_401(self):
        anon = app.test_client()
        resp = anon.get("/api/market/orders")
        self.assertEqual(resp.status_code, 401)
        resp = anon.post("/api/market/orders", json={"address": self._ADDRESS})
        self.assertEqual(resp.status_code, 401)

    def test_market_new_pages_redirect_unauthenticated(self):
        anon = app.test_client()
        for path in ("/fitness-market/products", "/fitness-market/favorites",
                     "/fitness-market/checkout", "/fitness-market/orders"):
            resp = anon.get(path)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/login", resp.headers.get("Location", ""))

    def test_home_unauthenticated_401(self):
        anon = app.test_client()
        self.assertEqual(anon.get("/api/market/home").status_code, 401)


def repository_cart_user():  # matches the signup email used in setUp
    from database import mongo

    user = mongo.get_users_collection().find_one({"email": "shopper@poseai.test"})
    return str(user["_id"])


if __name__ == "__main__":
    unittest.main()