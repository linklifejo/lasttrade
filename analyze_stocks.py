from database_helpers import get_system_status, get_setting
import json
import time

def analyze_stocks():
    status_data = get_system_status()
    if not status_data:
        print("Status not found.")
        return
        
    summary = status_data.get('summary', {})
    print(f"Summary: {json.dumps(summary, indent=2)}")
    
    holdings = status_data.get('holdings', [])
    total_asset = summary.get('total_asset', 0)
    target_cnt = float(get_setting('target_stock_count', 5))
    cap_ratio = float(get_setting('trading_capital_ratio', 70)) / 100.0
    split_cnt = int(float(get_setting('split_buy_cnt', 5)))
    
    alloc_per_stock = (total_asset * cap_ratio) / target_cnt
    
    weights = []
    for i in range(split_cnt):
        if i < 2: weights.append(1)
        else: weights.append(weights[-1] * 2)
    total_weight = sum(weights)
    cumulative_ratios = []
    curr_s = 0
    for w in weights:
        curr_s += w
        cumulative_ratios.append(curr_s / total_weight)
        
    print(f"\nAlloc per Stock: {alloc_per_stock:,.0f}")
    print(f"Split Count: {split_cnt}")
    print(f"Cumulative Ratios: {[f'{r*100:.1f}%' for r in cumulative_ratios]}")
    
    for stk in holdings:
        name = stk.get('stk_nm')
        code = stk.get('stk_cd')
        pur_amt = stk.get('pur_amt', 0)
        step = stk.get('watering_step')
        ratio = pur_amt / alloc_per_stock if alloc_per_stock > 0 else 0
        
        print(f"\n[{name} ({code})]")
        print(f"Pur Amt: {pur_amt:,}")
        print(f"Fill Ratio: {ratio*100:.2f}%")
        print(f"Current UI Step: {step}")
        
        step_idx = 0
        for i, th in enumerate(cumulative_ratios):
            if ratio >= (th * 0.90):
                step_idx = i + 1
            else:
                break
        print(f"Calculated Step Idx: {step_idx}")

if __name__ == "__main__":
    analyze_stocks()
