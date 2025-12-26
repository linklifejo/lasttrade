from database_helpers import get_system_status, get_setting
import json

def analyze_korean_air():
    # 1. Get Settings
    target_cnt = float(get_setting('target_stock_count', 5))
    cap_ratio = float(get_setting('trading_capital_ratio', 70)) / 100.0
    strategy = get_setting('single_stock_strategy', 'WATER')
    sl_rate = float(get_setting('stop_loss_rate', -1))
    
    # 2. Get Status from DB
    status_data = get_system_status()
    if not status_data:
        print("Status data not found in DB.")
        return
        
    summary = status_data.get('summary', {})
    holdings = status_data.get('holdings', [])
    total_asset = summary.get('total_asset', 0)
    
    alloc_per_stock = (total_asset * cap_ratio) / target_cnt
    
    ka = next((h for h in holdings if h.get('stk_cd') == 'A003490' or h.get('stk_cd') == '003490'), None)
    
    print(f"--- Settings ---")
    print(f"Strategy: {strategy}")
    print(f"SL Rate: {sl_rate}%")
    print(f"Target Count: {target_cnt}")
    print(f"Capital Ratio: {cap_ratio*100}%")
    print(f"Total Asset: {total_asset:,}")
    print(f"Alloc per Stock: {alloc_per_stock:,}")
    
    if ka:
        print(f"\n--- Korean Air (003490) ---")
        pchs_avg = float(ka.get('pchs_avg_pric', ka.get('avg_prc', 0)))
        qty = int(ka.get('rmnd_qty', ka.get('qty', 0)))
        cur_pchs_amt = pchs_avg * qty
        pl_rt = float(ka.get('pl_rt', 0))
        
        print(f"Current Pchs Amt: {cur_pchs_amt:,}")
        print(f"Profit Rate: {pl_rt}%")
        
        print(f"\n--- Analysis ---")
        threshold = alloc_per_stock * 0.95
        print(f"Threshold (95% of Alloc): {threshold:,.0f}원")
        
        if cur_pchs_amt < threshold:
            print(f"Current Status: [매집 중] (Fill: {cur_pchs_amt / alloc_per_stock * 100:.2f}%)")
            print(f"Reason: 'WATER' strategy prevents StopLoss during accumulation (under 95% of target allocation).")
            print(f"-> 봇은 현재 대한항공을 {int(cur_pchs_amt):,}원만큼 들고 있으며,")
            print(f"-> 목표치인 {int(alloc_per_stock):,}원의 95%인 {int(threshold):,}원에 도달할 때까지는")
            print(f"-> 손절선({sl_rate}%)을 무시하고 계속 물을 탑니다.")
        else:
            print(f"Current Status: [매집 완료] (Fill: {cur_pchs_amt / alloc_per_stock * 100:.2f}%)")
            print(f"Reason: Filled over 95%. StopLoss should be active.")
            if pl_rt >= sl_rate:
                print(f"But Profit Rate ({pl_rt}%) is NOT below StopLoss Rate ({sl_rate}%).")
            else:
                print(f"Profit Rate ({pl_rt}%) IS below StopLoss Rate ({sl_rate}%). Investigation required why it didn't sell.")
    else:
        print("\nKorean Air not found in current holdings.")
        print(f"Found stocks: {[h.get('stk_nm') for h in holdings]}")

if __name__ == "__main__":
    analyze_korean_air()
