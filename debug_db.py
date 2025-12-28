import sqlite3
import datetime

try:
    conn = sqlite3.connect('trading.db', timeout=10)
    cursor = conn.cursor()
    
    # 1. 설정값 확인
    print("=== Settings Check ===")
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('trading_mode', 'use_mock_server', 'is_paper_trading')")
    rows = cursor.fetchall()
    for row in rows:
        print(f"{row[0]}: {row[1]}")
        
    # 2. 로그 데이터 확인 (오늘 날짜)
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    print(f"\n=== Trading Logs Check ({today}) ===")
    
    # 모드별 데이터 개수 세기
    cursor.execute(f"SELECT mode, COUNT(*) FROM trades WHERE timestamp LIKE '{today}%' GROUP BY mode")
    log_stats = cursor.fetchall()
    for stat in log_stats:
        print(f"Mode {stat[0]}: {stat[1]} records")
        
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
