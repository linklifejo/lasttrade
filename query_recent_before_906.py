import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT * FROM trades WHERE id < 75054 ORDER BY id DESC LIMIT 20")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
