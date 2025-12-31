import sqlite3
import os

# reset_mock_db.py와 동일한 경로 로직 사용
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def force_set_asset():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 1. 설정값 강제 업데이트 (존재하면 update, 없으면 insert)
        # sqlite3에는 INSERT OR REPLACE가 있습니다.
        cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('initial_asset', '500000000', datetime('now'))")
        cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('trading_capital_ratio', '70', datetime('now'))")
        
        conn.commit()
        
        # 2. 확인
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('initial_asset', 'trading_capital_ratio')")
        print(f"✅ DB 업데이트 결과 ({DB_FILE}):")
        for row in cursor.fetchall():
            print(f" - {row[0]}: {row[1]}")
            
        conn.close()
    except Exception as e:
        print(f"❌ 설정 실패: {e}")

if __name__ == "__main__":
    force_set_asset()
