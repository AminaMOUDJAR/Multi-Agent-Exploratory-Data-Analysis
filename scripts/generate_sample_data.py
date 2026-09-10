"""Generate sample_data/sales_sample.csv — a messy retail dataset with
missing values, duplicates and outliers, ideal for testing the EDA pipeline.

Uses only the standard library. Run:  python scripts/generate_sample_data.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(7)

REGIONS = ["East"] * 34 + ["West"] * 30 + ["North"] * 20 + ["South"] * 16
CATEGORIES = {  # category -> (mean unit sales, sd)
    "Electronics": (220, 90),
    "Furniture": (160, 70),
    "Apparel": (70, 30),
    "Grocery": (35, 12),
}
START = date(2024, 1, 1)

rows = []
for i in range(1, 381):
    cat = random.choices(list(CATEGORIES), weights=[30, 25, 25, 20])[0]
    mu, sd = CATEGORIES[cat]
    sales = max(5.0, random.gauss(mu, sd))
    qty = random.randint(1, 10)
    disc = random.choice([0, 0, 0, 0, 0.05, 0.1, 0.15, 0.2, 0.3])
    profit = sales * qty * (0.28 - 0.9 * disc) + random.gauss(0, 12)
    rows.append({
        "order_id": f"ORD-{i:04d}",
        "order_date": (START + timedelta(days=random.randrange(365))).isoformat(),
        "region": random.choice(REGIONS),
        "category": cat,
        "customer_age": random.randint(18, 70),
        "sales": round(sales, 2),
        "quantity": qty,
        "discount": disc,
        "profit": round(profit, 2),
        "satisfaction": round(min(5, max(1, random.gauss(4.1, 0.8))), 1),
    })

# Missing values (~3%)
for r in random.sample(rows, 12):
    r["sales"] = ""
for r in random.sample(rows, 10):
    r["customer_age"] = ""
for r in random.sample(rows, 6):
    r["region"] = ""

# Extreme outliers (typos / fraud-ish spikes)
for r in random.sample(rows, 6):
    r["sales"] = round(float(r["sales"] or 100) * 15, 2)

# Duplicate rows
rows.extend(dict(r) for r in random.sample(rows, 18))
random.shuffle(rows)

out = Path(__file__).resolve().parents[1] / "sample_data" / "sales_sample.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

print(f"wrote {len(rows)} rows -> {out}")
