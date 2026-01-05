
import sys
import os
import time
from kiwoom.mock_api import MockKiwoomAPI
from logger import logger

def verify():
    print("=== [Verification] Mock Engine Price Movement Test ===")
    api = MockKiwoomAPI()
    
    # 1. Initial State
    stocks, summary = api.get_account_data("MOCK_TOKEN")
    if not stocks:
        print("No stocks in mock_holdings. Cannot verify movement without held stocks.")
        return
        
    print(f"Total held stocks: {len(stocks)}")
    
    # Capture prices
    prices_v1 = {s['stk_cd']: s['cur_prc'] for s in stocks}
    print(f"T1 Prices: {prices_v1}")
    
    # 2. Wait and Update
    print("Waiting 1 second for mandatory movement...")
    time.sleep(1)
    
    # 3. Get updated data
    stocks_v2, summary_v2 = api.get_account_data("MOCK_TOKEN")
    prices_v2 = {s['stk_cd']: s['cur_prc'] for s in stocks_v2}
    print(f"T2 Prices: {prices_v2}")
    
    # 4. Compare
    changed = []
    for code in prices_v1:
        if prices_v1[code] != prices_v2.get(code):
            changed.append(code)
            
    if changed:
        print(f"✅ SUCCESS: {len(changed)} stocks moved! ({', '.join(changed)})")
        for code in changed:
            print(f"  - {code}: {prices_v1[code]} -> {prices_v2[code]}")
    else:
        print("❌ FAILURE: No prices changed.")

if __name__ == "__main__":
    verify()
