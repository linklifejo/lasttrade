import sqlite3
import os

db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- [Trades for 014910 (Sungmoon)] ---")
rows = cursor.execute("SELECT * FROM trades WHERE code = '014910'").fetchall()
for row in rows:
    print(dict(row))

conn.close()
