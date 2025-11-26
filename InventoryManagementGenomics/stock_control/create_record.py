import random
import datetime
from django.utils.timezone import now
from django.contrib.auth.models import User
from inventory.models import Product, Withdrawal  # Replace 'myapp' with your actual app name

# List of laboratory reagents
reagents = [
    "Acetic Acid", "Acetone", "Ammonium Hydroxide", "Benzene", "Boric Acid", "Calcium Chloride", "Chloroform",
    "Copper Sulfate", "Ethanol", "Formaldehyde", "Glycerol", "Hydrochloric Acid", "Hydrogen Peroxide", "Iodine Solution",
    "Isopropanol", "Methanol", "Nitric Acid", "Oxalic Acid", "Phenol", "Phosphoric Acid", "Potassium Hydroxide",
    "Silver Nitrate", "Sodium Bicarbonate", "Sodium Hydroxide", "Sulfuric Acid", "Toluene", "Urea", "Xylene",
    "Zinc Sulfate", "Magnesium Sulfate", "Ferric Chloride", "Lithium Chloride", "Manganese Dioxide", "Nickel Sulfate",
    "Chromic Acid", "Sodium Chloride", "Potassium Nitrate", "Calcium Hydroxide", "Sodium Thiosulfate",
    "Ammonium Nitrate", "Barium Hydroxide", "Cobalt Chloride", "Titanium Dioxide", "Sodium Citrate", "Lead Acetate",
    "Potassium Permanganate", "Aluminum Sulfate", "Mercuric Chloride", "Cadmium Sulfate", "Cyanuric Acid",
    "Sodium Metabisulfite", "Iron(III) Sulfate", "Copper Nitrate", "Bismuth Subnitrate", "Zirconium Oxychloride",
    "Strontium Nitrate", "Sodium Nitrite", "Ammonium Thiocyanate", "Cerium Oxide", "Thallium Sulfate", "Thorium Nitrate",
    "Vanadium Pentoxide", "Yttrium Oxide", "Zinc Acetate", "Ruthenium Chloride", "Rhodium Nitrate", "Iridium Chloride",
    "Osmium Tetroxide", "Palladium Chloride", "Platinum Nitrate", "Gold Chloride", "Silver Acetate", "Sodium Benzoate",
    "Sodium Borohydride", "Potassium Bromide", "Potassium Dichromate", "Sodium Fluoride", "Potassium Iodide",
    "Potassium Cyanide", "Sodium Cyanide", "Lithium Hydroxide", "Calcium Carbonate", "Magnesium Oxide",
    "Sodium Sulfate", "Potassium Sulfate", "Ammonium Phosphate", "Sodium Peroxide", "Barium Sulfate",
    "Chromium Trioxide", "Cobalt Nitrate", "Nickel Acetate", "Manganese Chloride", "Tin(II) Chloride",
    "Titanium Tetrachloride", "Zinc Oxide", "Iron(II) Chloride", "Vanadium Chloride", "Lanthanum Oxide",
]

# Select 100 unique reagents
selected_reagents = random.sample(reagents, min(100, len(reagents)))


# Get an existing user or create one
users = list(User.objects.all())
if not users:
    user = User.objects.create(username="admin", email="admin@example.com")
    users.append(user)

# Create 100 Products
products = []
for i, reagent in enumerate(selected_reagents):
    product = Product.objects.create(
        supplier=random.choice(["LEICA", "THIRD_PARTY"]),
        product_code=f"REAG-{i+1:03d}",
        name=reagent,
        threshold=random.randint(5, 20),
        lead_time=datetime.timedelta(days=random.randint(1, 14)),
        current_stock=random.randint(10, 100)
    )
    products.append(product)

print("✅ 100 Laboratory Reagents added to the database!")

# Create 50 Withdrawals
for _ in range(50):
    product = random.choice(products)
    user = random.choice(users)
    quantity = random.randint(1, 10)
    withdrawal_type = random.choice(["unit", "volume"])

    Withdrawal.objects.create(
        product=product,
        quantity=quantity,
        withdrawal_type=withdrawal_type,
        timestamp=now(),
        user=user,
        barcode=f"BAR-{random.randint(1000, 9999)}" if random.choice([True, False]) else None
    )

print("✅ 50 Withdrawal records added to the database!")
