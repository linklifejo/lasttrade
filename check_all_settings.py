import sqlite3
import os

db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- [Current Database Settings] ---")
rows = cursor.execute("SELECT key, value FROM settings").fetchall()
for row in rows:
    print(f"{row['key']:30} : {row['value']}")

conn.close()
