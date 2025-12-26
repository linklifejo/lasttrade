import sqlite3
import os
import json

def check_db():
    db_path = 'trading.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=== Mock Holdings (보유종목 - mock_holdings) ===")
    try:
        cursor.execute("SELECT * FROM mock_holdings")
        rows = cursor.fetchall()
        if not rows:
            print("보유 종목 데이터가 없습니다. (전량 매도 추정)")
        else:
            for row in rows:
                print(dict(row))
    except Exception as e:
        print(f"Error checking mock_holdings: {e}")

    print("\n=== Recent Trades (최근 매매 내역 - trades) ===")
    try:
        cursor.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 10")
        logs = cursor.fetchall()
        if logs:
            for log in logs:
                print(dict(log))
        else:
            print("매매 내역이 없습니다. (봇이 매매를 수행하지 않았음)")
    except Exception as e:
        print(f"Error checking trades: {e}")

    print("\n=== System Status (UI 데이터 - system_status) ===")
    try:
        cursor.execute("SELECT * FROM system_status WHERE id=1")
        row = cursor.fetchone()
        if row:
            status_json = row['status_json']
            print(f"Update Time: {row['updated_at']}")
            try:
                data = json.loads(status_json)
                
                print("\n --- Summary Data ---")
                summary = data.get('summary', {})
                print(json.dumps(summary, indent=2, ensure_ascii=False))
                
                holdings = data.get('holdings', [])
                print(f"\nUI Holdings Count: {len(holdings)}")
                if holdings:
                    print("First Holding Sample:", holdings[0])
            except:
                print("JSON 파싱 오류")
        else:
            print("System Status 데이터가 없습니다. (UI 빈 화면 원인)")
    except Exception as e:
        print(f"Error checking system_status: {e}")

    conn.close()

if __name__ == '__main__':
    check_db()
