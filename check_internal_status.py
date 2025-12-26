import json
import os
import sqlite3

def check():
    db_path = 'trading.db'
    if not os.path.exists(db_path):
        print("DB not found")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 설정 조회
    cursor.execute("SELECT * FROM settings WHERE key IN ('target_stock_count', 'use_mock_server', 'is_paper_trading')")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    print(f"--- Settings ---")
    print(settings)
    
    # 상태 조회 (system_status 테이블)
    cursor.execute("SELECT status_json FROM system_status WHERE id = 1")
    row = cursor.fetchone()
    if row:
        status = json.loads(row['status_json'])
        summary = status.get('summary', {})
        holdings = status.get('holdings', [])
        print(f"\n--- Bot Status ---")
        print(f"API Mode: {summary.get('api_mode')}")
        print(f"Deposit: {summary.get('deposit', 0):,}")
        print(f"Current Stocks Count: {len(holdings)}")
        print(f"Bot Running (WebSocket): {summary.get('bot_running')}")
        
    conn.close()

if __name__ == "__main__":
    check()
