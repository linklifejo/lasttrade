import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print("=" * 80)
print("현재 보유 종목별 매수 명령 횟수 (REAL 모드)")
print("=" * 80)

# 종목별 마지막 매도 이후 매수 횟수
cursor.execute("""
    SELECT DISTINCT code FROM trades WHERE type='buy' AND mode='REAL'
""")

stocks = cursor.fetchall()
for (code,) in stocks:
    # 마지막 매도 시점
    cursor.execute("""
        SELECT MAX(timestamp) FROM trades 
        WHERE code = ? AND type = 'sell' AND mode = 'REAL'
    """, (code,))
    last_sell = cursor.fetchone()[0] or '2000-01-01'
    
    # 그 이후 매수 횟수 (DISTINCT timestamp)
    cursor.execute("""
        SELECT COUNT(DISTINCT timestamp) FROM trades 
        WHERE code = ? AND type = 'buy' AND mode = 'REAL' AND timestamp > ?
    """, (code, last_sell))
    buy_count = cursor.fetchone()[0]
    
    # 총 수량
    cursor.execute("""
        SELECT SUM(qty) FROM trades 
        WHERE code = ? AND type = 'buy' AND mode = 'REAL' AND timestamp > ?
    """, (code, last_sell))
    total_qty = cursor.fetchone()[0] or 0
    
    # 종목명 조회
    cursor.execute("""
        SELECT name FROM trades 
        WHERE code = ? AND mode = 'REAL' 
        ORDER BY timestamp DESC LIMIT 1
    """, (code,))
    name_row = cursor.fetchone()
    name = name_row[0] if name_row and name_row[0] else code
    
    if buy_count > 0:
        print(f"{name:20s} ({code}) | 매수:{buy_count}회 | 수량:{total_qty}주")

conn.close()
