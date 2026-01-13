import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM trades")
row = cursor.fetchone()
print(f"Total rows in trades: {row[0]}")
# Also list last 5 trades to be sure
cursor.execute("SELECT id, timestamp, type, code, name FROM trades ORDER BY id DESC LIMIT 5")
rows = cursor.fetchall()
for r in rows:
    print(r)
conn.close()
