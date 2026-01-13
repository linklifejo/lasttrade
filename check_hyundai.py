import sqlite3
import datetime

def check_hyundai():
    conn = sqlite3.connect('c:/lasttrade/trading.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. 현대차 거래 기록 확인
    rows = cursor.execute("SELECT id, timestamp, type, name, qty, price, amt, mode FROM trades WHERE code = '005380' OR name LIKE '%현대차%' ORDER BY id DESC LIMIT 20").fetchall()
    print("=== 현대차 거래 기록 ===")
    for r in rows:
        print(f"[{r['timestamp']}] {r['type']} | {r['name']}({r['mode']}) | {r['qty']}주 | {r['price']:,}원 | 총 {r['amt']:,}원")
    
    # 2. 현재 설정 확인
    settings = cursor.execute("SELECT key, value FROM settings WHERE key IN ('target_stock_count', 'trading_capital_ratio', 'split_buy_cnt', 'min_purchase_amount', 'early_stop_step')").fetchall()
    print("\n=== 현재 설정 ===")
    for s in settings:
        print(f"{s['key']}: {s['value']}")
        
    conn.close()

if __name__ == "__main__":
    check_hyundai()
