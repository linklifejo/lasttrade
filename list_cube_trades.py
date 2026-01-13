import sqlite3
import json
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
# Filter for THE CUBE& (013720)
cursor.execute("SELECT * FROM trades WHERE code = '013720' OR name LIKE '%더큐브%' ORDER BY timestamp ASC")
rows = cursor.fetchall()
print(f"Total records found: {len(rows)}")
for row in rows:
    print(row)
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
