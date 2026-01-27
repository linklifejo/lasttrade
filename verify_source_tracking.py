import sqlite3
import os
import sys

# 경로 설정
sys.path.append(os.getcwd())
from database_helpers import get_db_connection

def verify_and_test():
    print("Example: Checking DB Schema and inserting a test trade...")
    
    with get_db_connection() as conn:
        # 1. 컬럼 확인
        print("[1] 'mock_holdings' 테이블 컬럼 정보 조회:")
        cursor = conn.execute("PRAGMA table_info(mock_holdings)")
        cols = [row['name'] for row in cursor.fetchall()]
        print(f"    -> Columns: {cols}")
        
        if 'source' not in cols:
            print("❌ 실패: 'source' 컬럼이 없습니다!")
            return

        print("✅ 성공: 'source' 컬럼 존재함.")

        # 2. 강제 매수 기록 삽입 (mock_api 로직 흉내)
        test_code = 'TEST99'
        test_source = 'AI_Verification_Test'
        
        print(f"\n[2] 테스트 데이터 삽입 (Code: {test_code}, Source: {test_source})")
        
        # 기존 테스트 데이터 삭제
        conn.execute("DELETE FROM mock_holdings WHERE code = ?", (test_code,))
        
        # 신규 삽입
        conn.execute('''
            INSERT INTO mock_holdings (code, qty, avg_price, current_price, updated_at, source)
            VALUES (?, 1, 10000, 10000, datetime("now"), ?)
        ''', (test_code, test_source))
        conn.commit()
        
        # 3. 조회 및 검증
        print("\n[3] DB 데이터 조회 결과:")
        cursor = conn.execute("SELECT code, qty, source FROM mock_holdings WHERE code = ?", (test_code,))
        row = cursor.fetchone()
        
        if row:
            print(f"    -> Code: {row['code']}")
            print(f"    -> Qty: {row['qty']}")
            print(f"    -> Source: {row['source']}")
            
            if row['source'] == test_source:
                print("\n🎉 [검증 성공] 소스 출처(Source)가 DB에 정확히 저장되었습니다!")
            else:
                print(f"\n❌ [검증 실패] 저장된 Source가 다릅니다: {row['source']}")
        else:
            print("\n❌ [검증 실패] 데이터가 저장되지 않았습니다.")

        # 테스트 데이터 정리
        conn.execute("DELETE FROM mock_holdings WHERE code = ?", (test_code,))
        conn.commit()

if __name__ == "__main__":
    verify_and_test()
