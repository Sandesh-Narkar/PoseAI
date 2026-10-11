"""Fitness Market — idempotent catalog seed.

Run manually:      python -m market.seed
Run automatically: routes call `seed_if_empty()` on first catalog read so a
fresh database is instantly browsable (mirrors the existing app cadence).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from . import repository

logger = logging.getLogger("market.seed")

_CATEGORIES = [
    {"slug": "supplements", "name": "Supplements", "subtitle": "Whey & more", "sort_order": 10},
    {"slug": "protein", "name": "Protein", "subtitle": "Protein & bars", "sort_order": 20},
    {"slug": "performance", "name": "Performance", "subtitle": "Pre-workout", "sort_order": 30},
    {"slug": "recovery", "name": "Recovery", "subtitle": "Recovery tools", "sort_order": 40},
    {"slug": "training-gear", "name": "Training Gear", "subtitle": "Equipment", "sort_order": 50},
    {"slug": "apparel", "name": "Apparel", "subtitle": "Gym essentials", "sort_order": 60},
    {"slug": "accessories", "name": "Accessories", "subtitle": "Hydration & gear", "sort_order": 70},
    {"slug": "creatine", "name": "Creatine", "subtitle": "Strength & power", "sort_order": 80},
    {"slug": "vitamins", "name": "Vitamins", "subtitle": "Daily essentials", "sort_order": 90},
    {"slug": "deals", "name": "Hot Deals", "subtitle": "Limited offers", "sort_order": 100},
]

# (name, brand, category, subcategory, price, mrp, rating, reviews, stock, tags, is_deal, image, badge, badge_color, weight_label, ai_match)
_PRODUCTS_46: list[tuple] = [
    # Protein & Gainers
    ("BioAbsorb Whey Protein & Gold Standard Combo 1kg", "FlexLine", "protein", "whey", 2999, 3599, 4.9, 3420, 34, ["protein", "whey", "isolate", "muscle-gain", "strength"], True, "/images/market_products/image-1-1782968120.webp", "AI MATCH 98%", "mk-badge-teal", "2.0 KG", 98),
    ("Gold 100% Pea Protein Plant Isolate 1kg", "Nutrabay", "protein", "plant", 2399, 2999, 4.6, 1280, 25, ["protein", "vegan", "plant", "isolate", "muscle-gain"], False, "/images/market_products/Pea-Protein-1771222444.webp", "ORGANIC PEA", "mk-badge-green", "1.0 KG", 93),
    ("Complete Fermented Yeast Protein 1kg", "Nutrabay", "protein", "plant", 2599, 3199, 4.5, 720, 18, ["protein", "yeast", "clean", "muscle-gain"], False, "/images/market_products/Yeast-Protein-1771222444.webp", "FERMENTED YEAST", "mk-badge-blue", "1.0 KG", 91),
    ("Mega Mass Gainer XXL 3kg", "Nutrabay", "protein", "gainer", 3499, 4299, 4.5, 980, 22, ["protein", "gainer", "mass", "calories", "muscle-gain"], True, "/images/market_products/Mass-&-Weight-gainers-1767084988.webp", "HIGH CALORIE", "mk-badge-teal", "3.0 KG", 89),

    # Creatine & Supplements
    ("Pure Micronized Creatine Monohydrate 250g", "Nutrabay", "creatine", "monohydrate", 799, 999, 4.8, 3120, 60, ["creatine", "monohydrate", "strength", "muscle-gain"], True, "/images/market_products/Creatine-2-1779255946.webp", "MICRONIZED 200 MESH", "mk-badge-blue", "250 G", 96),
    ("Organic Ashwagandha KSM-66 60ct", "Nutrabay", "supplements", "adaptogen", 699, 999, 4.7, 1420, 40, ["supplements", "ashwagandha", "adaptogen", "wellness", "recovery"], False, "/images/market_products/Ashwagandha-1770189032.webp", "KSM-66 GOLD", "mk-badge-blue", "60 CT", 94),
    ("Triple Strength Omega-3 Fish Oil 1000mg 90ct", "Nutrabay", "supplements", "omega-3", 849, 1199, 4.6, 1890, 35, ["supplements", "omega-3", "fish-oil", "wellness"], True, "/images/market_products/Omega-1766725264.webp", "TRIPLE STRENGTH", "mk-badge-teal", "90 CAPS", 95),
    ("Pro Daily Multivitamins for Men 60ct", "Nutrabay", "vitamins", "multivitamin", 649, 899, 4.7, 2110, 50, ["vitamins", "supplements", "multivitamin", "daily", "wellness"], False, "/images/market_products/Multivitamins-for-Men-1776232203.webp", "ACTIVE MULTI", "mk-badge-blue", "60 CT", 92),
    ("Vitamin D3 + K2 Bone & Muscle Health 60ct", "Nutrabay", "vitamins", "single-vitamins", 549, 799, 4.5, 940, 3, ["vitamins", "supplements", "vitamin-d", "immunity", "wellness"], False, "/images/market_products/Single-Vitamins-1767085085.webp", "MAX ABSORPTION", "mk-badge-blue", "60 CT", 90),
    ("Advanced Pre & Probiotic 50 Billion CFU", "Nutrabay", "supplements", "gut-health", 999, 1399, 4.4, 680, 20, ["supplements", "probiotic", "wellness", "gut"], False, "/images/market_products/Pre-&-Probiotic-1-1779255946.webp", "50B CFU", "mk-badge-green", "60 CAPS", 89),
    ("Gold Pure Himalayan Shilajit Resin 20g", "Nutrabay", "supplements", "vitality", 1299, 1799, 4.8, 2450, 15, ["supplements", "shilajit", "strength", "vitality"], True, "/images/market_products/Shilajit-1767085156.webp", "PURIFIED RESIN", "mk-badge-teal", "20 G", 97),
    ("Micronized Creatine 500g", "Nutrabay", "creatine", "monohydrate", 1499, 1899, 4.7, 1200, 0, ["creatine", "monohydrate", "strength"], False, "/images/market_products/Creatine-2-1779255946.webp", "ZERO STOCK", "mk-badge-gray", "500 G", 92),

    # Performance
    ("Rage X Explosive Pre-Workout Cola 300g", "Nutrabay", "pre-workout", "energy", 1499, 1999, 4.6, 1750, 35, ["pre-workout", "performance", "energy", "caffeine", "strength"], True, "/images/market_products/Pre-Workout-1768369799.webp", "EXPLOSIVE PUMP", "mk-badge-red", "300 G", 95),
    ("XTEND 7g BCAA + Gold Electrolytes 30 Servings", "Scivation & Nutrabay", "performance", "bcaa", 1899, 2399, 4.7, 2180, 25, ["bcaa", "performance", "recovery", "electrolytes"], False, "/images/market_products/BCAA-1-1776232203.webp", "INTRA WORKOUT", "mk-badge-cyan", "30 SERVINGS", 93),
    ("Pure L-Carnitine 1000mg + Liquid 1100mg Stack", "Nutrabay", "performance", "weight-loss", 1199, 1599, 4.4, 910, 20, ["performance", "weight-loss", "energy", "l-carnitine"], False, "/images/market_products/L-Carnitine-1770189032.webp", "METABOLIC ACCELERATOR", "mk-badge-blue", "60 TABS", 90),

    # Recovery
    ("High Absorption Magnesium Glycinate 60ct", "Nutrabay", "recovery", "minerals", 699, 949, 4.8, 1640, 45, ["recovery", "magnesium", "sleep", "wellness"], True, "/images/market_products/Magnesium-1767085118.webp", "CNS RESTORATION", "mk-badge-teal", "60 CAPS", 96),
    ("Technogym Textured Mobility & Slam Ball 6kg", "Technogym", "recovery", "mobility", 3999, 4999, 4.7, 540, 15, ["recovery", "mobility", "slam-ball", "training-gear"], False, "/images/market_products/A0001-SB-grey.jpg", "TEXTURED GRIP", "mk-badge-blue", "6.0 KG", 94),
    ("Technogym Heavy-Duty 9kg Wall Medicine Ball", "Technogym", "recovery", "mobility", 4999, 5999, 4.8, 420, 12, ["recovery", "mobility", "medicine-ball", "strength"], False, "/images/market_products/toolsmedicine-ball-plp.jpg", "DOUBLE STITCHED", "mk-badge-gray", "9.0 KG", 92),
    ("Technogym Wellness Active Sitting & Core Ball 65cm", "Technogym", "recovery", "core", 6499, 7999, 4.6, 310, 10, ["recovery", "active-sitting", "posture", "mobility"], False, "/images/market_products/wbas-w.webp", "ITALIAN DESIGN", "mk-badge-blue", "65 CM", 91),

    # Training Gear (Dumbbells, Barbells, Plates, Stations)
    ("PowerMax Pro Rubber Dumbbell Pair 2.5kg", "PowerMax", "training-gear", "dumbbells", 1499, 1999, 4.7, 1920, 30, ["training-gear", "dumbbells", "strength", "muscle-gain"], True, "/images/market_products/Dummbal.png", "RUBBER COATED", "mk-badge-blue", "PAIR 2.5KG", 95),
    ("Technogym 10kg Rubber Hex Dumbbell", "Technogym", "training-gear", "dumbbells", 2999, 3599, 4.8, 1420, 20, ["training-gear", "dumbbells", "strength", "hex"], False, "/images/market_products/hexagon-dumbbells-plp.jpg", "ANTI-ROLL HEX", "mk-badge-gray", "10.0 KG", 96),
    ("Technogym 10kg Rubber Hex Dumbbell (White Studio)", "Technogym", "training-gear", "dumbbells", 3199, 3799, 4.8, 860, 18, ["training-gear", "dumbbells", "strength", "studio"], False, "/images/market_products/hexagon-dumbbells-white.webp", "STUDIO EDITION", "mk-badge-blue", "10.0 KG", 94),
    ("Technogym Luxury Chrome Dumbbells Set (1-5kg)", "Technogym", "training-gear", "dumbbells", 8999, 10999, 4.9, 630, 8, ["training-gear", "dumbbells", "chrome", "luxury"], False, "/images/market_products/chrome-dumbbells-plp.jpg", "MIRROR CHROME", "mk-badge-teal", "SET 1-5KG", 98),
    ("Technogym Pro Round Urethane Dumbbell 16kg", "Technogym", "training-gear", "dumbbells", 4499, 5299, 4.8, 710, 14, ["training-gear", "dumbbells", "urethane", "commercial"], False, "/images/market_products/dumbbellss-plp.jpg", "COMMERCIAL URETHANE", "mk-badge-gray", "16.0 KG", 95),
    ("Technogym Smart Adjustable Dumbbells & Storage Station", "Technogym", "training-gear", "dumbbells", 24999, 29999, 4.9, 380, 5, ["training-gear", "dumbbells", "station", "smart"], True, "/images/market_products/hero-4-3.jpg", "PRECISION DIAL", "mk-badge-teal", "STATION KIT", 99),
    ("Technogym Competition Kettlebell 8kg / 18lb", "Technogym", "training-gear", "kettlebells", 3299, 3999, 4.7, 890, 16, ["training-gear", "kettlebells", "strength"], False, "/images/market_products/A0001689-grey.jpg", "SOLID CAST IRON", "mk-badge-blue", "8.0 KG", 92),
    ("Technogym Competition Kettlebell 20kg Chrome Handle", "Technogym", "training-gear", "kettlebells", 5499, 6499, 4.8, 520, 10, ["training-gear", "kettlebells", "strength", "chrome"], False, "/images/market_products/kettlebells-plp.jpg", "PRO CHROME HANDLE", "mk-badge-gray", "20.0 KG", 94),
    ("Technogym Olympic Angled EZ Curl Bar", "Technogym", "training-gear", "barbells", 4299, 5199, 4.8, 1140, 22, ["training-gear", "barbells", "ez-bar", "strength"], True, "/images/market_products/angled-fitness-bar-plp.jpg", "BIOMECHANIC CURVE", "mk-badge-blue", "1200 MM", 97),
    ("Technogym Olympic 2000mm Chrome Fitness Barbell", "Technogym", "training-gear", "barbells", 6999, 8499, 4.7, 780, 15, ["training-gear", "barbells", "olympic", "strength"], False, "/images/market_products/fitness-bar-2000mm-plp.jpg", "BRONZE BUSHING", "mk-badge-gray", "2000 MM", 93),
    ("Technogym Performance 2000 Olympic Barbell 20kg", "Technogym", "training-gear", "barbells", 7999, 9499, 4.9, 620, 12, ["training-gear", "barbells", "olympic", "performance"], False, "/images/market_products/performance-bar-2000-grey.jpg", "8-NEEDLE BEARING", "mk-badge-blue", "20.0 KG", 98),
    ("Technogym Professional Weightlifting Bar 20kg", "Technogym", "training-gear", "barbells", 9999, 11999, 4.9, 490, 8, ["training-gear", "barbells", "weightlifting"], False, "/images/market_products/professional-bar-plp.jpg", "IWF CALIBRATED", "mk-badge-teal", "20.0 KG", 99),
    ("Technogym Straight Fixed Weight Barbell Kit", "Technogym", "training-gear", "barbells", 8499, 9999, 4.6, 320, 10, ["training-gear", "barbells", "fixed"], False, "/images/market_products/fixed-barbell-kit-plp.jpg", "PRE-ASSEMBLED", "mk-badge-gray", "KIT", 90),
    ("Technogym Competition Olympic Bumper Plates Set", "Technogym", "training-gear", "weight-plates", 14999, 17999, 4.9, 410, 6, ["training-gear", "weight-plates", "bumper", "strength"], True, "/images/market_products/bumper-plates-plp.jpg", "DEAD BOUNCE RUBBER", "mk-badge-blue", "SET 5-25KG", 98),
    ("Technogym 15kg Olympic Bumper Plate (Yellow)", "Technogym", "training-gear", "weight-plates", 3499, 4199, 4.8, 590, 18, ["training-gear", "weight-plates", "bumper", "15kg"], False, "/images/market_products/FF15-EQ-grey.jpg", "COMPETITION YELLOW", "mk-badge-teal", "15.0 KG", 95),
    ("Technogym Pro Urethane Grip Weight Plates Set", "Technogym", "training-gear", "weight-plates", 12999, 15499, 4.8, 680, 10, ["training-gear", "weight-plates", "urethane", "strength"], False, "/images/market_products/urethane-plates-plp.jpg", "QUAD-GRIP HANDLES", "mk-badge-gray", "SET 1.25-20KG", 96),
    ("Technogym Functional Power Sandbag 10kg", "Technogym", "training-gear", "functional", 4499, 5499, 4.7, 720, 14, ["training-gear", "functional", "power-bag", "strength"], False, "/images/market_products/A000-SB-grey.jpg", "BALLISTIC NYLON", "mk-badge-blue", "10.0 KG", 93),
    ("Technogym Multi-Functional Adjustable Workout Bench", "Technogym", "training-gear", "benches", 19999, 24999, 4.9, 310, 5, ["training-gear", "benches", "all-in-one", "strength"], True, "/images/market_products/Technogym_Bench_-_side_white_background.webp", "STORAGE INTEGRATED", "mk-badge-teal", "BENCH SYSTEM", 99),
    ("PowerMax GH-350 Multi-Station Home Gym", "PowerMax", "training-gear", "home-gym", 39999, 48999, 4.8, 180, 4, ["training-gear", "home-gym", "strength", "machine"], False, "/images/market_products/Untitled-1---20-10-2025-09-15-49.png", "150LBS WEIGHT STACK", "mk-badge-red", "HOME GYM", 97),
    ("PowerMax Fitness TDA-96 Motorized Treadmill", "PowerMax", "training-gear", "cardio", 32999, 39999, 4.7, 420, 6, ["training-gear", "cardio", "treadmill"], True, "/images/market_products/MAIN.png", "AUTO-INCLINE 15%", "mk-badge-blue", "MOTORIZED", 94),
    ("PowerMax Commercial Cross Trainer Elliptical", "PowerMax", "training-gear", "cardio", 27999, 34999, 4.6, 290, 8, ["training-gear", "cardio", "elliptical"], False, "/images/market_products/ELIPATICAL_.png", "MAGNETIC RESISTANCE", "mk-badge-gray", "CROSS TRAINER", 91),

    # Accessories
    ("PowerMax Gym Shaker Bottle 700ml (Black)", "PowerMax", "accessories", "shakers", 499, 699, 4.8, 2890, 80, ["accessories", "shakers", "hydration"], True, "/images/market_products/1604726193_product_07112020104633.jpg", "LEAK-PROOF TRITAN", "mk-badge-blue", "700 ML", 97),
    ("PowerMax Smart Bluetooth Body Fat Scale", "PowerMax", "accessories", "smart-devices", 1899, 2499, 4.7, 1540, 35, ["accessories", "smart-devices", "scale", "body-fat"], False, "/images/market_products/WEIGHT-SCales_.png", "13 BODY METRICS", "mk-badge-teal", "BLUETOOTH 5.0", 95),
    ("PowerMax Heavy-Duty Treadmill Equipment Mat", "PowerMax", "accessories", "mats", 1499, 1999, 4.6, 680, 25, ["accessories", "mats", "protection"], False, "/images/market_products/PMM-09-Option-1-White-Image-6a01a9e512746.jpg", "HIGH DENSITY PVC", "mk-badge-gray", "200X90 CM", 89),

    # Apparel
    ("Nike Air Zoom SuperRep Training Shoes", "Nike", "apparel", "shoes", 8999, 10999, 4.8, 1120, 18, ["apparel", "shoes", "training", "performance"], True, "/images/products/nike-air-zoom-superrep.svg", "ZOOM AIR CUSHION", "mk-badge-blue", "SIZE 10", 96),
    ("Under Armour HeatGear Compression Top", "Under Armour", "apparel", "compression", 1999, 2499, 4.7, 1450, 30, ["apparel", "compression", "training"], False, "/images/products/under-armour-compression-top.svg", "ANTI-ODOR TECH", "mk-badge-gray", "SIZE L", 93),
    ("GripTech Pro Leather Weightlifting Gloves", "GripTech", "accessories", "gloves", 799, 1099, 4.6, 920, 45, ["accessories", "gloves", "grip"], False, "/images/products/griptech-weightlifting-gloves.svg", "WRIST WRAP SUPPORT", "mk-badge-blue", "PAIR", 91),
]


SLUG_MAP = {
    "BioAbsorb Whey Protein & Gold Standard Combo 1kg": "whey-protein-isolate-2kg",
    "Pure Micronized Creatine Monohydrate 250g": "creatine-monohydrate-250g",
    "Micronized Creatine 500g": "micronized-creatine-500g",
    "PowerMax Gym Shaker Bottle 700ml (Black)": "steel-shaker-bottle-700ml",
    "Vitamin D3 + K2 Bone & Muscle Health 60ct": "vitamin-d3-plus-k2-60ct",
}


def _slugify(name: str) -> str:
    if name in SLUG_MAP:
        return SLUG_MAP[name]
    normalized = (
        name.lower()
        .replace("&", "and")
        .replace("+", " plus ")
        .replace(",", "")
        .replace(".", "")
        .replace("'", "")
        .replace("/", " or ")
        .replace("(", "")
        .replace(")", "")
    )
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


from .catalog_data import PRODUCTS_84


def seed_if_empty(force_reset: bool = False) -> int:
    """Insert categories + products (84 unique catalog items).

    Returns the number of products inserted.
    """
    repository._ready()
    products = repository.get_products_collection()
    categories = repository.get_categories_collection()

    if force_reset:
        products.delete_many({})
        categories.delete_many({})

    if products.count_documents({}) > 0 and not force_reset:
        return 0

    now = datetime.now(timezone.utc)
    for category in _CATEGORIES:
        categories.update_one(
            {"slug": category["slug"]},
            {"$set": {**category, "is_active": True, "updated_at": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    seen: set[str] = set()
    base = datetime.now(timezone.utc)
    catalog = PRODUCTS_84

    for index, item in enumerate(catalog):
        name = item["name"]
        slug = item.get("slug") or _slugify(name)
        if slug in seen:
            raise RuntimeError("Duplicate product slug generated: {0}".format(slug))
        seen.add(slug)
        created_at = base - timedelta(minutes=len(catalog) - index)

        price = int(item["price"])
        mrp = int(item.get("mrp") or item.get("original_price") or price)
        image_urls = item.get("image_urls") or []
        thumbnail = item.get("thumbnail") or (image_urls[0] if image_urls else "")

        doc = {
            "slug": slug,
            "name": name,
            "brand": item["brand"],
            "category": item["category"],
            "subcategory": item.get("subcategory", ""),
            "product_type": item.get("product_type", "general"),
            "description": item.get("description") or _description(item["brand"], name, item["category"]),
            "price": price,
            "original_price": mrp,
            "discount_percentage": item.get("discount_percentage") or _discount(price, mrp),
            "image_urls": image_urls,
            "thumbnail": thumbnail,
            "tags": item.get("tags") or [],
            "goal_tags": item.get("goal_tags") or [],
            "rating": float(item.get("rating", 4.5)),
            "review_count": int(item.get("review_count", 100)),
            "stock_quantity": int(item.get("stock_quantity", 20)),
            "is_active": True,
            "is_deal": bool(item.get("is_deal", False)),
            "badge": item.get("badge") or "",
            "badge_color": item.get("badge_color") or "mk-badge-blue",
            "weight_label": item.get("weight_label") or "",
            "ai_match": item.get("ai_match"),
            "flavor_options": item.get("flavor_options") or [],
            "size_options": item.get("size_options") or [],
            "weight_options": item.get("weight_options") or [],
            "variants": item.get("variants") or [],
            "specifications": item.get("specifications") or {},
            "nutrition_facts": item.get("nutrition_facts") or [],
            "highlights": item.get("highlights") or [],
            "synergy_stack": item.get("synergy_stack") or [],
            "target_benefit": item.get("target_benefit") or "",
            "benefits": item.get("benefits") or [],
            "usage": item.get("usage") or "",
            "ingredients": item.get("ingredients") or [],
            "created_at": created_at,
            "updated_at": created_at,
        }
        products.insert_one(doc)

    logger.info("Market seeded: %d categories, %d products", len(_CATEGORIES), len(catalog))
    return len(catalog)


def _discount(price: int, mrp: int) -> int:
    if mrp <= 0:
        return 0
    return round(((mrp - price) / mrp) * 100)


def _description(brand: str, name: str, category: str) -> str:
    return (
        "{0} {1} — a premium {2} essential verified by the PoseAI training team."
        .format(brand, name, category.replace("-", " "))
    )


def backfill_presentational() -> int:
    """Idempotent presentational backfill for existing catalogs."""
    repository._ready()
    products = repository.get_products_collection()
    total = products.count_documents({})
    if total == 0:
        return 0

    docs = list(products.find({}).sort([("_id", 1)]))
    timestamps = [doc.get("created_at") for doc in docs if doc.get("created_at")]
    uniform = len(timestamps) > 1 and (max(timestamps) - min(timestamps)) <= timedelta(seconds=2)
    base = datetime.now(timezone.utc)
    updated = 0
    for index, doc in enumerate(docs):
        fields: dict[str, Any] = {}
        if uniform:
            fields["created_at"] = base - timedelta(minutes=len(docs) - index)
            fields["updated_at"] = base
        if not doc.get("description"):
            fields["description"] = _description(
                str(doc.get("brand") or ""),
                str(doc.get("name") or ""),
                str(doc.get("category") or ""),
            )
        if fields:
            products.update_one({"_id": doc["_id"]}, {"$set": fields})
            updated += 1
    if updated:
        logger.info("Market presentational backfill updated %d products", updated)
    return updated


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    reset = "--reset" in sys.argv
    inserted = seed_if_empty(force_reset=reset)
    message = "Catalog reset & seeded. Products: {0}".format(inserted) if reset else "Catalog already seeded or newly seeded ({0} items).".format(inserted)
    logger.info("Market seed complete — %s", message)