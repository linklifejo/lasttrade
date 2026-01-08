from database_helpers import save_setting
from kiwoom_adapter import reset_api, fn_kt00004
import time

print("🚨 REAL 모드로 강제 전환 및 잔고 확인 중...")

# 1. 설정 강제 변경
save_setting('trading_mode', 'REAL')
save_setting('use_mock_server', False)

# 2. API 리셋 (중요)
reset_api()

time.sleep(1)

# 3. 잔고 재조회
try:
    print("=== [REAL] 잔고 조회 ===")
    stocks, summary = fn_kt00004()
    
    if isinstance(stocks, str):
        print(f"❌ 잔고 조회 에러: {stocks}")
    elif not stocks:
        print("✅ 보유 종목 없음 (전량 매도 완료된 듯)")
    else:
        for s in stocks:
            name = s.get('stk_nm', 'Unknown')
            qty = s.get('rmnd_qty', s.get('hold_qty', 0))
            print(f"⚠️ [잔존] {name}: {qty}주")
            
except Exception as e:
    print(f"❌ 조회 실패: {e}")
