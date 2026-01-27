import sqlite3
import os

DB_FILE = 'trading.db'

def add_source_column():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 1. mock_holdings 테이블에 source 컬럼 추가 확인
        cursor.execute("PRAGMA table_info(mock_holdings)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'source' not in columns:
            print("[Update] mock_holdings 테이블에 'source' 컬럼 추가 중...")
            cursor.execute("ALTER TABLE mock_holdings ADD COLUMN source TEXT DEFAULT 'Unknown'")
            conn.commit()
            print("성공: mock_holdings.source 추가 완료")
        else:
            print("정보: mock_holdings.source 이미 존재함")
            
        conn.close()
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    add_source_column()
