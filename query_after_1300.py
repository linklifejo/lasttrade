import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT * FROM trades WHERE timestamp > '2026-01-13 13:00:00' ORDER BY id DESC")
rows = cursor.fetchall()
print(f"Trades after 13:00: {len(rows)}")
for row in rows:
    print(row)
conn.close()
