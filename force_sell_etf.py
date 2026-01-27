
import sys
import os
import time

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kiwoom_adapter import fn_kt10001, get_token, fn_kt00004
from logger import logger

def force_sell_target():
    token = get_token()
    if not token:
        print("❌ 토큰 발급 실패")
        return

    # 1. 보유 종목 조회
    my_stocks = fn_kt00004(token=token)
    if not my_stocks:
        print("보유 종목이 없습니다.")
        return

    target_name_part = "RISE" # 키워드: RISE
    target_code = None
    target_qty = 0
    
    for s in my_stocks:
        if target_name_part in s['stk_nm']:
            target_code = s['stk_cd']
            target_qty = int(s['rmnd_qty'])
            print(f"✅ 타겟 발견: {s['stk_nm']} ({s['stk_cd']}) / 잔고: {target_qty}주")
            break
            
    if target_code and target_qty > 0:
        print(f"🚨 강제 매도 실행: {target_code} {target_qty}주")
        
        # 실제 매도 API 호출
        res_code, res_msg = fn_kt10001(target_code, str(target_qty), token=token)
        
        if str(res_code) in ['0', 'SUCCESS']:
            print("✅ 매도 주문 성공!")
            
            # DB 로그는 이 스크립트에서 직접 남기지 않고 패스 (단발성)
        else:
            print(f"❌ 매도 실패: {res_msg}")

    else:
        print(f"❌ '{target_name_part}' 포함된 종목을 찾을 수 없습니다.")

if __name__ == "__main__":
    force_sell_target()
