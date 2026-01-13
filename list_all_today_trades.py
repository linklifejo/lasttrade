import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT * FROM trades WHERE timestamp LIKE '2026-01-13%' ORDER BY id DESC LIMIT 50")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
