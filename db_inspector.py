import sqlite3
import os

db_path = 'trading.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- Settings ---")
rows = cursor.execute("SELECT * FROM settings WHERE key IN ('target_stock_count', 'use_mock_server', 'is_paper_trading')").fetchall()
for row in rows:
    print(f"{row['key']}: {row['value']}")

print("\n--- Latest Trades (Today) ---")
import datetime
today = datetime.date.today().strftime('%Y-%m-%d')
rows = cursor.execute("SELECT mode, code, type, qty, timestamp FROM trades WHERE timestamp LIKE ? LIMIT 20", (f"{today}%",)).fetchall()
for row in rows:
    print(f"[{row['mode']}] {row['code']} {row['type']} {row['qty']} @ {row['timestamp']}")

conn.close()
