"""
Script to update all product images in market/catalog_data.py to use real photographs.
Replaces all SVG drawings and duplicate placeholders with real photorealistic studio images.
"""
import os
import re

def main():
    catalog_path = os.path.abspath('market/catalog_data.py')
    with open(catalog_path, 'r', encoding='utf-8') as f:
        code = f.read()

    # Define exact mapping for each product based on name or slug
    # We will parse PRODUCTS_84 items and update image_urls precisely.
    
    # 1. Direct replacements for specific SVGs:
    replacements = [
        # Supplements & Protein
        ('/images/products/creapure-creatine-monohydrate.svg', '/images/market_products/Creatine-2-1779255946.webp'),
        ('/images/products/fastup-reload-electrolytes.svg', '/images/market_products/BCAA-1-1776232203.webp'),
        ('/images/products/muscleblaze-biozyme-whey.svg', '/images/market_products/image-1-1782968120.webp'),
        ('/images/products/plantfuel-pea-rice-protein.svg', '/images/market_products/Pea-Protein-1771222444.webp'),
        ('/images/products/optimum-nutrition-gold-standard.svg', '/images/market_products/Mass-&-Weight-gainers-1767084988.webp'),
        ('/images/products/muscleblaze-raw-whey-isolate.svg', '/images/market_products/image-1-1782968120.webp'),
        ('/images/products/cosmix-plant-protein.svg', '/images/market_products/Yeast-Protein-1771222444.webp'),
        ('/images/products/the-whole-truth-raw-whey.svg', '/images/market_products/image-1-1782968120.webp'),
        ('/images/products/yogabar-protein-bars.svg', '/images/products/yogabar-protein-bars.webp'),
        ('/images/products/cellucor-c4-preworkout.svg', '/images/market_products/Pre-Workout-1768369799.webp'),
        ('/images/products/fastup-magnesium-glycinate.svg', '/images/market_products/Magnesium-1767085118.webp'),
        ('/images/products/bowflex-hex-dumbbells.svg', '/images/market_products/hexagon-dumbbells-white.webp'),
        ('/images/products/poseai-smart-thermal-shaker.svg', '/images/market_products/1604726193_product_07112020104633.jpg'),
        ('/images/products/hyperice-massage-gun.svg', '/images/products/hyperice-massage-gun.webp'),
        ('/images/products/nike-air-zoom-superrep.svg', '/images/products/nike-air-zoom-superrep.webp'),
        ('/images/products/apex-grip-liquid-chalk.svg', '/images/products/apex-grip-liquid-chalk.webp'),
        ('/images/products/boldfit-resistance-bands.svg', '/images/market_products/PMM-09-Option-1-White-Image-6a01a9e512746.jpg'),
        ('/images/products/poseai-ultra-grip-mat.svg', '/images/market_products/PMM-09-Option-1-White-Image-6a01a9e512746.jpg'),
    ]

    for old, new in replacements:
        code = code.replace(old, new)

    # 2. Apparel items that pointed to under-armour-compression-top.svg:
    # We differentiate each apparel item to its dedicated real image!
    apparel_maps = [
        ('Under Armour HeatGear Compression Top', '/images/products/under-armour-compression-top.webp'),
        ('PoseAI Dry-Fit Performance Athletic T-Shirt', '/images/products/poseai-performance-tshirt.webp'),
        ('PoseAI Core Training Breathable Mesh Shorts', '/images/products/poseai-mesh-shorts.webp'),
        ('Seamless Muscle-Fit Gym Stringer Tank Top', '/images/products/gym-stringer-tank-top.webp'),
        ('High-Waist Squat-Proof Compression Leggings', '/images/products/compression-leggings.webp'),
        ('PoseAI Heavyweight Fleece Warmup Workout Hoodie', '/images/products/poseai-workout-hoodie.webp'),
        ('Tapered Athletic Fit French Terry Joggers', '/images/products/athletic-joggers.webp'),
        ('UV 50+ Gradient Compression Arm Sleeves Pair', '/images/products/compression-arm-sleeves.webp'),
        ('Anti-Blister Cushioned Athletic Crew Socks (3-Pack)', '/images/products/athletic-crew-socks.webp'),
        ('Breathable Curved-Brim Athlete Snapback Cap', '/images/products/athlete-snapback-cap.webp'),
        ('Thermal ColdGear Base-Layer Long-Sleeve Shirt', '/images/products/thermal-coldgear-shirt.webp'),
    ]

    for name, img in apparel_maps:
        # Match product block by name and replace its image_urls
        pattern = re.compile(rf'("name":\s*"{re.escape(name)}".*?"image_urls":\s*\[)"[^"]+"(\])', re.DOTALL)
        code = pattern.sub(rf'\1"{img}"\2', code)

    # 3. Recovery items that pointed to poseai-recovery-foam-roller.svg:
    recovery_maps = [
        ('PoseAI High Density Deep Tissue Foam Roller 45cm', '/images/products/poseai-recovery-foam-roller.webp'),
        ('Vibrating Muscle Release Peanut Roller', '/images/products/peanut-roller.webp'),
        ('Ergonomic Spine Decompression Posture Stretcher', '/images/products/spine-stretcher.webp'),
    ]
    for name, img in recovery_maps:
        pattern = re.compile(rf'("name":\s*"{re.escape(name)}".*?"image_urls":\s*\[)"[^"]+"(\])', re.DOTALL)
        code = pattern.sub(rf'\1"{img}"\2', code)

    # 4. Accessories items that pointed to griptech-weightlifting-gloves.svg or wrist-wraps:
    accessory_maps = [
        ('GripTech Pro Leather Weightlifting Gloves', '/images/products/griptech-weightlifting-gloves.webp'),
        ('PoseAI Biomech Pro Heavy-Duty Wrist Wraps Pair', '/images/products/poseai-biomech-wrist-wraps.webp'),
        ('Heavy-Duty Padded Figure-8 Lifting Straps', '/images/products/figure8-lifting-straps.webp'),
        ('7mm Neoprene Compression Rebound Knee Sleeves Pair', '/images/products/compression-knee-sleeves.webp'),
        ('Quick-Release Stainless Steel Lever Powerlifting Belt 10mm', '/images/products/powerlifting-lever-belt.webp'),
    ]
    for name, img in accessory_maps:
        pattern = re.compile(rf'("name":\s*"{re.escape(name)}".*?"image_urls":\s*\[)"[^"]+"(\])', re.DOTALL)
        code = pattern.sub(rf'\1"{img}"\2', code)

    with open(catalog_path, 'w', encoding='utf-8') as f:
        f.write(code)

    print('Successfully updated market/catalog_data.py with real images.')

if __name__ == '__main__':
    main()
