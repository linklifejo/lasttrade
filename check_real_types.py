import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row

print("--- Real Mode Types ---")
cursor = conn.execute("SELECT type, count(*) as count FROM trades WHERE mode = 'REAL' GROUP BY type")
for row in cursor.fetchall():
    print(f"Type: {row['type']}, Count: {row['count']}")

print("\n--- Sell Sample ---")
cursor = conn.execute("SELECT type, timestamp FROM trades WHERE mode = 'REAL' AND type IN ('sell', 'SELL') LIMIT 5")
for row in cursor.fetchall():
    print(f"Type: {row['type']}, Time: {row['timestamp']}")
