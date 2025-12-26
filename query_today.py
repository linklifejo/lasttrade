import sqlite3
import os
import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def query_today_real():
    if not os.path.exists(DB_FILE):
        print("DB 파일을 찾을 수 없습니다.")
        return
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        # 오늘 날짜
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # 오늘 + REAL 모드 데이터만 상세 조회
        query = f"SELECT id, timestamp, type, code, name, qty, price, amt, mode FROM trades WHERE UPPER(mode) = 'REAL' AND timestamp LIKE '{today}%' ORDER BY id DESC"
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        
        print(f"=== [오늘: {today} | REAL 모드] 거래 내역 ===")
        if not rows:
            print("오늘 실전 투자로 저장된 데이터가 없습니다.")
        else:
            for row in rows:
                price = row['price'] if row['price'] is not None else 0
                amt = row['amt'] if row['amt'] is not None else 0
                print(f"[{row['timestamp']}] {row['type'].upper()} | {row['name']}({row['code']}) | {row['qty']}주 | {price:,.0f}원 | {amt:,.0f}원")
            print(f"\n총 {len(rows)}건의 오늘 실전 거래가 있습니다.")
            
    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    query_today_real()
