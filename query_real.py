import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def query_real():
    if not os.path.exists(DB_FILE):
        print("DB 파일을 찾을 수 없습니다.")
        return
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        # REAL 모드 데이터만 상세 조회
        cursor = conn.execute("SELECT id, timestamp, type, code, name, qty, price, amt, mode FROM trades WHERE UPPER(mode) = 'REAL' ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        
        print("=== [REAL 모드] 최근 20건 거래 내역 ===")
        if not rows:
            print("REAL 모드로 저장된 데이터가 없습니다.")
        else:
            for row in rows:
                price = row['price'] if row['price'] is not None else 0
                amt = row['amt'] if row['amt'] is not None else 0
                print(f"[{row['timestamp']}] {row['type'].upper()} | {row['name']}({row['code']}) | {row['qty']}주 | {price:,.0f}원 | {amt:,.0f}원")
        
        # 전체 통계 확인
        cursor = conn.execute("SELECT mode, COUNT(*) as cnt FROM trades GROUP BY mode")
        print("\n=== 전체 데이터 분포 (모드별) ===")
        for row in cursor.fetchall():
            print(f"모드: {row['mode']} | 건수: {row['cnt']}건")
            
    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    query_real()
