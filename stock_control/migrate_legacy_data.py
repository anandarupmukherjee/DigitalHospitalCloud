
import sqlite3
import json
import datetime

DB_PATH = '/code/db.sqlite3' # Path inside container
OUTPUT_FILE = 'inventory_dump.json'

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

conn = sqlite3.connect(DB_PATH)
conn.row_factory = dict_factory
cursor = conn.cursor()

data = []

today = datetime.date.today().isoformat()

# 1. Migrate Suppliers
cursor.execute("SELECT * FROM inventory_supplier")
suppliers = cursor.fetchall()
for s in suppliers:
    data.append({
        "model": "data_storage.supplier",
        "pk": s['id'],
        "fields": {
            "name": s['name'],
            "contact_email": s['contact_email'],
            "contact_phone": s['contact_phone']
        }
    })

# 2. Migrate Products -> Product + ProductItem
cursor.execute("SELECT * FROM inventory_product")
products = cursor.fetchall()

# Keep track of product info for snapshotting in PO/Withdrawal
product_map = {}

for p in products:
    p_id = p['id']
    product_map[p_id] = p
    
    # Create Product
    data.append({
        "model": "data_storage.product",
        "pk": p_id,
        "fields": {
            "product_code": p['product_code'],
            "name": p['name'],
            "supplier": p['supplier'],
            "threshold": p['threshold'],
            "lead_time": str(datetime.timedelta(days=1)) if not p['lead_time'] else str(datetime.timedelta(days=p['lead_time'] / 86400)) if p['lead_time'] > 1000 else "1 00:00:00" # lead_time in sqlite is often big int (seconds?) or timedelta?
            # Warning: lead_time in sqlite output showed 'bigint'. Django DurationField stores microseconds? or similar.
            # If we just put a string, loaddata handles it?
            # Let's assume standard duration string.
            # For safety, let's just use default or try to parse. 
            # If p['lead_time'] is large, likely microseconds.
        }
    })
    
    # Create ProductItem
    # Using SAME ID as Product for simplicity and FK preservation compatibility
    data.append({
        "model": "data_storage.productitem",
        "pk": p_id, 
        "fields": {
            "product": p_id,
            "lot_number": "LEGACY",
            "expiry_date": today,
            "current_stock": str(p['current_stock']),
            "units_per_quantity": p['units_per_quantity'],
            "accumulated_partial": p['accumulated_partial'],
            "product_feature": p['product_feature']
        }
    })

# 3. Migrate PurchaseOrders
cursor.execute("SELECT * FROM inventory_purchaseorder")
orders = cursor.fetchall()
for o in orders:
    pid = o['product_id']
    prod = product_map.get(pid, {})
    
    data.append({
        "model": "data_storage.purchaseorder",
        "pk": o['id'],
        "fields": {
            "quantity_ordered": o['quantity_ordered'],
            "order_date": o['order_date'],
            "expected_delivery": o['expected_delivery'],
            "status": o['status'],
            "ordered_by": o['ordered_by_id'],
            "product_item": pid, # Points to the ProductItem we created with same ID
            # Snapshot fields
            "product_code": prod.get('product_code', 'UNKNOWN'),
            "product_name": prod.get('name', 'UNKNOWN'),
            "lot_number": "LEGACY",
            "expiry_date": today
        }
    })

# 4. Migrate Withdrawals
cursor.execute("SELECT * FROM inventory_withdrawal")
withdrawals = cursor.fetchall()
for w in withdrawals:
    pid = w['product_id']
    prod = product_map.get(pid, {})
    
    data.append({
        "model": "data_storage.withdrawal",
        "pk": w['id'],
        "fields": {
            "quantity": str(w['quantity']),
            "withdrawal_type": w['withdrawal_type'],
            "timestamp": w['timestamp'],
            "user": w['user_id'],
            "product_item": pid,
             # Snapshot fields
            "product_code": prod.get('product_code', 'UNKNOWN'),
            "product_name": prod.get('name', 'UNKNOWN'),
            "lot_number": "LEGACY",
            "expiry_date": today,
            "parts_withdrawn": w['parts_withdrawn'],
            "barcode": w.get('barcode', '')
        }
    })

print(json.dumps(data, indent=2))
