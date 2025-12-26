import sqlite3
import datetime

today = datetime.datetime.now().strftime('%Y-%m-%d')
conn = sqlite3.connect('trading.db')
cursor = conn.execute("SELECT id, reason FROM trades WHERE type='sell' AND mode='MOCK' AND timestamp LIKE ? ORDER BY id DESC LIMIT 20", (f"{today}%",))
rows = cursor.fetchall()
conn.close()

print(f"=== MOCK 매도 사유 (최근 {len(rows)}건) ===")
for r in rows:
    print(f"ID: {r[0]}, Reason: {r[1]}")
