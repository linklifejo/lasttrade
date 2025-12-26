import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def check_status():
    """현재 상태 확인"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    
    print("=" * 60)
    print("📊 현재 시스템 상태")
    print("=" * 60)
    
    # 1. Mock 계좌
    print("\n💰 Mock 계좌:")
    cursor = conn.execute('SELECT * FROM mock_account WHERE id=1')
    row = cursor.fetchone()
    if row:
        print(f"   현금: {row['cash']:,}원")
        print(f"   총평가: {row['total_eval']:,}원")
    
    # 2. 보유 종목
    print("\n📦 보유 종목:")
    cursor = conn.execute('''
        SELECT h.code, s.name, h.qty, h.avg_price, p.current
        FROM mock_holdings h
        LEFT JOIN mock_stocks s ON h.code = s.code
        LEFT JOIN mock_prices p ON h.code = p.code
        WHERE h.qty > 0
    ''')
    holdings = cursor.fetchall()
    if holdings:
        for h in holdings:
            name = h['name'] or h['code']
            print(f"   {name} ({h['code']}): {h['qty']}주 @ {h['avg_price']:,}원")
    else:
        print("   (없음)")
    
    # 3. 등록된 종목 수
    print("\n📋 등록된 종목:")
    cursor = conn.execute('SELECT COUNT(*) as cnt FROM mock_stocks')
    cnt = cursor.fetchone()['cnt']
    print(f"   총 {cnt}개 종목 등록됨")
    
    # 4. 최근 거래 내역
    print("\n📈 최근 거래 (Mock):")
    cursor = conn.execute('''
        SELECT * FROM trades 
        WHERE mode='MOCK' 
        ORDER BY timestamp DESC 
        LIMIT 5
    ''')
    trades = cursor.fetchall()
    if trades:
        for t in trades:
            print(f"   {t['timestamp']}: {t['type']} {t['code']} {t['qty']}주")
    else:
        print("   (없음)")
    
    # 5. 설정 확인
    print("\n⚙️  주요 설정:")
    cursor = conn.execute("SELECT key, value FROM settings WHERE key IN ('use_mock_server', 'target_stock_count', 'auto_start')")
    for row in cursor.fetchall():
        print(f"   {row['key']}: {row['value']}")
    
    conn.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_status()
