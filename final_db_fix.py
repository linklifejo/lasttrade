import sqlite3
import os

def final_db_fix():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        print("Standardizing sources to '검색식' and '모델'...")
        # 1. AI 관련 데이터 -> 모델
        conn.execute("UPDATE mock_holdings SET source = '모델' WHERE source = 'AI_Model' OR source LIKE '%AI%' OR source = '모델'")
        
        # 2. 나머지는 검색식으로 간주 (Search, 조건식, Unknown, NULL 등)
        conn.execute("UPDATE mock_holdings SET source = '검색식' WHERE source != '모델' OR source IS NULL")
        
        conn.commit()
        
        # 확인
        cursor = conn.execute("SELECT code, source FROM mock_holdings")
        rows = cursor.fetchall()
        print("\n[Updated Holdings]")
        for row in rows:
            print(f"Code: {row['code']}, Source: {row['source']}")
            
        conn.close()
        print("\nDB Standardization Complete.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    final_db_fix()
