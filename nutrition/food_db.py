"""
PoseAI Nutrition Intelligence System — Food Database
====================================================
Comprehensive catalog of authentic Indian foods, traditional meals,
and global fitness staples with precise macronutrients, serving units,
food-quality classifications, and processing levels.
"""

from __future__ import annotations

import re
from typing import Any, Optional

FOOD_DATABASE: list[dict[str, Any]] = [
    # ── Indian Breads & Grains ─────────────────────────────────────────
    {
        "id": "roti_chapati",
        "name": "Roti / Chapati",
        "category": "indian_bread",
        "aliases": ["roti", "chapati", "phulka", "fulka", "wheat roti", "atta roti", "flatbread"],
        "serving_unit": "piece",
        "default_serving_qty": 2,
        "estimated_weight_g": 70,  # ~35g per roti
        "per_unit": {
            "calories_kcal": 104,
            "protein_g": 3.4,
            "carbs_g": 22.0,
            "fat_g": 0.8,
            "fiber_g": 2.8,
            "sugar_g": 0.3,
            "sodium_mg": 95,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Whole wheat grain rich in complex carbohydrates and dietary fiber",
                "Low in saturated fats and refined sugars",
            ],
        },
    },
    {
        "id": "plain_naan",
        "name": "Butter / Plain Naan",
        "category": "indian_bread",
        "aliases": ["naan", "butter naan", "garlic naan", "tandoori naan"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 110,
        "per_unit": {
            "calories_kcal": 280,
            "protein_g": 8.5,
            "carbs_g": 48.0,
            "fat_g": 6.8,
            "fiber_g": 2.1,
            "sugar_g": 3.2,
            "sodium_mg": 410,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": [
                "Refined flour (maida) base with added dairy fats",
                "Higher glycemic index and moderate sodium content",
            ],
        },
    },
    {
        "id": "paratha_aloo",
        "name": "Aloo Paratha",
        "category": "indian_bread",
        "aliases": ["paratha", "aloo paratha", "stuffed paratha", "methi paratha", "gobi paratha"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 140,
        "per_unit": {
            "calories_kcal": 290,
            "protein_g": 6.2,
            "carbs_g": 42.0,
            "fat_g": 11.5,
            "fiber_g": 3.8,
            "sugar_g": 1.5,
            "sodium_mg": 380,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": [
                "Traditional whole wheat bread with spiced potato filling cooked in oil/ghee",
                "Moderate calorie density with balanced carbohydrates",
            ],
        },
    },
    {
        "id": "steamed_rice",
        "name": "Steamed White Rice",
        "category": "indian_main",
        "aliases": ["rice", "white rice", "steamed rice", "boiled rice", "chawal"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 180,
        "per_unit": {
            "calories_kcal": 230,
            "protein_g": 4.5,
            "carbs_g": 50.0,
            "fat_g": 0.5,
            "fiber_g": 1.0,
            "sugar_g": 0.1,
            "sodium_mg": 5,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Easily digestible energy source rich in complex starch",
                "Virtually zero sodium and minimal dietary fat",
            ],
        },
    },
    {
        "id": "brown_rice",
        "name": "Brown Rice",
        "category": "indian_main",
        "aliases": ["brown rice", "whole grain rice"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 180,
        "per_unit": {
            "calories_kcal": 218,
            "protein_g": 5.0,
            "carbs_g": 45.8,
            "fat_g": 1.6,
            "fiber_g": 3.5,
            "sugar_g": 0.7,
            "sodium_mg": 4,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Intact bran layer providing steady glucose release",
                "Rich in magnesium, phosphorus, and B-vitamins",
            ],
        },
    },
    {
        "id": "biryani_chicken",
        "name": "Chicken Biryani",
        "category": "indian_main",
        "aliases": ["biryani", "chicken biryani", "dum biryani", "hyderabadi biryani"],
        "serving_unit": "plate",
        "default_serving_qty": 1,
        "estimated_weight_g": 350,
        "per_unit": {
            "calories_kcal": 560,
            "protein_g": 32.0,
            "carbs_g": 66.0,
            "fat_g": 18.5,
            "fiber_g": 3.2,
            "sugar_g": 2.4,
            "sodium_mg": 780,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "processed",
            "reasons": [
                "Excellent high-protein complete meal with seasoned chicken and basmati rice",
                "Spices (turmeric, cardamom, saffron) offer antioxidant properties; moderate sodium and fats",
            ],
        },
    },
    {
        "id": "biryani_veg",
        "name": "Veg Biryani / Pulao",
        "category": "indian_main",
        "aliases": ["veg biryani", "vegetable biryani", "pulao", "veg pulao", "peas pulao"],
        "serving_unit": "plate",
        "default_serving_qty": 1,
        "estimated_weight_g": 300,
        "per_unit": {
            "calories_kcal": 410,
            "protein_g": 9.5,
            "carbs_g": 72.0,
            "fat_g": 10.0,
            "fiber_g": 5.4,
            "sugar_g": 3.6,
            "sodium_mg": 620,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "processed",
            "reasons": [
                "Fragrant basmati rice infused with garden vegetables and aromatic spices",
                "Good fiber content with modest fat levels",
            ],
        },
    },

    # ── Indian Dals & Legumes ──────────────────────────────────────────
    {
        "id": "dal_tadka",
        "name": "Dal Tadka / Yellow Dal",
        "category": "indian_dal",
        "aliases": ["dal", "daal", "dal tadka", "yellow dal", "toor dal", "moong dal", "dal fry"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 200,
        "per_unit": {
            "calories_kcal": 180,
            "protein_g": 11.5,
            "carbs_g": 26.0,
            "fat_g": 4.2,
            "fiber_g": 6.8,
            "sugar_g": 1.2,
            "sodium_mg": 460,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Plant-based protein source high in soluble fiber and iron",
                "Low saturated fat with digestive spices like cumin and asafoetida",
            ],
        },
    },
    {
        "id": "dal_makhani",
        "name": "Dal Makhani",
        "category": "indian_dal",
        "aliases": ["dal makhani", "makhani dal", "black dal", "urad dal makhani"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 220,
        "per_unit": {
            "calories_kcal": 320,
            "protein_g": 12.0,
            "carbs_g": 32.0,
            "fat_g": 16.5,
            "fiber_g": 7.5,
            "sugar_g": 2.8,
            "sodium_mg": 590,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": [
                "Rich slow-cooked black lentils with whole butter and dairy cream",
                "High protein and fiber, balanced by higher saturated fats",
            ],
        },
    },
    {
        "id": "chole_curry",
        "name": "Chole / Chickpea Curry",
        "category": "indian_dal",
        "aliases": ["chole", "chana masala", "chole masala", "kabuli chana", "chickpea curry"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 220,
        "per_unit": {
            "calories_kcal": 270,
            "protein_g": 13.5,
            "carbs_g": 38.0,
            "fat_g": 7.8,
            "fiber_g": 9.2,
            "sugar_g": 3.4,
            "sodium_mg": 560,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Rich in dietary fiber and legume-based plant protein",
                "Promotes sustained satiety and supports cardiovascular wellness",
            ],
        },
    },
    {
        "id": "rajma_masala",
        "name": "Rajma / Kidney Bean Curry",
        "category": "indian_dal",
        "aliases": ["rajma", "rajma chawal", "rajma masala", "kidney beans curry"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 220,
        "per_unit": {
            "calories_kcal": 250,
            "protein_g": 14.0,
            "carbs_g": 36.0,
            "fat_g": 6.2,
            "fiber_g": 10.5,
            "sugar_g": 2.9,
            "sodium_mg": 520,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Exceptional fiber density (10.5g) supporting gut health and glycemic control",
                "High bioavailable plant protein and complex starches",
            ],
        },
    },

    # ── Indian Curries & Proteins ──────────────────────────────────────
    {
        "id": "paneer_curry",
        "name": "Paneer Butter Masala / Shahi Paneer",
        "category": "indian_main",
        "aliases": ["paneer", "paneer butter masala", "shahi paneer", "paneer tikka masala", "kadai paneer", "matar paneer"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 230,
        "per_unit": {
            "calories_kcal": 360,
            "protein_g": 16.5,
            "carbs_g": 14.0,
            "fat_g": 28.0,
            "fiber_g": 3.0,
            "sugar_g": 6.5,
            "sodium_mg": 680,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "processed",
            "reasons": [
                "Vegetarian whole protein with calcium and leucine",
                "Rich creamy gravy; pair with roti or rice for balanced macros",
            ],
        },
    },
    {
        "id": "paneer_raw_grilled",
        "name": "Grilled / Raw Paneer Cubes",
        "category": "indian_protein",
        "aliases": ["grilled paneer", "raw paneer", "paneer tikka", "tandoori paneer"],
        "serving_unit": "serving",
        "default_serving_qty": 1,
        "estimated_weight_g": 120,
        "per_unit": {
            "calories_kcal": 280,
            "protein_g": 20.4,
            "carbs_g": 4.8,
            "fat_g": 20.0,
            "fiber_g": 0.8,
            "sugar_g": 2.1,
            "sodium_mg": 280,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Concentrated vegetarian protein source packed with calcium",
                "Low in carbohydrates, ideal for muscle synthesis and recovery",
            ],
        },
    },
    {
        "id": "chicken_curry",
        "name": "Chicken Curry / Tariwala Chicken",
        "category": "indian_main",
        "aliases": ["chicken curry", "chicken gravy", "murgh curry", "home style chicken curry"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 250,
        "per_unit": {
            "calories_kcal": 310,
            "protein_g": 34.0,
            "carbs_g": 8.5,
            "fat_g": 15.0,
            "fiber_g": 2.2,
            "sugar_g": 2.8,
            "sodium_mg": 640,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "High biological value lean poultry protein with complete amino acid profile",
                "Traditional onion-tomato-ginger-garlic gravy rich in allicin and gingerols",
            ],
        },
    },
    {
        "id": "butter_chicken",
        "name": "Butter Chicken / Murgh Makhani",
        "category": "indian_main",
        "aliases": ["butter chicken", "murgh makhani", "chicken makhani"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 250,
        "per_unit": {
            "calories_kcal": 440,
            "protein_g": 30.0,
            "carbs_g": 16.0,
            "fat_g": 28.0,
            "fiber_g": 2.5,
            "sugar_g": 7.0,
            "sodium_mg": 760,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": [
                "Tender chicken in tomato, cream, and butter sauce",
                "Substantial protein content balanced by elevated saturated fats and sodium",
            ],
        },
    },
    {
        "id": "palak_paneer",
        "name": "Palak Paneer",
        "category": "indian_main",
        "aliases": ["palak paneer", "saag paneer", "spinach paneer"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 230,
        "per_unit": {
            "calories_kcal": 280,
            "protein_g": 17.0,
            "carbs_g": 10.0,
            "fat_g": 19.5,
            "fiber_g": 5.2,
            "sugar_g": 2.5,
            "sodium_mg": 540,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Iron and folate rich spinach pureed with calcium-dense cottage cheese",
                "Excellent micronutrient density and dietary fiber",
            ],
        },
    },
    {
        "id": "indian_thali",
        "name": "Complete Indian Thali",
        "category": "indian_main",
        "aliases": ["thali", "indian thali", "veg thali", "special thali", "deluxe thali"],
        "serving_unit": "serving",
        "default_serving_qty": 1,
        "estimated_weight_g": 600,
        "per_unit": {
            "calories_kcal": 780,
            "protein_g": 28.0,
            "carbs_g": 110.0,
            "fat_g": 25.0,
            "fiber_g": 14.0,
            "sugar_g": 12.0,
            "sodium_mg": 1120,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "processed",
            "reasons": [
                "Diverse nutrient matrix combining grains, lentils, fresh vegetables, curd, and salad",
                "High fiber and comprehensive micronutrient distribution across all food groups",
            ],
        },
    },

    # ── South Indian & Breakfast Classics ──────────────────────────────
    {
        "id": "idli_sambar",
        "name": "Idli with Sambar & Chutney",
        "category": "indian_breakfast",
        "aliases": ["idli", "idly", "idlis", "steamed idli", "sambar idli"],
        "serving_unit": "plate",
        "default_serving_qty": 2,  # 2 idlis with sambar
        "estimated_weight_g": 200,
        "per_unit": {
            "calories_kcal": 190,
            "protein_g": 6.8,
            "carbs_g": 38.0,
            "fat_g": 1.5,
            "fiber_g": 3.8,
            "sugar_g": 2.1,
            "sodium_mg": 480,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Naturally fermented rice and lentil batter steamed without added fats",
                "Fermentation enhances bio-availability of vitamin B and aids digestion",
            ],
        },
    },
    {
        "id": "dosa_masala",
        "name": "Masala Dosa",
        "category": "indian_breakfast",
        "aliases": ["dosa", "masala dosa", "plain dosa", "crispy dosa", "ghee roast dosa"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 220,
        "per_unit": {
            "calories_kcal": 340,
            "protein_g": 7.5,
            "carbs_g": 48.0,
            "fat_g": 13.0,
            "fiber_g": 4.0,
            "sugar_g": 2.5,
            "sodium_mg": 580,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "processed",
            "reasons": [
                "Fermented savory crepe with spiced potato filling",
                "High satisfaction index; moderate calories and healthy prebiotic fermentation",
            ],
        },
    },
    {
        "id": "poha",
        "name": "Poha / Kanda Poha",
        "category": "indian_breakfast",
        "aliases": ["poha", "kanda poha", "flattened rice", "batata poha"],
        "serving_unit": "plate",
        "default_serving_qty": 1,
        "estimated_weight_g": 200,
        "per_unit": {
            "calories_kcal": 260,
            "protein_g": 5.8,
            "carbs_g": 46.0,
            "fat_g": 6.5,
            "fiber_g": 3.2,
            "sugar_g": 2.0,
            "sodium_mg": 380,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Iron-rich flattened rice tempered with peanuts, turmeric, and fresh coriander",
                "Light on digestion, providing clean sustained carbohydrate fuel",
            ],
        },
    },
    {
        "id": "upma",
        "name": "Rava Upma",
        "category": "indian_breakfast",
        "aliases": ["upma", "rava upma", "sooji upma", "vegetable upma"],
        "serving_unit": "plate",
        "default_serving_qty": 1,
        "estimated_weight_g": 200,
        "per_unit": {
            "calories_kcal": 240,
            "protein_g": 6.0,
            "carbs_g": 42.0,
            "fat_g": 5.8,
            "fiber_g": 3.5,
            "sugar_g": 1.8,
            "sodium_mg": 390,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Toasted semolina infused with curry leaves, mustard seeds, and veggies",
                "Clean energizing breakfast with balanced complex carbohydrates",
            ],
        },
    },

    # ── Popular Street Foods & Snacks ──────────────────────────────────
    {
        "id": "vada_pav",
        "name": "Vada Pav",
        "category": "indian_snack",
        "aliases": ["vada pav", "wada pav", "batata vada pav", "bombay burger"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 140,
        "per_unit": {
            "calories_kcal": 290,
            "protein_g": 6.2,
            "carbs_g": 42.0,
            "fat_g": 11.0,
            "fiber_g": 2.8,
            "sugar_g": 3.0,
            "sodium_mg": 460,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": [
                "Deep-fried spiced potato fritter in refined flour bun with dry garlic chutney",
                "High energy density; best enjoyed as an occasional treat",
            ],
        },
    },
    {
        "id": "samosa",
        "name": "Samosa (Potato)",
        "category": "indian_snack",
        "aliases": ["samosa", "singara", "punjabi samosa", "aloo samosa"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 90,
        "per_unit": {
            "calories_kcal": 260,
            "protein_g": 4.5,
            "carbs_g": 32.0,
            "fat_g": 13.5,
            "fiber_g": 2.2,
            "sugar_g": 1.8,
            "sodium_mg": 380,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": [
                "Deep-fried pastry shell containing spiced potato and green peas",
                "High proportion of saturated frying oils and refined carbohydrates",
            ],
        },
    },
    {
        "id": "pav_bhaji",
        "name": "Pav Bhaji",
        "category": "indian_snack",
        "aliases": ["pav bhaji", "bhaji pav", "amul pav bhaji"],
        "serving_unit": "plate",
        "default_serving_qty": 1,  # 2 buttered pavs + bhaji
        "estimated_weight_g": 350,
        "per_unit": {
            "calories_kcal": 490,
            "protein_g": 11.0,
            "carbs_g": 65.0,
            "fat_g": 21.0,
            "fiber_g": 7.0,
            "sugar_g": 8.0,
            "sodium_mg": 890,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": [
                "Vegetable mash (potatoes, tomatoes, peas, cauliflower) with buttered bread",
                "Abundant vegetable fiber balanced by elevated butter fat and sodium",
            ],
        },
    },
    {
        "id": "misal_pav",
        "name": "Misal Pav",
        "category": "indian_snack",
        "aliases": ["misal pav", "puneri misal", "kolhapuri misal", "spicy misal"],
        "serving_unit": "plate",
        "default_serving_qty": 1,
        "estimated_weight_g": 320,
        "per_unit": {
            "calories_kcal": 460,
            "protein_g": 15.0,
            "carbs_g": 62.0,
            "fat_g": 17.5,
            "fiber_g": 8.5,
            "sugar_g": 4.5,
            "sodium_mg": 920,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": [
                "Sprouted moth beans in spicy curry topped with crunchy farsan and served with pav",
                "Good protein and fiber from legumes, with higher sodium and farsan fats",
            ],
        },
    },

    # ── Global Fitness & Whole Food Staples ────────────────────────────
    {
        "id": "boiled_eggs",
        "name": "Boiled Eggs (Whole)",
        "category": "fitness_staple",
        "aliases": ["egg", "boiled egg", "hard boiled egg", "eggs", "boiled eggs"],
        "serving_unit": "piece",
        "default_serving_qty": 2,
        "estimated_weight_g": 100,  # ~50g per egg
        "per_unit": {
            "calories_kcal": 72,
            "protein_g": 6.3,
            "carbs_g": 0.4,
            "fat_g": 4.8,
            "fiber_g": 0.0,
            "sugar_g": 0.2,
            "sodium_mg": 71,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Gold-standard biological protein with all 9 essential amino acids",
                "Packed with choline, lutein, and fat-soluble vitamins (A, D, E, B12)",
            ],
        },
    },
    {
        "id": "egg_whites",
        "name": "Egg Whites (Cooked)",
        "category": "fitness_staple",
        "aliases": ["egg white", "egg whites", "boiled egg white"],
        "serving_unit": "piece",
        "default_serving_qty": 4,
        "estimated_weight_g": 132,
        "per_unit": {
            "calories_kcal": 17,
            "protein_g": 3.6,
            "carbs_g": 0.2,
            "fat_g": 0.1,
            "fiber_g": 0.0,
            "sugar_g": 0.2,
            "sodium_mg": 55,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Pure bio-available albumin protein with near-zero fat and cholesterol",
                "Ideal for lean muscle preservation during caloric deficits",
            ],
        },
    },
    {
        "id": "chicken_breast_grilled",
        "name": "Grilled Chicken Breast",
        "category": "fitness_staple",
        "aliases": ["chicken breast", "grilled chicken", "boiled chicken", "baked chicken", "roast chicken"],
        "serving_unit": "serving",
        "default_serving_qty": 1,
        "estimated_weight_g": 150,
        "per_unit": {
            "calories_kcal": 248,
            "protein_g": 46.5,
            "carbs_g": 0.0,
            "fat_g": 5.4,
            "fiber_g": 0.0,
            "sugar_g": 0.0,
            "sodium_mg": 130,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Ultra-high protein-to-calorie ratio; cornerstone of athletic nutrition",
                "Abundant in niacin, vitamin B6, phosphorus, and selenium",
            ],
        },
    },
    {
        "id": "oatmeal_porridge",
        "name": "Oatmeal / Rolled Oats with Water or Milk",
        "category": "fitness_staple",
        "aliases": ["oats", "oatmeal", "porridge", "rolled oats", "overnight oats"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 240,
        "per_unit": {
            "calories_kcal": 210,
            "protein_g": 8.2,
            "carbs_g": 38.0,
            "fat_g": 3.8,
            "fiber_g": 5.5,
            "sugar_g": 2.0,
            "sodium_mg": 85,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Loaded with beta-glucan soluble fiber to support cardiovascular and metabolic health",
                "Slow-burning low-glycemic breakfast fuel",
            ],
        },
    },
    {
        "id": "whey_protein_shake",
        "name": "Whey Protein Shake (1 Scoop)",
        "category": "fitness_staple",
        "aliases": ["protein shake", "whey protein", "whey", "protein drink", "isolate"],
        "serving_unit": "scoop",
        "default_serving_qty": 1,
        "estimated_weight_g": 32,
        "per_unit": {
            "calories_kcal": 125,
            "protein_g": 25.0,
            "carbs_g": 2.5,
            "fat_g": 1.5,
            "fiber_g": 0.5,
            "sugar_g": 1.0,
            "sodium_mg": 110,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "processed",
            "reasons": [
                "Rapidly absorbed micro-filtered whey protein rich in BCAAs and leucine",
                "Optimizes post-exercise muscle protein synthesis",
            ],
        },
    },
    {
        "id": "greek_yogurt",
        "name": "Greek Yogurt / Hung Curd",
        "category": "fitness_staple",
        "aliases": ["greek yogurt", "curd", "dahi", "hung curd", "yogurt"],
        "serving_unit": "cup",
        "default_serving_qty": 1,
        "estimated_weight_g": 170,
        "per_unit": {
            "calories_kcal": 130,
            "protein_g": 17.0,
            "carbs_g": 6.0,
            "fat_g": 4.0,
            "fiber_g": 0.0,
            "sugar_g": 5.0,
            "sodium_mg": 65,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Strained dairy packed with double the protein of conventional yogurt",
                "Natural live active probiotic cultures aiding gut microbiome health",
            ],
        },
    },
    {
        "id": "peanut_butter",
        "name": "Peanut Butter",
        "category": "fitness_staple",
        "aliases": ["peanut butter", "pb", "nut butter"],
        "serving_unit": "tbsp",
        "default_serving_qty": 2,  # 32g
        "estimated_weight_g": 32,
        "per_unit": {
            "calories_kcal": 95,  # per 1 tbsp (16g)
            "protein_g": 4.0,
            "carbs_g": 3.5,
            "fat_g": 8.0,
            "fiber_g": 1.1,
            "sugar_g": 1.5,
            "sodium_mg": 70,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Heart-healthy monounsaturated fats, vitamin E, and magnesium",
                "High caloric density; excellent for healthy caloric surplus",
            ],
        },
    },
    {
        "id": "salmon_fish",
        "name": "Grilled Salmon / Fish Fillet",
        "category": "fitness_staple",
        "aliases": ["salmon", "fish", "grilled fish", "fish fillet", "tuna"],
        "serving_unit": "fillet",
        "default_serving_qty": 1,
        "estimated_weight_g": 170,
        "per_unit": {
            "calories_kcal": 340,
            "protein_g": 38.0,
            "carbs_g": 0.0,
            "fat_g": 20.0,
            "fiber_g": 0.0,
            "sugar_g": 0.0,
            "sodium_mg": 95,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Premier source of marine Omega-3 fatty acids (EPA & DHA) fighting inflammation",
                "High-potency lean protein accelerating joint and tendon recovery",
            ],
        },
    },
    {
        "id": "banana",
        "name": "Fresh Banana",
        "category": "fruit",
        "aliases": ["banana", "kela", "bananas"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 118,
        "per_unit": {
            "calories_kcal": 105,
            "protein_g": 1.3,
            "carbs_g": 27.0,
            "fat_g": 0.3,
            "fiber_g": 3.1,
            "sugar_g": 14.4,
            "sodium_mg": 1,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Natural fast-acting carbohydrate ideal for pre-workout glycogen replenishment",
                "Rich in potassium to mitigate muscle cramping and maintain electrolyte equilibrium",
            ],
        },
    },
    {
        "id": "apple",
        "name": "Fresh Apple",
        "category": "fruit",
        "aliases": ["apple", "seb", "apples", "green apple"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 182,
        "per_unit": {
            "calories_kcal": 95,
            "protein_g": 0.5,
            "carbs_g": 25.0,
            "fat_g": 0.3,
            "fiber_g": 4.4,
            "sugar_g": 19.0,
            "sodium_mg": 2,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Abundant pectin prebiotic fiber and quercetin antioxidants",
                "Hydrating and promotes satiety with low glycemic impact",
            ],
        },
    },
    {
        "id": "mixed_nuts",
        "name": "Almonds & Mixed Nuts",
        "category": "fitness_staple",
        "aliases": ["nuts", "almonds", "badam", "walnuts", "cashews", "mixed nuts"],
        "serving_unit": "handful",
        "default_serving_qty": 1,
        "estimated_weight_g": 30,
        "per_unit": {
            "calories_kcal": 175,
            "protein_g": 6.0,
            "carbs_g": 5.5,
            "fat_g": 15.2,
            "fiber_g": 3.0,
            "sugar_g": 1.2,
            "sodium_mg": 2,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Plant polyphenols, vitamin E, and essential polyunsaturated fats",
                "Supports cellular membrane integrity and brain health",
            ],
        },
    },
    {
        "id": "green_salad",
        "name": "Fresh Garden Green Salad",
        "category": "vegetable",
        "aliases": ["salad", "green salad", "cucumber", "veggie salad", "lettuce", "broccoli"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 150,
        "per_unit": {
            "calories_kcal": 45,
            "protein_g": 2.5,
            "carbs_g": 8.0,
            "fat_g": 0.4,
            "fiber_g": 3.8,
            "sugar_g": 3.2,
            "sodium_mg": 35,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": [
                "Exceptional micronutrient density with minimal caloric impact",
                "Cruciferous compounds, sulforaphane, and abundant hydration",
            ],
        },
    },
    {
        "id": "chocolate_bar",
        "name": "Chocolate Bar / Candy",
        "category": "snack",
        "aliases": ["chocolate", "chocolate bar", "candy", "milk chocolate", "sweet"],
        "serving_unit": "bar",
        "default_serving_qty": 1,
        "estimated_weight_g": 45,
        "per_unit": {
            "calories_kcal": 235,
            "protein_g": 3.0,
            "carbs_g": 26.0,
            "fat_g": 13.0,
            "fiber_g": 1.4,
            "sugar_g": 24.0,
            "sodium_mg": 45,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": [
                "High refined added sugar and saturated cocoa/dairy butter",
                "Elevated caloric density with limited micronutrient value",
            ],
        },
    },
    # ── Additional Indian Specialties & Street Foods ───────────────────
    {
        "id": "dabeli",
        "name": "Kutchi Dabeli",
        "category": "indian_snack",
        "aliases": ["dabeli", "kutchi dabeli", "double roti"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 130,
        "per_unit": {
            "calories_kcal": 240,
            "protein_g": 4.5,
            "carbs_g": 38.0,
            "fat_g": 8.5,
            "fiber_g": 2.5,
            "sugar_g": 5.0,
            "sodium_mg": 390,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": ["Spiced potato filling in pav garnished with sev and pomegranate"],
        },
    },
    {
        "id": "batata_vada",
        "name": "Batata Vada (Plain)",
        "category": "indian_snack",
        "aliases": ["batata vada", "aloo bonda", "potato vada", "vada patty"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 85,
        "per_unit": {
            "calories_kcal": 180,
            "protein_g": 3.2,
            "carbs_g": 22.0,
            "fat_g": 9.0,
            "fiber_g": 1.8,
            "sugar_g": 1.2,
            "sodium_mg": 310,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": ["Fried gram-flour batter coated mashed potato patty"],
        },
    },
    {
        "id": "kachori",
        "name": "Kachori (Khasta / Pyaaz)",
        "category": "indian_snack",
        "aliases": ["kachori", "khasta kachori", "pyaaz kachori", "dal kachori"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 90,
        "per_unit": {
            "calories_kcal": 220,
            "protein_g": 4.0,
            "carbs_g": 24.0,
            "fat_g": 12.0,
            "fiber_g": 2.0,
            "sugar_g": 1.0,
            "sodium_mg": 340,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["Deep-fried spiced lentil or onion flaky pastry"],
        },
    },
    {
        "id": "medu_vada",
        "name": "Medu Vada",
        "category": "indian_snack",
        "aliases": ["medu vada", "ulundu vadai", "vada", "sambar vada"],
        "serving_unit": "piece",
        "default_serving_qty": 2,
        "estimated_weight_g": 70,
        "per_unit": {
            "calories_kcal": 165,
            "protein_g": 5.2,
            "carbs_g": 16.0,
            "fat_g": 9.5,
            "fiber_g": 2.2,
            "sugar_g": 0.5,
            "sodium_mg": 280,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": ["Crispy fried black gram (urad dal) fritter with coconut chutney"],
        },
    },
    {
        "id": "sabudana_khichdi",
        "name": "Sabudana Khichdi",
        "category": "indian_main",
        "aliases": ["sabudana khichdi", "sago khichdi", "sabudana"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 200,
        "per_unit": {
            "calories_kcal": 340,
            "protein_g": 4.5,
            "carbs_g": 52.0,
            "fat_g": 13.0,
            "fiber_g": 1.5,
            "sugar_g": 1.8,
            "sodium_mg": 320,
        },
        "food_quality": {
            "classification": "balanced",
            "processing_level": "minimally_processed",
            "reasons": ["Tapioca pearls sautéed with roasted peanuts, cumin, and green chillies"],
        },
    },
    {
        "id": "bhel_puri",
        "name": "Bhel Puri",
        "category": "indian_chaat",
        "aliases": ["bhel puri", "bhelpuri", "bhel", "sukha bhel"],
        "serving_unit": "plate",
        "default_serving_qty": 1,
        "estimated_weight_g": 160,
        "per_unit": {
            "calories_kcal": 210,
            "protein_g": 4.8,
            "carbs_g": 39.0,
            "fat_g": 4.5,
            "fiber_g": 3.2,
            "sugar_g": 6.0,
            "sodium_mg": 480,
        },
        "food_quality": {
            "classification": "balanced",
            "processing_level": "processed",
            "reasons": ["Puffed rice tossed with chopped onions, tomatoes, and tangy tamarind chutney"],
        },
    },
    {
        "id": "sev_puri",
        "name": "Sev Puri",
        "category": "indian_chaat",
        "aliases": ["sev puri", "sev batata puri", "sevpuri"],
        "serving_unit": "plate",
        "default_serving_qty": 1,
        "estimated_weight_g": 160,
        "per_unit": {
            "calories_kcal": 240,
            "protein_g": 4.2,
            "carbs_g": 34.0,
            "fat_g": 10.0,
            "fiber_g": 2.8,
            "sugar_g": 5.5,
            "sodium_mg": 510,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": ["Crispy papdi discs topped with spiced potatoes, chutneys, and fine sev"],
        },
    },
    {
        "id": "pani_puri",
        "name": "Pani Puri / Golgappa",
        "category": "indian_chaat",
        "aliases": ["pani puri", "golgappa", "puchka", "panipuri", "gupchup"],
        "serving_unit": "plate (6 pcs)",
        "default_serving_qty": 1,
        "estimated_weight_g": 180,
        "per_unit": {
            "calories_kcal": 160,
            "protein_g": 3.0,
            "carbs_g": 28.0,
            "fat_g": 4.0,
            "fiber_g": 2.0,
            "sugar_g": 3.0,
            "sodium_mg": 460,
        },
        "food_quality": {
            "classification": "balanced",
            "processing_level": "processed",
            "reasons": ["Hollow crisp puris filled with spiced potato/chickpeas and mint-flavoured water"],
        },
    },
    {
        "id": "dahi_puri",
        "name": "Dahi Puri",
        "category": "indian_chaat",
        "aliases": ["dahi puri", "dahi batata puri", "dahipuri"],
        "serving_unit": "plate (6 pcs)",
        "default_serving_qty": 1,
        "estimated_weight_g": 210,
        "per_unit": {
            "calories_kcal": 260,
            "protein_g": 6.0,
            "carbs_g": 36.0,
            "fat_g": 10.5,
            "fiber_g": 2.5,
            "sugar_g": 8.0,
            "sodium_mg": 420,
        },
        "food_quality": {
            "classification": "balanced",
            "processing_level": "processed",
            "reasons": ["Crispy puris filled with potatoes and topped with sweetened chilled yogurt and chutneys"],
        },
    },
    {
        "id": "chole_bhature",
        "name": "Chole Bhature",
        "category": "indian_main",
        "aliases": ["chole bhature", "chana bhatura", "bhatura"],
        "serving_unit": "plate (2 bhature + chole)",
        "default_serving_qty": 1,
        "estimated_weight_g": 380,
        "per_unit": {
            "calories_kcal": 580,
            "protein_g": 14.0,
            "carbs_g": 68.0,
            "fat_g": 28.0,
            "fiber_g": 8.0,
            "sugar_g": 4.0,
            "sodium_mg": 780,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "processed",
            "reasons": ["Deep-fried leavened sourdough bread served with spiced chickpea curry"],
        },
    },
    {
        "id": "veg_pulao",
        "name": "Vegetable Pulao",
        "category": "indian_main",
        "aliases": ["pulao", "veg pulao", "pilaf", "peas pulao"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 220,
        "per_unit": {
            "calories_kcal": 260,
            "protein_g": 5.5,
            "carbs_g": 48.0,
            "fat_g": 6.0,
            "fiber_g": 3.5,
            "sugar_g": 2.0,
            "sodium_mg": 310,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": ["Basmati rice cooked with whole spices, green peas, carrots, and beans"],
        },
    },
    {
        "id": "paneer_tikka",
        "name": "Paneer Tikka (Grilled)",
        "category": "indian_starter",
        "aliases": ["paneer tikka", "tandoori paneer tikka", "grilled paneer"],
        "serving_unit": "plate (6 skewers/cubes)",
        "default_serving_qty": 1,
        "estimated_weight_g": 180,
        "per_unit": {
            "calories_kcal": 280,
            "protein_g": 18.0,
            "carbs_g": 10.0,
            "fat_g": 19.0,
            "fiber_g": 2.5,
            "sugar_g": 3.0,
            "sodium_mg": 420,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": ["Marinated cottage cheese cubes roasted in tandoor with bell peppers and onions"],
        },
    },
    {
        "id": "chicken_tikka",
        "name": "Chicken Tikka (Boneless)",
        "category": "indian_starter",
        "aliases": ["chicken tikka", "tandoori chicken tikka", "murgh tikka"],
        "serving_unit": "plate (6 pieces)",
        "default_serving_qty": 1,
        "estimated_weight_g": 180,
        "per_unit": {
            "calories_kcal": 220,
            "protein_g": 28.0,
            "carbs_g": 4.0,
            "fat_g": 10.0,
            "fiber_g": 1.0,
            "sugar_g": 1.5,
            "sodium_mg": 460,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": ["Lean chicken breast cubes marinated in yogurt and Indian spices, clay-oven grilled"],
        },
    },
    {
        "id": "tandoori_chicken",
        "name": "Tandoori Chicken (Quarter/Leg)",
        "category": "indian_main",
        "aliases": ["tandoori chicken", "tandoori leg", "roasted chicken"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 170,
        "per_unit": {
            "calories_kcal": 260,
            "protein_g": 32.0,
            "carbs_g": 3.0,
            "fat_g": 13.0,
            "fiber_g": 1.0,
            "sugar_g": 1.0,
            "sodium_mg": 490,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": ["Bone-in chicken marinated in spiced yogurt and roasted in tandoor without added oil"],
        },
    },
    {
        "id": "egg_curry",
        "name": "Egg Curry (2 Eggs)",
        "category": "indian_curry",
        "aliases": ["egg curry", "anda curry", "egg masala", "anda masala"],
        "serving_unit": "bowl",
        "default_serving_qty": 1,
        "estimated_weight_g": 220,
        "per_unit": {
            "calories_kcal": 240,
            "protein_g": 14.0,
            "carbs_g": 10.0,
            "fat_g": 16.0,
            "fiber_g": 2.0,
            "sugar_g": 2.5,
            "sodium_mg": 520,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": ["Whole hard-boiled eggs simmered in an aromatic onion-tomato spiced gravy"],
        },
    },
    {
        "id": "dal_chawal",
        "name": "Dal Chawal Combo",
        "category": "indian_main",
        "aliases": ["dal chawal", "dal rice", "chawal dal"],
        "serving_unit": "plate",
        "default_serving_qty": 1,
        "estimated_weight_g": 350,
        "per_unit": {
            "calories_kcal": 380,
            "protein_g": 12.0,
            "carbs_g": 68.0,
            "fat_g": 6.5,
            "fiber_g": 6.0,
            "sugar_g": 2.0,
            "sodium_mg": 420,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": ["Classic wholesome comfort combination of steamed rice and yellow lentil dal"],
        },
    },
    {
        "id": "rajma_chawal",
        "name": "Rajma Chawal Combo",
        "category": "indian_main",
        "aliases": ["rajma chawal", "rajma rice", "chawal rajma"],
        "serving_unit": "plate",
        "default_serving_qty": 1,
        "estimated_weight_g": 360,
        "per_unit": {
            "calories_kcal": 420,
            "protein_g": 14.0,
            "carbs_g": 72.0,
            "fat_g": 8.0,
            "fiber_g": 8.5,
            "sugar_g": 3.0,
            "sodium_mg": 510,
        },
        "food_quality": {
            "classification": "nutrient_dense",
            "processing_level": "minimally_processed",
            "reasons": ["Complete plant protein meal combining kidney bean curry with steamed basmati rice"],
        },
    },
    {
        "id": "gulab_jamun",
        "name": "Gulab Jamun",
        "category": "indian_sweet",
        "aliases": ["gulab jamun", "jamun", "sweet"],
        "serving_unit": "piece (2 pcs)",
        "default_serving_qty": 1,
        "estimated_weight_g": 70,
        "per_unit": {
            "calories_kcal": 280,
            "protein_g": 4.0,
            "carbs_g": 44.0,
            "fat_g": 10.0,
            "fiber_g": 0.5,
            "sugar_g": 36.0,
            "sodium_mg": 85,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["Fried khoya milk-solid dumplings soaked in rose-cardamom sugar syrup"],
        },
    },
    {
        "id": "pizza",
        "canonical_id": "pizza",
        "name": "Pizza",
        "category": "Fast Food",
        "aliases": ["pizza", "cheese pizza", "veg pizza", "margherita"],
        "serving_unit": "slice",
        "default_serving_qty": 1,
        "estimated_weight_g": 105,
        "per_unit": {
            "calories_kcal": 285,
            "protein_g": 12.0,
            "carbs_g": 35.0,
            "fat_g": 10.5,
            "fiber_g": 2.2,
            "sugar_g": 3.8,
            "sodium_mg": 560,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["Refined flour crust with cheese and tomato sauce"],
        },
    },
    {
        "id": "burger",
        "canonical_id": "burger",
        "name": "Burger",
        "category": "Fast Food",
        "aliases": ["burger", "veggie burger", "chicken burger", "hamburger"],
        "serving_unit": "piece",
        "default_serving_qty": 1,
        "estimated_weight_g": 150,
        "per_unit": {
            "calories_kcal": 360,
            "protein_g": 15.0,
            "carbs_g": 40.0,
            "fat_g": 16.0,
            "fiber_g": 3.0,
            "sugar_g": 5.0,
            "sodium_mg": 680,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["Bun sandwich with patty and condiments"],
        },
    },
    {
        "id": "french_fries",
        "canonical_id": "french_fries",
        "name": "French Fries",
        "category": "Fast Food",
        "aliases": ["french fries", "fries", "potato fries"],
        "serving_unit": "serving",
        "default_serving_qty": 1,
        "estimated_weight_g": 115,
        "per_unit": {
            "calories_kcal": 310,
            "protein_g": 3.5,
            "carbs_g": 41.0,
            "fat_g": 15.0,
            "fiber_g": 3.8,
            "sugar_g": 0.5,
            "sodium_mg": 280,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["Deep-fried potato sticks with salt"],
        },
    },
    {
        "id": "packaged_chips",
        "canonical_id": "packaged_chips",
        "name": "Packaged Potato Chips",
        "category": "Packaged Snacks",
        "aliases": ["packaged chips", "potato chips", "lays", "crisps"],
        "serving_unit": "packet (30g)",
        "default_serving_qty": 1,
        "estimated_weight_g": 30,
        "per_unit": {
            "calories_kcal": 160,
            "protein_g": 2.0,
            "carbs_g": 15.0,
            "fat_g": 10.0,
            "fiber_g": 1.2,
            "sugar_g": 1.0,
            "sodium_mg": 210,
        },
        "food_quality": {
            "classification": "occasional",
            "processing_level": "ultra_processed",
            "reasons": ["Deep-fried packaged snack high in sodium and vegetable oils"],
        },
    },
]

for f in FOOD_DATABASE:
    f["canonical_id"] = f.get("canonical_id") or f["id"]
    if "nutrition" not in f:
        f["nutrition"] = f.get("per_unit", {})

# Quick lookup index by ID and canonical ID
_FOOD_BY_ID = {f["id"]: f for f in FOOD_DATABASE}
for f in FOOD_DATABASE:
    _FOOD_BY_ID[f["canonical_id"]] = f


def get_food_by_id(food_id: str) -> Optional[dict[str, Any]]:
    """Fetch food record by unique ID or canonical ID."""
    return _FOOD_BY_ID.get(food_id)


def resolve_canonical_food(name_or_query: str) -> Optional[dict[str, Any]]:
    """
    Resolve any candidate food name or alias to its verified canonical food record.
    Matches exact ID, exact alias/name, or highest-ranking token match.
    """
    if not name_or_query:
        return None
    raw = str(name_or_query).strip()
    q = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    if not q:
        return None

    # 1. Direct ID match
    clean_id = re.sub(r"[^a-z0-9]+", "_", q)
    if clean_id in _FOOD_BY_ID:
        return _FOOD_BY_ID[clean_id]

    # 2. Exact name or alias match
    for f in FOOD_DATABASE:
        if q == f["name"].lower():
            return f
        for a in f.get("aliases", []):
            if q == a.lower():
                return f

    # 3. Substring / Token matching
    matches = search_foods(q, limit=1)
    if matches:
        return matches[0]

    return None


def search_foods(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search foods by name, alias, or category with ranking.
    Returns matched food items sorted by relevance.
    """
    if not query or not query.strip():
        return FOOD_DATABASE[:limit]

    q = query.strip().lower()
    exact_matches: list[dict[str, Any]] = []
    prefix_matches: list[dict[str, Any]] = []
    partial_matches: list[dict[str, Any]] = []

    for food in FOOD_DATABASE:
        id_lower = food.get("id", "").lower()
        name_lower = food["name"].lower()
        aliases = [a.lower() for a in food.get("aliases", [])]

        if q == name_lower or q == id_lower or any(q == a for a in aliases):
            exact_matches.append(food)
        elif name_lower.startswith(q) or id_lower.startswith(q) or any(a.startswith(q) for a in aliases):
            prefix_matches.append(food)
        elif q in name_lower or q in id_lower or any(q in a for a in aliases) or q in food.get("category", ""):
            partial_matches.append(food)

    results = exact_matches + prefix_matches + partial_matches
    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for f in results:
        if f["id"] not in seen:
            seen.add(f["id"])
            deduped.append(f)
            if len(deduped) >= limit:
                break
    return deduped


def scale_nutrition(food: dict[str, Any], quantity: float = 1.0) -> dict[str, Any]:
    """
    Scale a food item's per_unit nutrition by the chosen serving quantity.
    Returns rounded, clean nutrition values.
    """
    qty = max(0.1, float(quantity))
    base = food.get("per_unit", {})
    est_weight = food.get("estimated_weight_g")
    
    scaled_weight = round(est_weight * qty) if est_weight else None

    return {
        "calories_kcal": int(round(base.get("calories_kcal", 0) * qty)),
        "protein_g": round(base.get("protein_g", 0) * qty, 1),
        "carbs_g": round(base.get("carbs_g", 0) * qty, 1),
        "fat_g": round(base.get("fat_g", 0) * qty, 1),
        "fiber_g": round(base.get("fiber_g", 0) * qty, 1),
        "sugar_g": round(base.get("sugar_g", 0) * qty, 1),
        "sodium_mg": int(round(base.get("sodium_mg", 0) * qty)),
        "serving_unit": food.get("serving_unit", "serving"),
        "serving_qty": qty,
        "estimated_weight_g": scaled_weight,
    }
