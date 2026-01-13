import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT * FROM trades WHERE timestamp LIKE '2026-01-13%' AND id < 75054 ORDER BY id DESC")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
