import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def reset_mock_data():
    """Mock 데이터 완전 초기화"""
    conn = sqlite3.connect(DB_FILE)
    try:
        # 1. Mock 관련 테이블 모두 삭제
        conn.execute("DELETE FROM mock_stocks")
        conn.execute("DELETE FROM mock_prices")
        conn.execute("DELETE FROM mock_holdings")
        conn.execute("DELETE FROM mock_account")
        
        print("✅ Mock 데이터 초기화 완료")
        print("   - mock_stocks 삭제")
        print("   - mock_prices 삭제")
        print("   - mock_holdings 삭제")
        print("   - mock_account 삭제")
        print("\n봇 재시작 시 자동으로 올바른 데이터가 생성됩니다.")
        
        conn.commit()
    except Exception as e:
        print(f"❌ 오류: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset_mock_data()
