import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def cleanup_duplicates():
    if not os.path.exists(DB_FILE):
        print("DB file not found")
        return
    
    conn = sqlite3.connect(DB_FILE)
    try:
        # 1. 'SELL' (대문자) 타입이면서 'sell' (소문자) 타입과 동일한 시간/종목인 행 찾기
        # log_trade_sync는 'SELL'을, log_sell_to_db는 'sell'을 사용함.
        # 'sell' 쪽이 정보(amt, reason)가 더 풍부하므로 'SELL'을 삭제.
        
        # 확인용 쿼리 (오늘 날짜 위주)
        find_query = """
        SELECT t1.id, t1.timestamp, t1.code, t1.name 
        FROM trades t1
        JOIN trades t2 ON t1.timestamp = t2.timestamp 
                      AND t1.code = t2.code 
                      AND t1.mode = t2.mode
        WHERE t1.type = 'SELL' AND t2.type = 'sell'
        """
        duplicates = conn.execute(find_query).fetchall()
        print(f"찾은 중복 데이터 개수: {len(duplicates)}건")
        
        if len(duplicates) > 0:
            delete_query = """
            DELETE FROM trades 
            WHERE id IN (
                SELECT t1.id 
                FROM trades t1
                JOIN trades t2 ON t1.timestamp = t2.timestamp 
                              AND t1.code = t2.code 
                              AND t1.mode = t2.mode
                WHERE t1.type = 'SELL' AND t2.type = 'sell'
            )
            """
            cursor = conn.execute(delete_query)
            conn.commit()
            print(f"성공적으로 {cursor.rowcount}건의 중복 데이터를 삭제했습니다.")
        else:
            print("삭제할 중복 데이터가 없습니다.")
            
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup_duplicates()
