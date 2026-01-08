
import sqlite3
import datetime

db_path = 'trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 최근 20개 매도 기록 조회
print("--- Recent Sells ---")
cursor.execute("SELECT id, timestamp, code, name, type, mode FROM trades WHERE type='sell' ORDER BY id DESC LIMIT 20")
rows = cursor.fetchall()
if not rows:
    print("No sell records found.")
else:
    for row in rows:
        print(row)

print("\n--- Summary by Mode (Today) ---")
today = datetime.datetime.now().strftime('%Y-%m-%d')
cursor.execute("SELECT mode, COUNT(*) FROM trades WHERE type='sell' AND timestamp LIKE ? GROUP BY mode", (f"{today}%",))
print(cursor.fetchall())

conn.close()
