import sqlite3

conn = sqlite3.connect('trading.db')

# 현재 보유 중인 종목들의 매수 거래 내역 조회
print("=== 현재 보유 종목의 매수 거래 내역 ===\n")

cursor = conn.execute("""
    SELECT code, timestamp, type, qty, amt 
    FROM trades 
    WHERE mode='MOCK' 
    AND code IN (SELECT code FROM mock_holdings WHERE qty > 0)
    ORDER BY code, timestamp
""")

current_code = None
buy_count = 0

for row in cursor.fetchall():
    code, timestamp, trade_type, qty, amt = row
    
    if code != current_code:
        if current_code:
            print(f"  → 총 매수 횟수: {buy_count}회\n")
        current_code = code
        buy_count = 0
        print(f"[{code}]")
    
    if trade_type == 'buy':
        buy_count += 1
        print(f"  {buy_count}차 매수: {timestamp} | {qty}주 | {amt:,}원")
    else:
        print(f"  매도: {timestamp} | {qty}주 | {amt:,}원")

if current_code:
    print(f"  → 총 매수 횟수: {buy_count}회\n")

# 각 종목별 마지막 매도 이후 매수 횟수 계산
print("\n=== 종목별 단계 계산 (마지막 매도 이후 매수 횟수) ===\n")

cursor = conn.execute("SELECT code, qty FROM mock_holdings WHERE qty > 0")
holdings = cursor.fetchall()

for code, qty in holdings:
    cursor = conn.execute('''
        SELECT COUNT(*) FROM trades 
        WHERE mode = 'MOCK' AND code = ? AND type = 'buy'
        AND timestamp > (
            SELECT COALESCE(MAX(timestamp), '2000-01-01') 
            FROM trades 
            WHERE mode = 'MOCK' AND code = ? AND type = 'sell'
        )
    ''', (code, code))
    
    buy_count = cursor.fetchone()[0]
    print(f"{code}: {qty}주 보유 → {buy_count}차 (매수 {buy_count}회)")

conn.close()
