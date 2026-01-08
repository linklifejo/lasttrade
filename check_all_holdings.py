import sqlite3

conn = sqlite3.connect('trading.db')

# 현재 보유 중인 모든 종목
print("=== 현재 보유 종목 ===\n")
cursor = conn.execute("""
    SELECT h.code, s.name, h.qty, h.avg_price
    FROM mock_holdings h
    LEFT JOIN mock_stocks s ON h.code = s.code
    WHERE h.qty > 0
    ORDER BY h.code
""")

holdings = cursor.fetchall()

for code, name, qty, avg_price in holdings:
    print(f"\n[{code}] {name or '이름없음'}")
    print(f"  보유: {qty}주 @ {avg_price:,.0f}원")
    
    # trades 테이블에서 거래 내역 확인
    cursor2 = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN type='buy' THEN 1 ELSE 0 END) as buys,
               SUM(CASE WHEN type='sell' THEN 1 ELSE 0 END) as sells
        FROM trades 
        WHERE mode='MOCK' AND code=?
    """, (code,))
    
    total, buys, sells = cursor2.fetchone()
    print(f"  거래 기록: 총 {total}건 (매수 {buys or 0}회, 매도 {sells or 0}회)")
    
    # 마지막 매도 이후 매수 횟수
    cursor2 = conn.execute("""
        SELECT COUNT(*) FROM trades 
        WHERE mode = 'MOCK' AND code = ? AND type = 'buy'
        AND timestamp > (
            SELECT COALESCE(MAX(timestamp), '2000-01-01') 
            FROM trades 
            WHERE mode = 'MOCK' AND code = ? AND type = 'sell'
        )
    """, (code, code))
    
    step = cursor2.fetchone()[0]
    print(f"  계산된 단계: {step}차")
    
    if total == 0:
        print(f"  ⚠️ WARNING: trades 테이블에 거래 기록이 없습니다!")

conn.close()
