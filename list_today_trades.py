import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT * FROM trades WHERE DATE(timestamp) = '2026-01-13'")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
