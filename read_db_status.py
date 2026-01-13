import sqlite3
import json
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT status_json FROM system_status WHERE api_mode = 'REAL'")
row = cursor.fetchone()
if row:
    data = json.loads(row[0])
    print(json.dumps(data, indent=2, ensure_ascii=False))
else:
    print("No status found.")
conn.close()
