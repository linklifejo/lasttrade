from database_helpers import save_setting, get_setting, get_db_connection
import sqlite3

print("🛠 [Fix] 매수 안되는 문제 해결 시작...")

# 1. 목표 종목 수 5개로 설정 (현재 1개로 되어 있음)
old_cnt = get_setting('target_stock_count', 1)
save_setting('target_stock_count', 5)
print(f"✅ 목표 종목 수 변경: {old_cnt} -> 5")

# 2. Mock 모드 보유 목록 초기화 (유령 종목 제거)
try:
    with get_db_connection() as conn:
        conn.execute("DELETE FROM mock_holdings")
        # trades 테이블은 기록용이므로 놔두되, 굳이 깨끗하게 하려면 아래 주석 해제
        # conn.execute("DELETE FROM trades WHERE mode = 'MOCK'")
        conn.commit()
    print("✅ Mock 보유 목록 초기화 완료 (유령 종목 제거)")
except Exception as e:
    print(f"❌ DB 초기화 실패: {e}")

# 3. 추가 매수 간격 등 필수 설정 확인
print(f"📍 추가매수간격: {get_setting('additional_buy_interval', 4)}%")
print(f"📍 분할매수횟수: {get_setting('split_buy_cnt', 5)}회")

print("\n🚀 설정 수정 완료! 이제 봇이 새로운 종목을 찾아 매수할 것입니다.")
