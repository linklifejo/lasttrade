import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(system_status)")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
