/**
 * PoseAI Fitness Market — All Products Catalog Controller
 * Pure Vanilla JavaScript (No Frameworks, No Libraries)
 * Full State Management, Cart Drawer, Filtering, Steppers & Backend Connection
 */
"use strict";

(function () {
  // ── 48 Products Catalog Data (Exact Reference Fidelity) ─────────────────────
  var ALL_PRODUCTS = [
    // PAGE 1 (Items 1 to 12 - Exactly matching reference screenshot)
    {
      id: "prod-1",
      name: "Gold Standard 100% Whey Double Rich Chocolate",
      brand: "OPTIMUM NUTRITION",
      variant: "1.0 KG",
      category: "whey",
      group: "supplements",
      price: 3299,
      mrp: 3899,
      discount: 15,
      rating: 4.8,
      reviews: 3420,
      in_stock: true,
      badge: "AI MATCH 98%",
      badge_class: "badge-dark-teal",
      image: "/images/products/optimum-nutrition-gold-standard.svg",
      is_favorite: false,
    },
    {
      id: "prod-2",
      name: "Biozyme Performance Whey Protein - Kesar...",
      brand: "MUSCLEBLAZE",
      variant: "1.0 KG",
      category: "whey",
      group: "supplements",
      price: 2499,
      mrp: 3299,
      discount: 24,
      rating: 4.7,
      reviews: 1890,
      in_stock: true,
      badge: "ENHANCED ABSORPTION",
      badge_class: "badge-blue",
      image: "/images/products/muscleblaze-biozyme-whey.svg",
      is_favorite: false,
    },
    {
      id: "prod-3",
      name: "Creapure Micronized Pure Creatine Monohydrate",
      brand: "FAST&UP",
      variant: "250 G",
      category: "creatine",
      group: "supplements",
      price: 1149,
      mrp: 1499,
      discount: 23,
      rating: 4.9,
      reviews: 840,
      in_stock: true,
      badge: "CREAPURE® GERMAN",
      badge_class: "badge-blue",
      image: "/images/products/creapure-creatine-monohydrate.svg",
      is_favorite: true, // Pre-filled red heart in reference screenshot
    },
    {
      id: "prod-4",
      name: "Biomech Heavy Duty 18\" Powerlifting Wrist Wraps",
      brand: "BOLDFIT",
      variant: "PAIR",
      category: "gear",
      group: "supplements",
      price: 899,
      mrp: 1299,
      discount: 31,
      rating: 4.6,
      reviews: 4120,
      in_stock: true,
      badge: "INJURY PREVENTION",
      badge_class: "badge-dark-teal",
      image: "/images/products/poseai-biomech-wrist-wraps.svg",
      is_favorite: false,
    },
    {
      id: "prod-5",
      name: "WrathX Extreme Pre-Workout - Fruit Punch Blast",
      brand: "MUSCLEBLAZE",
      variant: "30 SERVINGS",
      category: "pre-workout",
      group: "supplements",
      price: 1699,
      mrp: 2299,
      discount: 26,
      rating: 4.5,
      reviews: 980,
      in_stock: true,
      badge: "300MG CAFFEINE",
      badge_class: "badge-red",
      image: "/images/products/cellucor-c4-preworkout.svg",
      is_favorite: false,
    },
    {
      id: "prod-6",
      name: "Grid Trigger Point Deep Tissue Foam Roller",
      brand: "BOLDFIT",
      variant: "45 CM",
      category: "gear",
      group: "supplements",
      price: 799,
      mrp: 1499,
      discount: 46,
      rating: 4.8,
      reviews: 3210,
      in_stock: true,
      badge: "RECOVERY",
      badge_class: "badge-blue",
      image: "/images/products/poseai-recovery-foam-roller.svg",
      is_favorite: false,
    },
    {
      id: "prod-7",
      name: "Dri-FIT Biomech Form Visualizer Training Tee",
      brand: "NIKE TRAINING",
      variant: "SIZE L",
      category: "apparel",
      group: "supplements",
      price: 2195,
      mrp: 2895,
      discount: 24,
      rating: 4.9,
      reviews: 630,
      in_stock: true,
      badge: "CAMERA TRACK OPTIC",
      badge_class: "badge-dark-teal",
      image: "/images/products/nike-air-zoom-superrep.svg",
      is_favorite: false,
    },
    {
      id: "prod-8",
      name: "Cold Processed Pure Whey Isolate - Raw Unflavored",
      brand: "THE WHOLE TRUTH",
      variant: "1.0 KG",
      category: "whey",
      group: "supplements",
      price: 2999,
      mrp: 3499,
      discount: 14,
      rating: 4.8,
      reviews: 1110,
      in_stock: true,
      badge: "ZERO SUCRALOSE",
      badge_class: "badge-dark-teal",
      image: "/images/products/the-whole-truth-raw-whey.svg",
      is_favorite: false,
    },
    {
      id: "prod-9",
      name: "Reload Hydration & Energy Electrolytes - Citrus Lime",
      brand: "FAST&UP",
      variant: "20 TABS",
      category: "electrolytes",
      group: "wellness",
      price: 299,
      mrp: 390,
      discount: 23,
      rating: 4.6,
      reviews: 5310,
      in_stock: true,
      badge: "HYDRATION",
      badge_class: "badge-blue",
      image: "/images/products/fastup-reload-electrolytes.svg",
      is_favorite: false,
    },
    {
      id: "prod-10",
      name: "Power Resistance Loop Bands for Assisted Pull-ups",
      brand: "BOLDFIT",
      variant: "PACK OF 5",
      category: "gear",
      group: "supplements",
      price: 1499,
      mrp: 2999,
      discount: 50,
      rating: 4.7,
      reviews: 3180,
      in_stock: true,
      badge: "5-RESISTANCE SET",
      badge_class: "badge-green",
      image: "/images/products/boldfit-resistance-bands.svg",
      is_favorite: false,
    },
    {
      id: "prod-11",
      name: "Men's Weightlifting Gloves with Dynamic Palm Grip",
      brand: "UNDER ARMOUR",
      variant: "PAIR",
      category: "gear",
      group: "supplements",
      price: 1799,
      mrp: 2499,
      discount: 28,
      rating: 4.7,
      reviews: 740,
      in_stock: true,
      badge: "MICRO-PERF LEATHER",
      badge_class: "badge-blue",
      image: "/images/products/griptech-weightlifting-gloves.svg",
      is_favorite: false,
    },
    {
      id: "prod-12",
      name: "Magnesio Chelate Pure Magnesium Glycinate...",
      brand: "FAST&UP",
      variant: "60 VEG CAPSULES",
      category: "vitamins",
      group: "wellness",
      price: 649,
      mrp: 850,
      discount: 24,
      rating: 4.9,
      reviews: 1430,
      in_stock: true,
      badge: "CNS RECOVERY",
      badge_class: "badge-dark-teal",
      image: "/images/products/fastup-magnesium-glycinate.svg",
      is_favorite: false,
    },

    // PAGE 2 (Items 13 to 24)
    {
      id: "prod-13",
      name: "Mass Gainer XXL High Calorie Anabolic Matrix",
      brand: "MUSCLEBLAZE",
      variant: "3.0 KG",
      category: "whey",
      group: "supplements",
      price: 4499,
      mrp: 5299,
      discount: 15,
      rating: 4.5,
      reviews: 980,
      in_stock: true,
      badge: "LABDOOR CERTIFIED",
      badge_class: "badge-dark-teal",
      image: "/images/products/muscleblaze-raw-whey-isolate.svg",
      is_favorite: false,
    },
    {
      id: "prod-14",
      name: "Organic Pea & Brown Rice Plant Protein Blend",
      brand: "THE WHOLE TRUTH",
      variant: "1.0 KG",
      category: "whey",
      group: "supplements",
      price: 2599,
      mrp: 3199,
      discount: 19,
      rating: 4.5,
      reviews: 720,
      in_stock: true,
      badge: "VEGAN APPROVED",
      badge_class: "badge-green",
      image: "/images/products/cosmix-plant-protein.svg",
      is_favorite: false,
    },
    {
      id: "prod-15",
      name: "BCAA 2:1:1 Intra-Workout Muscle Recovery Powder",
      brand: "OPTIMUM NUTRITION",
      variant: "400 G",
      category: "bcaa",
      group: "supplements",
      price: 1699,
      mrp: 2099,
      discount: 19,
      rating: 4.4,
      reviews: 620,
      in_stock: true,
      badge: "INTRA WORKOUT",
      badge_class: "badge-blue",
      image: "/images/products/fastup-reload-electrolytes.svg",
      is_favorite: false,
    },
    {
      id: "prod-16",
      name: "Daily Multivitamin Formula with 23 Essential Micronutrients",
      brand: "FAST&UP",
      variant: "60 TABLETS",
      category: "vitamins",
      group: "wellness",
      price: 649,
      mrp: 849,
      discount: 23,
      rating: 4.6,
      reviews: 2210,
      in_stock: true,
      badge: "DAILY MULTI",
      badge_class: "badge-blue",
      image: "/images/products/fastup-magnesium-glycinate.svg",
      is_favorite: false,
    },
    {
      id: "prod-17",
      name: "C4 Sport Explosive Energy Pre-Workout Formula",
      brand: "BOLDFIT",
      variant: "30 SERVINGS",
      category: "pre-workout",
      group: "supplements",
      price: 1399,
      mrp: 1699,
      discount: 18,
      rating: 4.5,
      reviews: 960,
      in_stock: true,
      badge: "EXPLOSIVE ENERGY",
      badge_class: "badge-red",
      image: "/images/products/cellucor-c4-preworkout.svg",
      is_favorite: false,
    },
    {
      id: "prod-18",
      name: "Triple Strength Omega-3 Fish Oil 1000mg EPA/DHA",
      brand: "THE WHOLE TRUTH",
      variant: "90 SOFTGELS",
      category: "vitamins",
      group: "wellness",
      price: 849,
      mrp: 1099,
      discount: 23,
      rating: 4.4,
      reviews: 980,
      in_stock: true,
      badge: "TRIPLE STRENGTH",
      badge_class: "badge-blue",
      image: "/images/products/fastup-magnesium-glycinate.svg",
      is_favorite: false,
    },
    {
      id: "prod-19",
      name: "Smart Stainless Thermal Hydration Shaker 700ml",
      brand: "BOLDFIT",
      variant: "700 ML",
      category: "gear",
      group: "supplements",
      price: 899,
      mrp: 1199,
      discount: 25,
      rating: 4.8,
      reviews: 2240,
      in_stock: true,
      badge: "SMART HYDRATE",
      badge_class: "badge-blue",
      image: "/images/products/poseai-smart-thermal-shaker.svg",
      is_favorite: false,
    },
    {
      id: "prod-20",
      name: "EAAs 9 Essential Amino Acids Instant Hydration Formula",
      brand: "MUSCLEBLAZE",
      variant: "300 G",
      category: "bcaa",
      group: "supplements",
      price: 1899,
      mrp: 2299,
      discount: 17,
      rating: 4.5,
      reviews: 480,
      in_stock: true,
      badge: "FULL SPECTRUM",
      badge_class: "badge-blue",
      image: "/images/products/fastup-reload-electrolytes.svg",
      is_favorite: false,
    },
    {
      id: "prod-21",
      name: "Liquid Grip Chalk for Deadlifts and Calisthenics",
      brand: "BOLDFIT",
      variant: "250 ML",
      category: "gear",
      group: "supplements",
      price: 449,
      mrp: 699,
      discount: 36,
      rating: 4.9,
      reviews: 840,
      in_stock: true,
      badge: "GRIP AID",
      badge_class: "badge-blue",
      image: "/images/products/apex-grip-liquid-chalk.svg",
      is_favorite: false,
    },
    {
      id: "prod-22",
      name: "Performance Dual-Layer Compression Leggings",
      brand: "UNDER ARMOUR",
      variant: "SIZE M",
      category: "apparel",
      group: "supplements",
      price: 1899,
      mrp: 2499,
      discount: 24,
      rating: 4.7,
      reviews: 740,
      in_stock: true,
      badge: "RECOVERY WEAR",
      badge_class: "badge-indigo",
      image: "/images/products/under-armour-compression-top.svg",
      is_favorite: false,
    },
    {
      id: "prod-23",
      name: "Slow-Release Micellar Casein Night Shake",
      brand: "THE WHOLE TRUTH",
      variant: "1.0 KG",
      category: "whey",
      group: "supplements",
      price: 3199,
      mrp: 3799,
      discount: 16,
      rating: 4.4,
      reviews: 410,
      in_stock: true,
      badge: "8-HR DIGESTION",
      badge_class: "badge-dark",
      image: "/images/products/the-whole-truth-raw-whey.svg",
      is_favorite: false,
    },
    {
      id: "prod-24",
      name: "High-Density Dual-Texture Acupressure Yoga Mat 6mm",
      brand: "BOLDFIT",
      variant: "6MM DUAL",
      category: "gear",
      group: "supplements",
      price: 1499,
      mrp: 1899,
      discount: 21,
      rating: 4.4,
      reviews: 860,
      in_stock: true,
      badge: "ALIGNMENT GUIDE",
      badge_class: "badge-dark-teal",
      image: "/images/products/poseai-ultra-grip-mat.svg",
      is_favorite: false,
    },

    // PAGE 3 (Items 25 to 36)
    {
      id: "prod-25",
      name: "Nitric Oxide Pump Matrix Citrulline Malate 2:1",
      brand: "MUSCLEBLAZE",
      variant: "200 G",
      category: "pre-workout",
      group: "supplements",
      price: 899,
      mrp: 1199,
      discount: 25,
      rating: 4.6,
      reviews: 510,
      in_stock: true,
      badge: "VASODILATION",
      badge_class: "badge-red",
      image: "/images/products/cellucor-c4-preworkout.svg",
      is_favorite: false,
    },
    {
      id: "prod-26",
      name: "KSM-66 Organic Ashwagandha Root Extract 600mg",
      brand: "FAST&UP",
      variant: "60 CAPSULES",
      category: "vitamins",
      group: "wellness",
      price: 899,
      mrp: 1199,
      discount: 25,
      rating: 4.5,
      reviews: 720,
      in_stock: true,
      badge: "CORTISOL CONTROL",
      badge_class: "badge-blue",
      image: "/images/products/fastup-magnesium-glycinate.svg",
      is_favorite: false,
    },
    {
      id: "prod-27",
      name: "Hydrolyzed Type I & III Marine Collagen Peptides",
      brand: "THE WHOLE TRUTH",
      variant: "400 G",
      category: "vitamins",
      group: "wellness",
      price: 1999,
      mrp: 2499,
      discount: 20,
      rating: 4.4,
      reviews: 410,
      in_stock: true,
      badge: "JOINT SUPPORT",
      badge_class: "badge-dark-teal",
      image: "/images/products/plantfuel-pea-rice-protein.svg",
      is_favorite: false,
    },
    {
      id: "prod-28",
      name: "Cast Iron Hexagonal Dumbbell Set with Contoured Grip",
      brand: "BOLDFIT",
      variant: "PAIR 10KG",
      category: "gear",
      group: "supplements",
      price: 3499,
      mrp: 4499,
      discount: 22,
      rating: 4.7,
      reviews: 490,
      in_stock: true,
      badge: "HEAVY DUTY",
      badge_class: "badge-dark",
      image: "/images/products/bowflex-hex-dumbbells.svg",
      is_favorite: false,
    },
    {
      id: "prod-29",
      name: "High Performance Deep Muscle Percussion Massage Gun",
      brand: "BOLDFIT",
      variant: "6 HEADS",
      category: "gear",
      group: "supplements",
      price: 4999,
      mrp: 6999,
      discount: 28,
      rating: 4.8,
      reviews: 1320,
      in_stock: true,
      badge: "PERCUSSION THERAPY",
      badge_class: "badge-blue",
      image: "/images/products/hyperice-massage-gun.svg",
      is_favorite: false,
    },
    {
      id: "prod-30",
      name: "Organic Green Superfood Detox & Gut Health Blend",
      brand: "FAST&UP",
      variant: "300 G",
      category: "vitamins",
      group: "wellness",
      price: 1649,
      mrp: 1999,
      discount: 17,
      rating: 4.2,
      reviews: 660,
      in_stock: true,
      badge: "SUPERFOOD",
      badge_class: "badge-green",
      image: "/images/products/cosmix-plant-protein.svg",
      is_favorite: false,
    },
    {
      id: "prod-31",
      name: "Thermal Fleece Athletic Workout Hoodie",
      brand: "NIKE TRAINING",
      variant: "SIZE XL",
      category: "apparel",
      group: "supplements",
      price: 2499,
      mrp: 2999,
      discount: 16,
      rating: 4.2,
      reviews: 150,
      in_stock: true,
      badge: "THERMAL WEAVE",
      badge_class: "badge-dark",
      image: "/images/products/under-armour-compression-top.svg",
      is_favorite: false,
    },
    {
      id: "prod-32",
      name: "Tart Cherry Concentrated Melatonin Sleep Matrix",
      brand: "FAST&UP",
      variant: "60 CAPSULES",
      category: "electrolytes",
      group: "wellness",
      price: 1599,
      mrp: 1999,
      discount: 20,
      rating: 4.3,
      reviews: 300,
      in_stock: true,
      badge: "DEEP SLEEP",
      badge_class: "badge-indigo",
      image: "/images/products/fastup-magnesium-glycinate.svg",
      is_favorite: false,
    },
    {
      id: "prod-33",
      name: "Bio-Response Leather Lever Powerlifting Belt 10mm",
      brand: "BOLDFIT",
      variant: "SIZE L",
      category: "gear",
      group: "supplements",
      price: 2499,
      mrp: 3299,
      discount: 24,
      rating: 4.6,
      reviews: 700,
      in_stock: true,
      badge: "IPF COMPLIANT",
      badge_class: "badge-dark",
      image: "/images/products/poseai-biomech-wrist-wraps.svg",
      is_favorite: false,
    },
    {
      id: "prod-34",
      name: "Pure Micronized L-Glutamine Amino Acid",
      brand: "OPTIMUM NUTRITION",
      variant: "300 G",
      category: "bcaa",
      group: "supplements",
      price: 1299,
      mrp: 1599,
      discount: 18,
      rating: 4.5,
      reviews: 380,
      in_stock: true,
      badge: "GUT IMMUNITY",
      badge_class: "badge-blue",
      image: "/images/products/fastup-reload-electrolytes.svg",
      is_favorite: false,
    },
    {
      id: "prod-35",
      name: "High Intensity Pro Cardio Speed Jump Rope",
      brand: "BOLDFIT",
      variant: "ADJUSTABLE",
      category: "gear",
      group: "supplements",
      price: 399,
      mrp: 699,
      discount: 43,
      rating: 4.5,
      reviews: 890,
      in_stock: true,
      badge: "BALL BEARING",
      badge_class: "badge-blue",
      image: "/images/products/bowflex-hex-dumbbells.svg",
      is_favorite: false,
    },
    {
      id: "prod-36",
      name: "Clean Nutrition High Protein Energy Bar Box of 12",
      brand: "THE WHOLE TRUTH",
      variant: "BOX OF 12",
      category: "whey",
      group: "supplements",
      price: 999,
      mrp: 1200,
      discount: 16,
      rating: 4.7,
      reviews: 1420,
      in_stock: true,
      badge: "NO ADDED SUGAR",
      badge_class: "badge-green",
      image: "/images/products/yogabar-protein-bars.svg",
      is_favorite: false,
    },

    // PAGE 4 (Items 37 to 48)
    {
      id: "prod-37",
      name: "Electrolyte Effervescent Hydration Tablets Watermelon",
      brand: "FAST&UP",
      variant: "20 TABS",
      category: "electrolytes",
      group: "wellness",
      price: 299,
      mrp: 390,
      discount: 23,
      rating: 4.6,
      reviews: 1800,
      in_stock: true,
      badge: "ZERO SUGAR",
      badge_class: "badge-blue",
      image: "/images/products/fastup-reload-electrolytes.svg",
      is_favorite: false,
    },
    {
      id: "prod-38",
      name: "Flex Movement 4-Way Stretch Training Shorts",
      brand: "NIKE TRAINING",
      variant: "SIZE M",
      category: "apparel",
      group: "supplements",
      price: 1599,
      mrp: 2199,
      discount: 27,
      rating: 4.3,
      reviews: 380,
      in_stock: true,
      badge: "4-WAY FLEX",
      badge_class: "badge-dark",
      image: "/images/products/under-armour-compression-top.svg",
      is_favorite: false,
    },
    {
      id: "prod-39",
      name: "Vitamin D3 60,000 IU + Vitamin K2 MK-7",
      brand: "FAST&UP",
      variant: "60 CAPSULES",
      category: "vitamins",
      group: "wellness",
      price: 549,
      mrp: 699,
      discount: 21,
      rating: 4.5,
      reviews: 1480,
      in_stock: true,
      badge: "BONE DENSITY",
      badge_class: "badge-blue",
      image: "/images/products/fastup-magnesium-glycinate.svg",
      is_favorite: false,
    },
    {
      id: "prod-40",
      name: "Hydrolyzed Whey Protein Ultra Clean Formula",
      brand: "OPTIMUM NUTRITION",
      variant: "1.5 KG",
      category: "whey",
      group: "supplements",
      price: 4999,
      mrp: 5999,
      discount: 16,
      rating: 4.9,
      reviews: 1200,
      in_stock: true,
      badge: "FAST DIGEST",
      badge_class: "badge-dark-teal",
      image: "/images/products/optimum-nutrition-gold-standard.svg",
      is_favorite: false,
    },
    {
      id: "prod-41",
      name: "Caffeine 200mg + L-Theanine 100mg Focus Blend",
      brand: "MUSCLEBLAZE",
      variant: "60 TABLETS",
      category: "pre-workout",
      group: "supplements",
      price: 499,
      mrp: 699,
      discount: 28,
      rating: 4.3,
      reviews: 350,
      in_stock: true,
      badge: "CLEAN FOCUS",
      badge_class: "badge-blue",
      image: "/images/products/cellucor-c4-preworkout.svg",
      is_favorite: false,
    },
    {
      id: "prod-42",
      name: "Deep Tissue Acupressure Lacrosse Massage Balls",
      brand: "BOLDFIT",
      variant: "PACK OF 2",
      category: "gear",
      group: "supplements",
      price: 499,
      mrp: 649,
      discount: 23,
      rating: 4.4,
      reviews: 310,
      in_stock: true,
      badge: "TRIGGER POINT",
      badge_class: "badge-dark",
      image: "/images/products/poseai-recovery-foam-roller.svg",
      is_favorite: false,
    },
    {
      id: "prod-43",
      name: "Zinc Chelate + Natural Vitamin C Immune Shield",
      brand: "FAST&UP",
      variant: "60 TABS",
      category: "vitamins",
      group: "wellness",
      price: 499,
      mrp: 649,
      discount: 23,
      rating: 4.2,
      reviews: 430,
      in_stock: true,
      badge: "IMMUNITY",
      badge_class: "badge-green",
      image: "/images/products/fastup-magnesium-glycinate.svg",
      is_favorite: false,
    },
    {
      id: "prod-44",
      name: "Joint Shield Glucosamine Chondroitin & MSM Complex",
      brand: "THE WHOLE TRUTH",
      variant: "60 TABLETS",
      category: "vitamins",
      group: "wellness",
      price: 1199,
      mrp: 1499,
      discount: 20,
      rating: 4.1,
      reviews: 380,
      in_stock: true,
      badge: "CARTILAGE CARE",
      badge_class: "badge-dark-teal",
      image: "/images/products/fastup-magnesium-glycinate.svg",
      is_favorite: false,
    },
    {
      id: "prod-45",
      name: "Anabolic Creatine HCl High Absorption Capsules",
      brand: "MUSCLEBLAZE",
      variant: "120 CAPSULES",
      category: "creatine",
      group: "supplements",
      price: 1899,
      mrp: 2299,
      discount: 17,
      rating: 4.3,
      reviews: 540,
      in_stock: true,
      badge: "NO WATER BLOAT",
      badge_class: "badge-blue",
      image: "/images/products/creapure-creatine-monohydrate.svg",
      is_favorite: false,
    },
    {
      id: "prod-46",
      name: "Wind-Resistant High-Visibility Athletic Running Jacket",
      brand: "UNDER ARMOUR",
      variant: "SIZE L",
      category: "apparel",
      group: "supplements",
      price: 2899,
      mrp: 3599,
      discount: 19,
      rating: 4.5,
      reviews: 210,
      in_stock: true,
      badge: "WEATHER PROOF",
      badge_class: "badge-dark",
      image: "/images/products/under-armour-compression-top.svg",
      is_favorite: false,
    },
    {
      id: "prod-47",
      name: "50 Billion CFU Multi-Strain Probiotic Complex",
      brand: "THE WHOLE TRUTH",
      variant: "30 CAPSULES",
      category: "vitamins",
      group: "wellness",
      price: 1299,
      mrp: 1599,
      discount: 18,
      rating: 4.3,
      reviews: 320,
      in_stock: true,
      badge: "MICROBIOME",
      badge_class: "badge-green",
      image: "/images/products/fastup-magnesium-glycinate.svg",
      is_favorite: false,
    },
    {
      id: "prod-48",
      name: "Performance Arch Support Athletic Training Crew Socks",
      brand: "UNDER ARMOUR",
      variant: "PACK OF 6",
      category: "apparel",
      group: "supplements",
      price: 499,
      mrp: 699,
      discount: 28,
      rating: 4.3,
      reviews: 520,
      in_stock: true,
      badge: "CUSHION SUPPORT",
      badge_class: "badge-dark",
      image: "/images/products/under-armour-compression-top.svg",
      is_favorite: false,
    },
  ];

  // ── Cart State (Synced with Backend /api/market/cart) ─────────────────────
  var cartState = {};

  // ── Filter State ────────────────────────────────────────────────────────────
  var filterState = {
    search: "",
    inStockOnly: false,
    categories: [],
    brands: [],
    pricePreset: "all",
    priceMin: 0,
    priceMax: 10000,
    rating: "",
    discount: "",
    sort: "relevance",
    page: 1,
    limit: 12,
    dealsOnly: false,
  };

  // ── Helper Formatter ────────────────────────────────────────────────────────
  function formatRupees(amount) {
    var val = Number(amount) || 0;
    return "₹" + val.toLocaleString("en-IN");
  }

  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ── Read URL Query Parameters ───────────────────────────────────────────────
  function readUrlParams() {
    var params = new URLSearchParams(window.location.search);
    var q = (params.get("search") || params.get("q") || "").trim();
    if (q) filterState.search = q;

    var cat = params.get("category");
    if (cat) filterState.categories = cat.toLowerCase().split(",").filter(Boolean);

    var b = params.get("brands") || params.get("brand");
    if (b) filterState.brands = b.split(",").map(function (x) { return x.trim().toUpperCase(); }).filter(Boolean);

    if (params.get("in_stock") === "1" || params.get("in_stock") === "true") {
      filterState.inStockOnly = true;
    }

    if (params.get("min_price")) {
      filterState.priceMin = parseInt(params.get("min_price"), 10) || 0;
    }
    if (params.get("max_price")) {
      filterState.priceMax = parseInt(params.get("max_price"), 10) || 10000;
    }
    if (params.get("rating")) {
      filterState.rating = params.get("rating");
    }
    if (params.get("discount")) {
      filterState.discount = parseInt(params.get("discount"), 10) || "";
    }
    if (params.get("sort")) {
      filterState.sort = params.get("sort");
    }
    if (params.get("page")) {
      filterState.page = parseInt(params.get("page"), 10) || 1;
    }
    if (params.get("deals") === "true" || params.get("deal") === "1") {
      filterState.dealsOnly = true;
      filterState.discount = 20;
    }

    syncControlsToState();
  }

  function syncControlsToState() {
    var searchInput = document.getElementById("navSearchInput");
    if (searchInput) searchInput.value = filterState.search;

    var inStockSwitch = document.getElementById("inStockOnlyCheckbox");
    if (inStockSwitch) inStockSwitch.checked = filterState.inStockOnly;

    document.querySelectorAll("input[name='categoryFilter']").forEach(function (cb) {
      cb.checked = filterState.categories.indexOf(cb.value.toLowerCase()) !== -1;
    });

    document.querySelectorAll("input[name='brandFilter']").forEach(function (cb) {
      cb.checked = filterState.brands.indexOf(cb.value.toUpperCase()) !== -1;
    });

    var minInput = document.getElementById("filterPriceMinInput");
    var maxInput = document.getElementById("filterPriceMaxInput");
    var slider = document.getElementById("filterPriceSlider");
    if (minInput) minInput.value = filterState.priceMin > 0 ? filterState.priceMin : "";
    if (maxInput) maxInput.value = filterState.priceMax < 10000 ? filterState.priceMax : "";
    if (slider) slider.value = Math.min(filterState.priceMax, 10000);

    document.querySelectorAll("input[name='ratingRadio']").forEach(function (rb) {
      rb.checked = rb.value === filterState.rating;
    });

    document.querySelectorAll(".discount-chip").forEach(function (btn) {
      var d = parseInt(btn.getAttribute("data-discount"), 10);
      btn.classList.toggle("active", d === filterState.discount);
    });

    var sortSelect = document.getElementById("catalogSortSelect");
    if (sortSelect && filterState.sort) sortSelect.value = filterState.sort;

    var catBadge = document.getElementById("categorySectionBadge");
    if (catBadge) {
      catBadge.textContent = filterState.categories.length > 0 ? (filterState.categories.length + " Selected") : "All";
    }
  }

  function syncUrl() {
    var params = new URLSearchParams();
    if (filterState.search) params.set("search", filterState.search);
    if (filterState.categories && filterState.categories.length) params.set("category", filterState.categories.join(","));
    if (filterState.brands && filterState.brands.length) params.set("brands", filterState.brands.join(","));
    if (filterState.inStockOnly) params.set("in_stock", "1");
    if (filterState.priceMin > 0) params.set("min_price", filterState.priceMin);
    if (filterState.priceMax < 10000) params.set("max_price", filterState.priceMax);
    if (filterState.rating) params.set("rating", filterState.rating);
    if (filterState.discount) params.set("discount", filterState.discount);
    if (filterState.sort && filterState.sort !== "relevance") params.set("sort", filterState.sort);
    if (filterState.page > 1) params.set("page", filterState.page);

    var qs = params.toString();
    window.history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : ""));
  }

  // ── Backend API Sync (Seamless connection with Flask /api/market/*) ──────────
  function loadBackendProducts() {
    if (!window.MarketAPI || typeof window.MarketAPI.products !== "function") {
      renderActiveFilterChips();
      renderProductGrid();
      return;
    }

    window.MarketAPI.products({ limit: 100 })
      .then(function (res) {
        var items = (res && (res.products || res.items)) || [];
        if (items.length > 0) {
          var mapped = items.map(function (doc, idx) {
            var orig = doc.original_price || doc.mrp || Math.round(doc.price * 1.25);
            var disc = doc.discount_percentage != null ? Math.round(doc.discount_percentage) : Math.round(((orig - doc.price) / orig) * 100);
            return {
              id: String(doc.id || doc._id || ("prod-" + (idx + 1))),
              name: doc.name,
              brand: (doc.brand || "PoseAI").toUpperCase(),
              variant: doc.weight_label || "Standard",
              category: (doc.category || "supplements").toLowerCase(),
              price: doc.price,
              mrp: orig,
              discount: disc > 0 ? disc : 0,
              rating: Number(doc.rating || 4.7),
              reviews: doc.review_count || 1200,
              in_stock: doc.in_stock !== false,
              badge: doc.badge || (disc > 0 ? disc + "% OFF" : "BIOMETRIC SYNC"),
              badge_class: doc.badge_color ? ("badge-" + doc.badge_color) : "badge-blue",
              image: doc.thumbnail || (doc.image_urls && doc.image_urls[0]) || doc.image || "/images/products/muscleblaze-biozyme-whey.svg",
              is_favorite: !!doc.is_favorite,
            };
          });
          ALL_PRODUCTS = mapped;
        }
        renderActiveFilterChips();
        renderProductGrid();
      })
      .catch(function (err) {
        console.warn("Catalog API load failed, using fallback:", err);
        renderActiveFilterChips();
        renderProductGrid();
      });
  }

  function syncWithBackendCart() {
    if (window.MarketAPI && typeof window.MarketAPI.cart === "function") {
      window.MarketAPI.cart({ silent: true })
        .then(function (res) {
          if (res && res.cart && Array.isArray(res.cart.items) && res.cart.items.length > 0) {
            var newCart = {};
            res.cart.items.forEach(function (item) {
              newCart[item.product_id] = {
                id: item.product_id,
                name: item.name,
                variant: item.weight_label || "Standard",
                price: item.price,
                quantity: item.quantity,
                image: item.thumbnail || "/images/products/optimum-nutrition-gold-standard.svg",
              };
            });
            cartState = newCart;
            updateCartDrawerUI();
            renderProductGrid();
          }
        })
        .catch(function () {
          /* Fallback gracefully to local dataset */
        });
    }
  }

  function sendCartUpdateToBackend(productId, quantity) {
    if (!window.MarketAPI) return;
    if (quantity > 0) {
      if (typeof window.MarketAPI.updateQuantity === "function") {
        window.MarketAPI.updateQuantity(productId, quantity).catch(function () {
          if (typeof window.MarketAPI.addToCart === "function") {
            window.MarketAPI.addToCart(productId, quantity).catch(function () {});
          }
        });
      }
    } else {
      if (typeof window.MarketAPI.removeItem === "function") {
        window.MarketAPI.removeItem(productId).catch(function () {});
      }
    }
  }

  // ── Cart Calculations & UI Updates ──────────────────────────────────────────
  function updateCartDrawerUI() {
    var cartItemsList = document.getElementById("cartDrawerItemsList");
    var cartBadgeCount = document.getElementById("navCartCountBadge");
    var drawerTitleCount = document.getElementById("drawerCartTitleCount");
    var subtotalEl = document.getElementById("drawerSubtotalAmount");
    var gstEl = document.getElementById("drawerGstAmount");
    var totalEl = document.getElementById("drawerTotalAmount");

    var keys = Object.keys(cartState);
    var totalCount = 0;
    var subtotal = 0;

    var html = "";
    keys.forEach(function (key) {
      var item = cartState[key];
      if (!item || item.quantity <= 0) return;
      totalCount += item.quantity;
      subtotal += item.price * item.quantity;

      html +=
        '<div class="drawer-cart-item">' +
        '<div class="drawer-item-thumb">' +
        '<img src="' + escapeHtml(item.image) + '" alt="' + escapeHtml(item.name) + '">' +
        '</div>' +
        '<div class="drawer-item-info">' +
        '<div class="drawer-item-name">' + escapeHtml(item.name) + '</div>' +
        '<div class="drawer-item-variant">' + escapeHtml(item.variant) + '</div>' +
        '<div class="drawer-item-price">' + formatRupees(item.price) + '</div>' +
        '</div>' +
        '<div class="drawer-item-stepper">' +
        '<button type="button" class="drawer-stepper-btn" data-drawer-dec="' + escapeHtml(item.id) + '">−</button>' +
        '<span class="drawer-stepper-val">' + item.quantity + '</span>' +
        '<button type="button" class="drawer-stepper-btn" data-drawer-inc="' + escapeHtml(item.id) + '">+</button>' +
        '</div>' +
        '</div>';
    });

    if (cartItemsList) {
      cartItemsList.innerHTML = html || '<p style="text-align:center; color:#94a3b8; padding:32px 0;">Your cart is empty.</p>';
    }

    // GST is 18% as specified in reference design (₹5,347 subtotal -> ₹962 GST)
    var gst = Math.round(subtotal * 0.18);
    var total = subtotal + gst;

    if (subtotalEl) subtotalEl.textContent = formatRupees(subtotal);
    if (gstEl) gstEl.textContent = formatRupees(gst);
    if (totalEl) totalEl.textContent = formatRupees(total);
    if (cartBadgeCount) cartBadgeCount.textContent = totalCount;
    if (drawerTitleCount) drawerTitleCount.textContent = "Your Cart (" + totalCount + ")";

    // Update all matching card steppers on page
    document.querySelectorAll("[data-card-stepper-id]").forEach(function (el) {
      var prodId = el.getAttribute("data-card-stepper-id");
      var qty = (cartState[prodId] && cartState[prodId].quantity) || 0;
      var parent = el.parentElement;
      if (!parent) return;

      if (qty > 0) {
        parent.innerHTML =
          '<div class="card-qty-stepper" data-card-stepper-id="' + prodId + '">' +
          '<button type="button" class="stepper-btn" data-stepper-dec="' + prodId + '">−</button>' +
          '<span class="stepper-num">' + qty + '</span>' +
          '<button type="button" class="stepper-btn" data-stepper-inc="' + prodId + '">+</button>' +
          '</div>';
      } else {
        parent.innerHTML =
          '<button type="button" class="btn-add-cart" data-add-cart="' + prodId + '">' +
          '<span class="material-symbols-outlined" style="font-size:16px;">add</span> + ADD' +
          '</button>';
      }
    });
  }

  function handleQuantityChange(productId, delta) {
    var prod = ALL_PRODUCTS.find(function (p) { return p.id === productId; });
    var current = (cartState[productId] && cartState[productId].quantity) || 0;
    var next = current + delta;

    if (next > 0) {
      if (!cartState[productId] && prod) {
        cartState[productId] = {
          id: prod.id,
          name: prod.name,
          variant: (prod.brand || "") + " • " + (prod.variant || ""),
          price: prod.price,
          quantity: next,
          image: prod.image,
        };
      } else if (cartState[productId]) {
        cartState[productId].quantity = next;
      }
    } else {
      delete cartState[productId];
    }

    sendCartUpdateToBackend(productId, next);
    updateCartDrawerUI();
  }

  // ── Render Active Filter Tags ───────────────────────────────────────────────
  function renderActiveFilterChips() {
    var container = document.getElementById("activeFilterChipsList");
    if (!container) return;

    var chips = [];

    if (filterState.search) {
      chips.push({ id: "search", label: 'Search: "' + filterState.search + '"' });
    }
    if (filterState.inStockOnly) {
      chips.push({ id: "in_stock", label: "In Stock" });
    }
    if (filterState.categories && filterState.categories.length > 0) {
      filterState.categories.forEach(function (c) {
        chips.push({ id: "cat_" + c, label: c.charAt(0).toUpperCase() + c.slice(1) });
      });
    }
    if (filterState.priceMax && filterState.priceMax < 10000) {
      chips.push({ id: "price", label: "Under ₹" + filterState.priceMax.toLocaleString("en-IN") });
    }
    if (filterState.brands && filterState.brands.length > 0) {
      filterState.brands.forEach(function (b) {
        chips.push({ id: "brand_" + b, label: b });
      });
    }
    if (filterState.discount) {
      chips.push({ id: "discount", label: filterState.discount + "% or more" });
    }
    if (filterState.dealsOnly) {
      chips.push({ id: "deals", label: "Hot Deals" });
    }

    var html = "";
    chips.forEach(function (chip) {
      html +=
        '<span class="filter-chip-pill">' +
        escapeHtml(chip.label) +
        '<button type="button" class="chip-remove-btn" data-remove-chip="' + escapeHtml(chip.id) + '">✕</button>' +
        '</span>';
    });

    container.innerHTML = html;
  }

  // ── Filter & Sort Logic ─────────────────────────────────────────────────────
  function getFilteredProducts() {
    var list = ALL_PRODUCTS.slice();

    // Search query with typo tolerance (e.g. protien <-> protein)
    if (filterState.search) {
      var q = filterState.search.toLowerCase().trim();
      var normalizedQ = q.replace(/protien/g, "protein");
      list = list.filter(function (p) {
        var name = (p.name || "").toLowerCase();
        var brand = (p.brand || "").toLowerCase();
        var cat = (p.category || "").toLowerCase();
        return name.indexOf(q) !== -1 || name.indexOf(normalizedQ) !== -1 ||
               brand.indexOf(q) !== -1 || brand.indexOf(normalizedQ) !== -1 ||
               cat.indexOf(q) !== -1 || cat.indexOf(normalizedQ) !== -1;
      });
    }

    // In Stock
    if (filterState.inStockOnly) {
      list = list.filter(function (p) { return p.in_stock; });
    }

    // Category
    if (filterState.categories && filterState.categories.length > 0) {
      list = list.filter(function (p) {
        return filterState.categories.indexOf(p.category) !== -1;
      });
    }

    // Deals
    if (filterState.dealsOnly) {
      list = list.filter(function (p) {
        return p.is_deal || p.discount >= 20;
      });
    }

    // Brands
    if (filterState.brands && filterState.brands.length > 0) {
      list = list.filter(function (p) {
        return filterState.brands.indexOf(p.brand) !== -1;
      });
    }

    // Price Max / Min
    if (filterState.priceMin != null) {
      list = list.filter(function (p) { return p.price >= filterState.priceMin; });
    }
    if (filterState.priceMax != null) {
      list = list.filter(function (p) { return p.price <= filterState.priceMax; });
    }

    // Rating
    if (filterState.rating) {
      var minR = parseFloat(filterState.rating);
      list = list.filter(function (p) { return p.rating >= minR; });
    }

    // Discount
    if (filterState.discount) {
      var minD = parseInt(filterState.discount, 10);
      list = list.filter(function (p) { return p.discount >= minD; });
    }

    // Sort
    if (filterState.sort === "price_asc") {
      list.sort(function (a, b) { return a.price - b.price; });
    } else if (filterState.sort === "price_desc") {
      list.sort(function (a, b) { return b.price - a.price; });
    } else if (filterState.sort === "rating_desc") {
      list.sort(function (a, b) { return b.rating - a.rating; });
    } else if (filterState.sort === "discount_desc") {
      list.sort(function (a, b) { return b.discount - a.discount; });
    }

    return list;
  }

  // ── Render Product Grid ─────────────────────────────────────────────────────
  function renderProductGrid() {
    var grid = document.getElementById("catalogProductGrid");
    var countBadge = document.getElementById("headerProductCountBadge");
    var subtitleCount = document.getElementById("headerSubtitleText");
    var paginationInfo = document.getElementById("paginationInfoText");
    var paginationControls = document.getElementById("paginationControlsList");

    if (!grid) return;

    var filtered = getFilteredProducts();
    var total = filtered.length;
    var totalPages = Math.max(1, Math.ceil(total / filterState.limit));

    if (filterState.page > totalPages) filterState.page = totalPages;

    var startIndex = (filterState.page - 1) * filterState.limit;
    var pageItems = filtered.slice(startIndex, startIndex + filterState.limit);

    if (countBadge) countBadge.textContent = total + " ITEMS";
    if (subtitleCount) {
      subtitleCount.textContent = "Showing " + total + " products across 8 biomechanically optimized categories";
    }

    var fromCount = total === 0 ? 0 : startIndex + 1;
    var toCount = Math.min(startIndex + filterState.limit, total);
    if (paginationInfo) {
      paginationInfo.textContent = "Showing " + fromCount + "-" + toCount + " of " + total + " products";
    }

    // Render Pagination buttons
    if (paginationControls) {
      var phtml = "";
      phtml += '<button type="button" class="page-btn" id="btnPagePrev" ' + (filterState.page <= 1 ? "disabled" : "") + '>&lt; Prev</button>';
      for (var p = 1; p <= totalPages; p++) {
        var activeCls = p === filterState.page ? "active" : "";
        phtml += '<button type="button" class="page-btn ' + activeCls + '" data-goto-page="' + p + '">' + p + '</button>';
      }
      phtml += '<button type="button" class="page-btn" id="btnPageNext" ' + (filterState.page >= totalPages ? "disabled" : "") + '>Next &gt;</button>';
      paginationControls.innerHTML = phtml;
    }

    if (pageItems.length === 0) {
      grid.innerHTML =
        '<div style="grid-column: 1/-1; text-align:center; padding: 60px 20px; background:#ffffff; border-radius:12px; border:1px dashed #cbd5e1;">' +
        '<span class="material-symbols-outlined" style="font-size:48px; color:#94a3b8;">inventory_2</span>' +
        '<h3 style="font-size:16px; font-weight:800; color:#1e293b; margin-top:8px;">No Products Match Your Filters</h3>' +
        '<p style="font-size:12px; color:#64748b; margin-top:4px;">Try resetting some criteria or broadening your price range.</p>' +
        '<button type="button" id="gridResetFiltersBtn" style="margin-top:16px; background:#1E3A8A; color:#fff; font-size:12px; font-weight:800; padding:8px 18px; border-radius:8px; cursor:pointer;">Reset All Filters</button>' +
        '</div>';
      var rbtn = document.getElementById("gridResetFiltersBtn");
      if (rbtn) rbtn.addEventListener("click", resetAllFilters);
      return;
    }

    var html = "";
    pageItems.forEach(function (prod) {
      var qty = (cartState[prod.id] && cartState[prod.id].quantity) || 0;
      var heartClass = prod.is_favorite ? "active" : "";
      var heartIcon = prod.is_favorite ? "favorite" : "favorite_border";

      var buttonOrStepper = "";
      if (qty > 0) {
        buttonOrStepper =
          '<div class="card-qty-stepper" data-card-stepper-id="' + prod.id + '">' +
          '<button type="button" class="stepper-btn" data-stepper-dec="' + prod.id + '">−</button>' +
          '<span class="stepper-num">' + qty + '</span>' +
          '<button type="button" class="stepper-btn" data-stepper-inc="' + prod.id + '">+</button>' +
          '</div>';
      } else {
        buttonOrStepper =
          '<button type="button" class="btn-add-cart" data-add-cart="' + prod.id + '">' +
          '<span class="material-symbols-outlined" style="font-size:16px;">add</span> + ADD' +
          '</button>';
      }

      var detailUrl = "/fitness-market/product/" + encodeURIComponent(prod.id);

      html +=
        '<article class="product-card" data-product-card="' + prod.id + '">' +
        '<span class="card-badge ' + (prod.badge_class || "badge-blue") + '">' + escapeHtml(prod.badge) + '</span>' +
        '<button type="button" class="wishlist-heart-btn ' + heartClass + '" data-toggle-fav="' + prod.id + '" aria-label="Save to Wishlist">' +
        '<span class="material-symbols-outlined" style="font-size:18px;">' + heartIcon + '</span>' +
        '</button>' +
        '<a href="' + detailUrl + '" class="card-image-box" title="' + escapeHtml(prod.name) + '">' +
        '<img src="' + escapeHtml(prod.image) + '" alt="' + escapeHtml(prod.name) + '" loading="lazy">' +
        '</a>' +
        '<div class="card-details">' +
        '<div class="card-brand-row">' +
        '<span>' + escapeHtml(prod.brand) + '</span>' +
        '<span class="card-variant-label">' + escapeHtml(prod.variant) + '</span>' +
        '</div>' +
        '<a href="' + detailUrl + '" class="card-product-title" title="' + escapeHtml(prod.name) + '">' + escapeHtml(prod.name) + '</a>' +
        '<div class="card-rating-row">' +
        '<span class="rating-badge"><span class="material-symbols-outlined" style="font-size:11px;">star</span> ' + prod.rating.toFixed(1) + '</span>' +
        '<span class="review-count-text">(' + prod.reviews.toLocaleString("en-IN") + ')</span>' +
        '<span class="stock-status-tag ' + (prod.in_stock ? "" : "out-of-stock") + '">• ' + (prod.in_stock ? "In Stock" : "Out of Stock") + '</span>' +
        '</div>' +
        '<div class="card-price-row">' +
        '<span class="current-price">' + formatRupees(prod.price) + '</span>' +
        '<span class="original-mrp">' + formatRupees(prod.mrp) + '</span>' +
        '<span class="discount-tag">-' + prod.discount + '% OFF</span>' +
        '</div>' +
        '<div class="card-action-slot">' +
        buttonOrStepper +
        '</div>' +
        '</div>' +
        '</article>';
    });

    grid.innerHTML = html;
  }

  // ── Reset Filters ───────────────────────────────────────────────────────────
  function resetAllFilters() {
    filterState.search = "";
    filterState.inStockOnly = false;
    filterState.categories = [];
    filterState.brands = [];
    filterState.pricePreset = "all";
    filterState.priceMin = 0;
    filterState.priceMax = 10000;
    filterState.rating = "";
    filterState.discount = "";
    filterState.dealsOnly = false;
    filterState.page = 1;

    var sInput = document.getElementById("navSearchInput");
    if (sInput) sInput.value = "";

    var inStockSwitch = document.getElementById("inStockOnlyCheckbox");
    if (inStockSwitch) inStockSwitch.checked = false;

    document.querySelectorAll("input[name='categoryFilter']").forEach(function (cb) {
      cb.checked = false;
    });

    document.querySelectorAll("input[name='brandFilter']").forEach(function (cb) {
      cb.checked = false;
    });

    var allPriceRadio = document.querySelector("input[name='priceRadio'][value='all']");
    if (allPriceRadio) allPriceRadio.checked = true;

    var minInput = document.getElementById("filterPriceMinInput");
    var maxInput = document.getElementById("filterPriceMaxInput");
    var slider = document.getElementById("filterPriceSlider");
    if (minInput) minInput.value = "";
    if (maxInput) maxInput.value = "";
    if (slider) slider.value = 10000;

    document.querySelectorAll("input[name='ratingRadio']").forEach(function (rb) {
      rb.checked = false;
    });

    document.querySelectorAll(".discount-chip").forEach(function (btn) {
      btn.classList.remove("active");
    });

    var catBadge = document.getElementById("categorySectionBadge");
    if (catBadge) catBadge.textContent = "All";

    syncUrl();
    renderActiveFilterChips();
    renderProductGrid();
  }

  // ── Event Handlers & DOM Setup ──────────────────────────────────────────────
  function setupEventListeners() {
    // 1. Cart Drawer Slide-out Toggle
    var cartTriggerBtn = document.getElementById("navCartButton");
    var drawer = document.getElementById("cartDrawerPanel");
    var backdrop = document.getElementById("cartDrawerBackdrop");
    var drawerCloseBtn = document.getElementById("cartDrawerCloseBtn");

    function openCart() {
      if (drawer) drawer.classList.add("open");
      if (backdrop) backdrop.classList.add("open");
    }

    function closeCart() {
      if (drawer) drawer.classList.remove("open");
      if (backdrop) backdrop.classList.remove("open");
    }

    if (cartTriggerBtn) cartTriggerBtn.addEventListener("click", openCart);
    if (drawerCloseBtn) drawerCloseBtn.addEventListener("click", closeCart);
    if (backdrop) backdrop.addEventListener("click", closeCart);

    // Escape key closes modals
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        closeCart();
        closeMobileNav();
        closeSidebarDrawer();
      }
    });

    // 2. Mobile Nav Drawer Toggle
    var hamburgerBtn = document.getElementById("mobileHamburgerBtn");
    var mobileNav = document.getElementById("mobileNavDrawer");

    function toggleMobileNav() {
      if (mobileNav) mobileNav.classList.toggle("open");
    }

    function closeMobileNav() {
      if (mobileNav) mobileNav.classList.remove("open");
    }

    if (hamburgerBtn) hamburgerBtn.addEventListener("click", toggleMobileNav);

    // 3. Mobile Filter Drawer
    var mobileFilterTrigger = document.getElementById("mobileFilterTriggerBtn");
    var sidebar = document.getElementById("catalogSidebar");

    function openSidebarDrawer() {
      if (sidebar) sidebar.classList.add("open");
      if (backdrop) backdrop.classList.add("open");
    }

    function closeSidebarDrawer() {
      if (sidebar) sidebar.classList.remove("open");
    }

    if (mobileFilterTrigger) mobileFilterTrigger.addEventListener("click", openSidebarDrawer);

    // 4. Dropdown Menus ("More" and "Vikram S.")
    var moreTrigger = document.getElementById("navMoreDropdownTrigger");
    var moreMenu = document.getElementById("navMoreDropdownMenu");
    var userTrigger = document.getElementById("navUserDropdownTrigger");
    var userMenu = document.getElementById("navUserDropdownMenu");

    if (moreTrigger && moreMenu) {
      moreTrigger.addEventListener("click", function (e) {
        e.stopPropagation();
        moreMenu.classList.toggle("show");
        if (userMenu) userMenu.classList.remove("show");
      });
    }

    if (userTrigger && userMenu) {
      userTrigger.addEventListener("click", function (e) {
        e.stopPropagation();
        userMenu.classList.toggle("show");
        if (moreMenu) moreMenu.classList.remove("show");
      });
    }

    document.addEventListener("click", function () {
      if (moreMenu) moreMenu.classList.remove("show");
      if (userMenu) userMenu.classList.remove("show");
    });

    // 5. Accordion Collapsible Sections (Categories)
    document.querySelectorAll("[data-accordion-toggle]").forEach(function (header) {
      header.addEventListener("click", function () {
        var targetId = header.getAttribute("data-accordion-toggle");
        var body = document.getElementById(targetId);
        var chevron = header.querySelector(".accordion-chevron");
        if (body) {
          body.classList.toggle("hidden");
        }
        if (chevron) {
          chevron.classList.toggle("collapsed");
        }
      });
    });

    // 6. In-Stock Only Switch
    var inStockSwitch = document.getElementById("inStockOnlyCheckbox");
    if (inStockSwitch) {
      inStockSwitch.addEventListener("change", function () {
        filterState.inStockOnly = inStockSwitch.checked;
        filterState.page = 1;
        renderActiveFilterChips();
        renderProductGrid();
      });
    }

    // 7. Categories Checkboxes
    document.querySelectorAll("input[name='categoryFilter']").forEach(function (cb) {
      cb.addEventListener("change", function () {
        var selected = [];
        document.querySelectorAll("input[name='categoryFilter']:checked").forEach(function (c) {
          selected.push(c.value);
        });
        filterState.categories = selected;
        filterState.page = 1;
        renderActiveFilterChips();
        renderProductGrid();
      });
    });

    // 8. Brand Checkboxes
    document.querySelectorAll("input[name='brandFilter']").forEach(function (cb) {
      cb.addEventListener("change", function () {
        var selected = [];
        document.querySelectorAll("input[name='brandFilter']:checked").forEach(function (b) {
          selected.push(b.value);
        });
        filterState.brands = selected;
        filterState.page = 1;
        renderActiveFilterChips();
        renderProductGrid();
      });
    });

    // 9. Price Radio Presets
    document.querySelectorAll("input[name='priceRadio']").forEach(function (rb) {
      rb.addEventListener("change", function () {
        var val = rb.value;
        filterState.pricePreset = val;
        var minInput = document.getElementById("filterPriceMinInput");
        var maxInput = document.getElementById("filterPriceMaxInput");
        var slider = document.getElementById("filterPriceSlider");

        if (val === "all") {
          filterState.priceMin = 0;
          filterState.priceMax = 10000;
        } else if (val === "0-500") {
          filterState.priceMin = 0;
          filterState.priceMax = 500;
        } else if (val === "500-1000") {
          filterState.priceMin = 500;
          filterState.priceMax = 1000;
        } else if (val === "1000-2500") {
          filterState.priceMin = 1000;
          filterState.priceMax = 2500;
        } else if (val === "2500-5000") {
          filterState.priceMin = 2500;
          filterState.priceMax = 5000;
        } else if (val === "5000+") {
          filterState.priceMin = 5000;
          filterState.priceMax = 20000;
        }

        if (minInput && filterState.priceMin != null) minInput.value = filterState.priceMin;
        if (maxInput && filterState.priceMax != null) maxInput.value = filterState.priceMax;
        if (slider && filterState.priceMax != null) slider.value = Math.min(filterState.priceMax, 5000);

        filterState.page = 1;
        renderActiveFilterChips();
        renderProductGrid();
      });
    });

    // 10. Min/Max Numeric Price Inputs & Slider
    var minInput = document.getElementById("filterPriceMinInput");
    var maxInput = document.getElementById("filterPriceMaxInput");
    var slider = document.getElementById("filterPriceSlider");

    if (minInput) {
      minInput.addEventListener("input", function () {
        filterState.priceMin = parseInt(minInput.value, 10) || 0;
        filterState.page = 1;
        renderActiveFilterChips();
        renderProductGrid();
      });
    }

    if (maxInput) {
      maxInput.addEventListener("input", function () {
        filterState.priceMax = parseInt(maxInput.value, 10) || 10000;
        if (slider) slider.value = Math.min(filterState.priceMax, 5000);
        filterState.page = 1;
        renderActiveFilterChips();
        renderProductGrid();
      });
    }

    if (slider) {
      slider.addEventListener("input", function () {
        var val = parseInt(slider.value, 10);
        filterState.priceMax = val;
        if (maxInput) maxInput.value = val;
        filterState.page = 1;
        renderActiveFilterChips();
        renderProductGrid();
      });
    }

    // 11. Rating Star Radios
    document.querySelectorAll("input[name='ratingRadio']").forEach(function (rb) {
      rb.addEventListener("change", function () {
        filterState.rating = rb.value;
        filterState.page = 1;
        renderProductGrid();
      });
    });

    // 12. Discount Chips
    document.querySelectorAll(".discount-chip").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var d = parseInt(btn.getAttribute("data-discount"), 10);
        if (filterState.discount === d) {
          filterState.discount = "";
          btn.classList.remove("active");
        } else {
          filterState.discount = d;
          document.querySelectorAll(".discount-chip").forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
        }
        filterState.page = 1;
        renderActiveFilterChips();
        renderProductGrid();
      });
    });

    // 13. Sort Dropdown
    var sortSelect = document.getElementById("catalogSortSelect");
    if (sortSelect) {
      sortSelect.addEventListener("change", function () {
        filterState.sort = sortSelect.value;
        filterState.page = 1;
        renderProductGrid();
      });
    }

    // 14. Clear All Filters Link
    var clearAllLink = document.getElementById("clearAllFiltersLink");
    if (clearAllLink) clearAllLink.addEventListener("click", resetAllFilters);

    var clearAllChips = document.getElementById("clearAllChipsLink");
    if (clearAllChips) clearAllChips.addEventListener("click", resetAllFilters);

    // 15. Global Click Delegation for Dynamic Elements
    document.addEventListener("click", function (e) {
      // "+ ADD" Button Click
      var addBtn = e.target.closest("[data-add-cart]");
      if (addBtn) {
        var pid = addBtn.getAttribute("data-add-cart");
        handleQuantityChange(pid, 1);
        return;
      }

      // Stepper Increment
      var incBtn = e.target.closest("[data-stepper-inc]");
      if (incBtn) {
        var pid = incBtn.getAttribute("data-stepper-inc");
        handleQuantityChange(pid, 1);
        return;
      }

      // Stepper Decrement
      var decBtn = e.target.closest("[data-stepper-dec]");
      if (decBtn) {
        var pid = decBtn.getAttribute("data-stepper-dec");
        handleQuantityChange(pid, -1);
        return;
      }

      // Drawer Stepper Increment
      var dIncBtn = e.target.closest("[data-drawer-inc]");
      if (dIncBtn) {
        var pid = dIncBtn.getAttribute("data-drawer-inc");
        handleQuantityChange(pid, 1);
        return;
      }

      // Drawer Stepper Decrement
      var dDecBtn = e.target.closest("[data-drawer-dec]");
      if (dDecBtn) {
        var pid = dDecBtn.getAttribute("data-drawer-dec");
        handleQuantityChange(pid, -1);
        return;
      }

      // Wishlist Heart Toggle
      var favBtn = e.target.closest("[data-toggle-fav]");
      if (favBtn) {
        var pid = favBtn.getAttribute("data-toggle-fav");
        var prod = ALL_PRODUCTS.find(function (p) { return p.id === pid; });
        if (prod) {
          prod.is_favorite = !prod.is_favorite;
          favBtn.classList.toggle("active", prod.is_favorite);
          var icon = favBtn.querySelector(".material-symbols-outlined");
          if (icon) icon.textContent = prod.is_favorite ? "favorite" : "favorite_border";

          if (window.MarketAPI) {
            if (prod.is_favorite && typeof window.MarketAPI.addFavorite === "function") {
              window.MarketAPI.addFavorite(pid).catch(function () {});
            } else if (!prod.is_favorite && typeof window.MarketAPI.removeFavorite === "function") {
              window.MarketAPI.removeFavorite(pid).catch(function () {});
            }
          }
        }
        return;
      }

      // Active Chip Remove
      var removeChipBtn = e.target.closest("[data-remove-chip]");
      if (removeChipBtn) {
        var chipId = removeChipBtn.getAttribute("data-remove-chip");
        if (chipId === "search") {
          filterState.search = "";
          var sInput = document.getElementById("navSearchInput");
          if (sInput) sInput.value = "";
        } else if (chipId === "in_stock") {
          filterState.inStockOnly = false;
          var inStockSwitch = document.getElementById("inStockOnlyCheckbox");
          if (inStockSwitch) inStockSwitch.checked = false;
        } else if (chipId.startsWith("cat_")) {
          var catSlug = chipId.replace("cat_", "");
          filterState.categories = filterState.categories.filter(function (c) { return c !== catSlug; });
          var cb = document.querySelector("input[name='categoryFilter'][value='" + catSlug + "']");
          if (cb) cb.checked = false;
          var catBadge = document.getElementById("categorySectionBadge");
          if (catBadge) catBadge.textContent = filterState.categories.length > 0 ? (filterState.categories.length + " Selected") : "All";
        } else if (chipId.startsWith("brand_")) {
          var brName = chipId.replace("brand_", "");
          filterState.brands = filterState.brands.filter(function (b) { return b !== brName; });
          var bcb = document.querySelector("input[name='brandFilter'][value='" + brName + "']");
          if (bcb) bcb.checked = false;
        } else if (chipId === "price") {
          filterState.priceMin = 0;
          filterState.priceMax = 10000;
          var minInput = document.getElementById("filterPriceMinInput");
          var maxInput = document.getElementById("filterPriceMaxInput");
          var slider = document.getElementById("filterPriceSlider");
          if (minInput) minInput.value = "";
          if (maxInput) maxInput.value = "";
          if (slider) slider.value = 10000;
          var allPriceRadio = document.querySelector("input[name='priceRadio'][value='all']");
          if (allPriceRadio) allPriceRadio.checked = true;
        } else if (chipId === "discount") {
          filterState.discount = "";
          document.querySelectorAll(".discount-chip").forEach(function (b) { b.classList.remove("active"); });
        } else if (chipId === "deals") {
          filterState.dealsOnly = false;
        }
        syncUrl();
        renderActiveFilterChips();
        renderProductGrid();
        return;
      }

      // Pagination Controls
      var pageBtn = e.target.closest("[data-goto-page]");
      if (pageBtn) {
        var targetPage = parseInt(pageBtn.getAttribute("data-goto-page"), 10);
        if (targetPage) {
          filterState.page = targetPage;
          syncUrl();
          renderProductGrid();
          window.scrollTo({ top: 0, behavior: "smooth" });
        }
        return;
      }

      if (e.target.closest("#btnPagePrev")) {
        if (filterState.page > 1) {
          filterState.page -= 1;
          syncUrl();
          renderProductGrid();
          window.scrollTo({ top: 0, behavior: "smooth" });
        }
        return;
      }

      if (e.target.closest("#btnPageNext")) {
        var total = getFilteredProducts().length;
        var maxPages = Math.ceil(total / filterState.limit);
        if (filterState.page < maxPages) {
          filterState.page += 1;
          syncUrl();
          renderProductGrid();
          window.scrollTo({ top: 0, behavior: "smooth" });
        }
        return;
      }
    });

    // Top Navbar Search Input Handling
    var searchInput = document.getElementById("navSearchInput");
    if (searchInput) {
      var searchTimer = null;
      searchInput.addEventListener("input", function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
          filterState.search = searchInput.value.trim();
          filterState.page = 1;
          syncUrl();
          renderActiveFilterChips();
          renderProductGrid();
        }, 250);
      });
      searchInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          clearTimeout(searchTimer);
          filterState.search = searchInput.value.trim();
          filterState.page = 1;
          syncUrl();
          renderActiveFilterChips();
          renderProductGrid();
        }
      });
    }

    // Top Navbar Logout Button
    var logoutBtn = document.getElementById("navLogoutBtn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", function () {
        var getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : function (p) { return p; };
        fetch(getUrl("/api/auth/logout"), { method: "POST", credentials: "include" })
          .finally(function () {
            window.location.href = "/login";
          });
      });
    }

    // Dynamic User Profile in Header
    var getUrl = typeof window.getApiUrl === "function" ? window.getApiUrl : function (p) { return p; };
    fetch(getUrl("/api/user/profile"), { credentials: "include" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        var u = data && (data.user || data.data || data);
        if (u) {
          var name = u.name || u.full_name || u.username;
          if (name) {
            var nameEl = document.getElementById("navUserName");
            if (nameEl) nameEl.textContent = name;
          }
          if (u.profile_picture) {
            var av = document.getElementById("navUserAvatar");
            if (av) av.src = u.profile_picture;
          }
        }
      })
      .catch(function () {});
  }

  // ── Initial Boot ────────────────────────────────────────────────────────────
  function boot() {
    readUrlParams();
    setupEventListeners();
    loadBackendProducts();
    updateCartDrawerUI();
    syncWithBackendCart();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
