import sqlite3
import os
import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def query_mock_today():
    if not os.path.exists(DB_FILE):
        print("DB 파일을 찾을 수 없습니다.")
        return
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        print(f"--- [오늘: {today}] MOCK 데이터 조회 ---")
        
        # 오늘 MOCK 데이터 개수 확인
        query = f"SELECT COUNT(*) as cnt FROM trades WHERE UPPER(mode) = 'MOCK' AND timestamp LIKE '{today}%'"
        row = conn.execute(query).fetchone()
        print(f"오늘 MOCK 거래 건수: {row['cnt']}건")
        
        # 샘플 5건 확인
        query = f"SELECT timestamp, name, type FROM trades WHERE UPPER(mode) = 'MOCK' AND timestamp LIKE '{today}%' LIMIT 5"
        rows = conn.execute(query).fetchall()
        for r in rows:
            print(f"[{r['timestamp']}] {r['type']} | {r['name']}")
            
    except Exception as e:
        print(f"에러: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    query_mock_today()
