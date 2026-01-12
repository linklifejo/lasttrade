import sqlite3
import os

db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- 2026-01-12 '우리로(046970)' 매매 기록 조회 ---")
cursor.execute("SELECT * FROM trades WHERE (code = '046970' OR name LIKE '%우리로%') AND timestamp LIKE '2026-01-12%'")
rows = cursor.fetchall()
if not rows:
    print("기록이 없습니다.")
else:
    for row in rows:
        print(f"[{row['timestamp']}] {row['name']}({row['code']}) {row['type']} {row['qty']}주 {row['price']}원, 수익률: {row['profit_rate']}%, 사유: {row['reason']}")

conn.close()
