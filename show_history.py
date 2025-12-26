import asyncio
from kiwoom_adapter import get_api, fn_au10001
import json

async def show_history():
    api = get_api()
    token = fn_au10001()
    
    print(f"--- 오늘 체결 내역 조회 ---")
    if not token:
        print("토큰 없음")
        return

    if hasattr(api, 'get_trade_history'):
        history = api.get_trade_history(token)
        if not history:
            print("오늘 체결 내역이 없습니다.")
        else:
            print(f"총 {len(history)}건의 체결 내역 확인:\n")
            for h in history:
                print(f"[{h.get('tm')}] {h.get('stk_nm')} | {h.get('io_tp_nm')} | 수량: {h.get('cntr_qty')} | 가격: {h.get('cntr_pric')} | 주문상태: {h.get('ord_stt')}")
    else:
        print("이 API는 체결 내역 조회를 지원하지 않습니다.")

if __name__ == "__main__":
    asyncio.run(show_history())
