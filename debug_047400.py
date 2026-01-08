import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print("=" * 80)
print("콜라리스생명 (047400) 상세 매수 기록")
print("=" * 80)

cursor.execute("""
    SELECT timestamp, type, qty, price, mode 
    FROM trades 
    WHERE code = '047400' 
    ORDER BY timestamp DESC
    LIMIT 20
""")

rows = cursor.fetchall()
for row in rows:
    print(f"{row[0]} | {row[1]:4s} | {row[2]:3d}주 | {row[3]:8.0f}원 | {row[4]}")

print("\n" + "=" * 80)
print("마지막 매도 이후 매수 횟수 (DISTINCT timestamp)")
print("=" * 80)

cursor.execute("""
    SELECT MAX(timestamp) FROM trades 
    WHERE code = '047400' AND type = 'sell' AND mode = 'REAL'
""")
last_sell = cursor.fetchone()[0] or '2000-01-01'
print(f"마지막 매도: {last_sell}")

cursor.execute("""
    SELECT COUNT(DISTINCT timestamp) FROM trades 
    WHERE code = '047400' AND type = 'buy' AND mode = 'REAL' AND timestamp > ?
""", (last_sell,))
buy_count = cursor.fetchone()[0]
print(f"매수 명령 횟수: {buy_count}회")

cursor.execute("""
    SELECT SUM(qty) FROM trades 
    WHERE code = '047400' AND type = 'buy' AND mode = 'REAL' AND timestamp > ?
""", (last_sell,))
total_qty = cursor.fetchone()[0] or 0
print(f"총 보유 수량: {total_qty}주")

print("\n" + "=" * 80)
print("각 매수 시점별 상세")
print("=" * 80)

cursor.execute("""
    SELECT timestamp, qty, price FROM trades 
    WHERE code = '047400' AND type = 'buy' AND mode = 'REAL' AND timestamp > ?
    ORDER BY timestamp ASC
""", (last_sell,))

buy_records = cursor.fetchall()
for i, (ts, qty, price) in enumerate(buy_records, 1):
    print(f"{i}번째 매수: {ts} | {qty}주 @ {price:,.0f}원")

conn.close()
