import asyncio
from kiwoom_adapter import get_api, fn_au10001
import json

async def cancel_specific_order(stk_cd, qty, ord_no):
    api = get_api()
    token = fn_au10001()
    
    print(f"--- 주문 취소 실행 ---")
    print(f"종목: {stk_cd}, 수량: {qty}, 주문번호: {ord_no}")
    
    if not token:
        print("토큰 없음")
        return

    try:
        # cancel_stock(stk_cd, qty, org_ord_no, token)
        res_code, res_msg = api.cancel_stock(stk_cd, str(qty), ord_no, token)
        print(f"결과 코드: {res_code}")
        print(f"결과 메시지: {res_msg}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # 대한항공 미체결 취소
    asyncio.run(cancel_specific_order('003490', 9429, '0141405'))
