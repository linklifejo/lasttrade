import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT * FROM asset_history ORDER BY timestamp DESC LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
