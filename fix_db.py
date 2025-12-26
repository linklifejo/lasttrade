import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def fix():
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("DROP TABLE IF EXISTS system_status")
        conn.commit()
        print("✅ system_status 테이블을 초기화했습니다. (재시작 시 신규 스키마로 생성됩니다.)")
    except Exception as e:
        print(f"에러: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix()
