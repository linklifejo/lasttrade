from kiwoom_adapter import fn_kt00004
import sys

# 강제로 REAL 모드 설정 (필요하다면)
# 하지만 fn_kt00004는 모드를 인자로 받지 않고 내부 설정 따름.
# 따라서 설정을 잠시 REAL로 속이거나, 직접 API 호출해야 함.
# 여기선 DB 설정이 REAL로 되어있으므로 그냥 호출하면 됨.

print("=== REAL 계좌 잔고 조회 ===")
try:
    # mode='REAL' 따위의 인자가 없으므로, 현재 설정(Real)을 믿고 호출
    stocks, summary = fn_kt00004()
    
    if not stocks:
        print("보유 종목 없음 (전량 매도 성공 추정)")
    else:
        for s in stocks:
            name = s.get('stk_nm', 'Unknown')
            qty = s.get('rmnd_qty', s.get('hold_qty', 0))
            print(f"[{name}] {qty}주 보유 중")
            
except Exception as e:
    print(f"조회 실패: {e}")
