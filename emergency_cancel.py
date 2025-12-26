import asyncio
import time
from kiwoom_adapter import get_api, fn_au10001
from logger import logger

async def cancel_all():
    api = get_api()
    token = fn_au10001()
    print(f"Token: {token[:10]}...")
    
    orders = api.get_outstanding_orders(token)
    print(f"Found {len(orders)} outstanding orders.")
    
    for order in orders:
        ord_no = order.get('ord_no', order.get('ORD_NO', ''))
        stk_cd = order.get('stk_cd', order.get('STK_CD', ''))
        qty = order.get('ord_qty', order.get('ORD_QTY', '0'))
        print(f"Cancelling {stk_cd} (No: {ord_no})...")
        code, msg = api.cancel_stock(stk_cd, qty, ord_no, token)
        print(f" Result: {code} / {msg}")

if __name__ == "__main__":
    asyncio.run(cancel_all())
