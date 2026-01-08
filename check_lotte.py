import sqlite3

conn = sqlite3.connect('trading.db')

# 롯데리조트월드 (032560) 거래 내역
print("=== 롯데리조트월드 (032560) 전체 거래 내역 ===\n")
cursor = conn.execute("""
    SELECT timestamp, type, qty, amt 
    FROM trades 
    WHERE mode='MOCK' AND code='032560' 
    ORDER BY timestamp
""")

rows = cursor.fetchall()
buy_count = 0
sell_count = 0

for i, row in enumerate(rows, 1):
    timestamp, trade_type, qty, amt = row
    if trade_type == 'buy':
        buy_count += 1
        print(f"{i}. [매수 {buy_count}차] {timestamp} | {qty}주 | {amt:,.0f}원")
    else:
        sell_count += 1
        print(f"{i}. [매도] {timestamp} | {qty}주 | {amt:,.0f}원")

print(f"\n총 거래: {len(rows)}건 (매수 {buy_count}회, 매도 {sell_count}회)")

# 마지막 매도 이후 매수 횟수
print("\n=== 마지막 매도 이후 매수 횟수 계산 ===\n")
cursor = conn.execute("""
    SELECT COUNT(*) FROM trades 
    WHERE mode = 'MOCK' AND code = '032560' AND type = 'buy'
    AND timestamp > (
        SELECT COALESCE(MAX(timestamp), '2000-01-01') 
        FROM trades 
        WHERE mode = 'MOCK' AND code = '032560' AND type = 'sell'
    )
""")

recent_buy_count = cursor.fetchone()[0]
print(f"마지막 매도 이후 매수 횟수: {recent_buy_count}회")
print(f"→ 단계: {recent_buy_count}차")

# 현재 보유 수량
cursor = conn.execute("SELECT qty FROM mock_holdings WHERE code='032560'")
row = cursor.fetchone()
if row:
    print(f"현재 보유: {row[0]}주")

conn.close()
