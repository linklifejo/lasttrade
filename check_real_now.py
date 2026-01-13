from kiwoom_adapter import get_token, get_account_data, get_balance
import asyncio

async def check_real():
    token = get_token()
    if not token:
        print("❌ Failed to get token")
        return
    
    # 1. 예수금 확인
    bal = get_balance(token=token)
    print(f"=== REAL 계좌 잔고 ===")
    print(f"예수금: {bal[2]:,}원")
    print(f"총평가금: {bal[1]:,}원")
    
    # 2. 보유 종목 확인
    stocks, summary = get_account_data(token=token)
    print(f"\n=== REAL 보유 종목 ({len(stocks)}개) ===")
    for s in stocks:
        name = s.get('stk_nm', 'Unknown')
        code = s.get('stk_cd', 'Unknown')
        qty = s.get('rmnd_qty', 0)
        pchs_avg = s.get('pchs_avg_pric', 0)
        print(f"[{code}] {name}: {qty}주 (평단 {pchs_avg}원)")

if __name__ == "__main__":
    asyncio.run(check_real())
