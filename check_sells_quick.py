import sqlite3
import datetime

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# 전체 매도 건수
cursor.execute("SELECT COUNT(*) FROM trades WHERE type='sell'")
total = cursor.fetchone()[0]
print(f"\n전체 매도 건수: {total}건")

# 오늘 매도 건수
today = datetime.datetime.now().strftime('%Y-%m-%d')
cursor.execute("SELECT COUNT(*) FROM trades WHERE type='sell' AND timestamp LIKE ?", (f'{today}%',))
today_count = cursor.fetchone()[0]
print(f"오늘 매도 건수: {today_count}건")

# 최근 10건
cursor.execute("""
    SELECT id, timestamp, name, qty, price, profit_rate, reason, mode 
    FROM trades 
    WHERE type='sell' 
    ORDER BY id DESC 
    LIMIT 10
""")

rows = cursor.fetchall()
print(f"\n=== 최근 매도 10건 ===")
if rows:
    for i, row in enumerate(rows, 1):
        print(f"{i}. [{row[7]}] {row[1]} | {row[2]} | {row[3]}주 @ {row[4]:,}원 | {row[5]:.2f}% | {row[6]}")
else:
    print("매도 기록 없음")

conn.close()
