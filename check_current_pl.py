from kiwoom_adapter import fn_kt00004, get_token
import json

token = get_token()
stocks = fn_kt00004(token=token)
if stocks:
    for s in stocks:
        print(f"Name: {s.get('stk_nm')}, Code: {s.get('stk_cd')}, Profit: {s.get('pl_rt')}%")
else:
    print("No holdings.")
