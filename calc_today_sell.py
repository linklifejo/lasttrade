import sqlite3
import datetime

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

today = datetime.date.today().strftime('%Y-%m-%d')
print(f"=== {today} 매도 현황 집계 ===\n")

# REAL 모드 매도 집계
cursor.execute("""
    SELECT SUM(amt), COUNT(*) 
    FROM trades 
    WHERE type='sell' AND timestamp LIKE ? AND mode='REAL'
""", (f"{today}%",))

row = cursor.fetchone()
total_sell_amt = int(row[0]) if row[0] else 0
sell_count = row[1]

print(f"💰 총 매도 금액: {total_sell_amt:,.0f}원 (총 {sell_count}건)\n")

if sell_count > 0:
    print("[상세 내역]")
    cursor.execute("""
        SELECT timestamp, name, qty, amt, profit_rate, reason 
        FROM trades 
        WHERE type='sell' AND timestamp LIKE ? AND mode='REAL'
        ORDER BY timestamp
    """, (f"{today}%",))
    
    for row in cursor.fetchall():
        ts, name, qty, amt, profit, reason = row
        ts_time = ts.split(' ')[1]
        print(f"- {ts_time} | {name} {qty}주 | {amt:,.0f}원 | {profit}% | {reason}")

conn.close()
