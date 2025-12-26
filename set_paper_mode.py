import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def set_paper():
    conn = sqlite3.connect(DB_FILE)
    try:
        # 1. 자체 모의 서버 끔
        conn.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)", 
                     ('use_mock_server', 'false', '2025-12-26 19:56:00'))
        # 2. 키움 모의투자(Paper Trading) 켬
        conn.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)", 
                     ('is_paper_trading', 'true', '2025-12-26 19:56:00'))
        conn.commit()
        print("✅ 시스템 설정을 [키움 모의투자(PAPER)] 모드로 정확히 전환했습니다.")
    except Exception as e:
        print(f"에러: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    set_paper()
