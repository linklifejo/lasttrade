import sqlite3
import time

def fix_source():
    try:
        conn = sqlite3.connect('trading.db')
        print(f"Target DB: trading.db")
        
        # 1. 현재 상태 확인
        cursor = conn.execute("SELECT code, source FROM mock_holdings")
        rows = cursor.fetchall()
        print(f"Before Update: {rows}")
        
        # 2. 업데이트
        conn.execute("UPDATE mock_holdings SET source='모델'")
        conn.commit()
        print("Update Executed.")
        
        # 3. 결과 확인
        cursor = conn.execute("SELECT code, source FROM mock_holdings")
        rows = cursor.fetchall()
        print(f"After Update: {rows}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_source()
