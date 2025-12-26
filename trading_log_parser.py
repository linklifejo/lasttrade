import re
import os
import datetime

# Base Log Directory
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, 'logs', f'trading_{datetime.datetime.now().strftime("%Y%m%d")}.log')

def get_trading_logs(days_to_check=3):
    """
    Parses the log files (last N days) to extract both BUY and SELL events.
    Returns a dictionary: {'buys': [], 'sells': []}
    """
    buys = []
    sells = []
    seen_buys = set()
    seen_sells = set()

    # Regex Patterns
    # Sell: 2025-12-18 11:28:44 [main.py:100] INFO - 🔵 삼성전자 10주 익절 완료 (수익율: 2.35%)
    # Or: 2025-12-18 11:28:44 [main.py:100] INFO - 🔴 삼성전자 10주 손절 완료 (수익율: -2.35%)
    # sell_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*INFO - [🔵🔴] (.*?) (\d+)주 (.*?) 완료 \(수익율: (.*?)%\)')
    sell_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*INFO - [🔵🔴]\s+(.*?)\s+(\d+)주\s+(.*?)\s+완료\s+\(수익율:\s+(.*?)%\)')
    
    # Buy: 2025-12-20 12:16:12 ... INFO - 삼성전자 10주 매수 주문 전송 완료
    # buy_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*INFO - (.*?) (\d+)주 매수 주문 전송 완료')
    buy_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*INFO\s+-\s+(.*?)\s+(\d+)주\s+매수\s+주문\s+전송\s+완료')

    # Reasons Map
    time_cut_pattern = re.compile(r'\[Time-Cut\] (.*?):')
    sl_pattern = re.compile(r'\[손절 진행\] (.*?):')
    ts_pattern = re.compile(r'\[트레일링 스탑 발동\] (.*?):')

    last_reason_map = {} 
    
    # Date Loop (Past -> Present)
    today = datetime.datetime.now()
    target_dates = []
    for i in range(days_to_check - 1, -1, -1):
        target_dates.append(today - datetime.timedelta(days=i))

    for date_obj in target_dates:
        date_str = date_obj.strftime("%Y%m%d")
        candidates = []
        base_name = f'trading_{date_str}.log'
        
        # Rotated files first (oldest to newest logic roughly)
        for k in range(10, 0, -1):
            rotated_name = f"{base_name}.{k}"
            full_path = os.path.join(LOG_DIR, 'logs', rotated_name)
            if os.path.exists(full_path):
                candidates.append(full_path)
        
        # Base file
        base_path = os.path.join(LOG_DIR, 'logs', base_name)
        if os.path.exists(base_path):
            candidates.append(base_path)

        for file_path in candidates:
            content = _read_file_safe(file_path)
            if not content: continue
            
            lines = content.splitlines()
            for line in lines:
                line = line.strip()

                # 1. Track Sell Reasons
                tc_match = time_cut_pattern.search(line)
                if tc_match: last_reason_map[tc_match.group(1).strip()] = "TimeCut (지루함)"
                
                sl_match = sl_pattern.search(line)
                if sl_match: last_reason_map[sl_match.group(1).strip()] = "StopLoss (물타기 실패)"
        
                ts_match = ts_pattern.search(line)
                if ts_match: last_reason_map[ts_match.group(1).strip()] = "TrailingStop (추세추종)"
        
                # 2. Check BUY
                buy_match = buy_pattern.search(line)
                if buy_match:
                    time_str = buy_match.group(1)
                    stock_name = buy_match.group(2).strip()
                    qty = buy_match.group(3)
                    
                    unique_key = f"{time_str}_{stock_name}_{qty}"
                    if unique_key not in seen_buys:
                        buys.append({
                            "id": unique_key, # Added ID
                            "time": time_str,
                            "name": stock_name,
                            "qty": qty,
                            "type": "Buy"
                        })
                        seen_buys.add(unique_key)
                    continue 
        
                # 3. Check SELL
                sell_match = sell_pattern.search(line)
                if sell_match:
                    time_str = sell_match.group(1)
                    stock_name = sell_match.group(2).strip()
                    qty = sell_match.group(3)
                    type_str = sell_match.group(4)
                    profit_rate = sell_match.group(5)
                    
                    unique_key = f"{time_str}_{stock_name}_{qty}"
                    if unique_key in seen_sells:
                        continue
                    seen_sells.add(unique_key)

                    if "익절" in type_str:
                        reason = "TakeProfit (익절)"
                    elif "상한가" in type_str:
                        reason = "UpperLimit (상한가)"
                    else:
                        reason = last_reason_map.get(stock_name, "StopLoss (일반 손절)")
        
                    sells.append({
                        "id": unique_key, # Added ID
                        "time": time_str,
                        "name": stock_name,
                        "qty": qty,
                        "profit_rate": profit_rate,
                        "reason": reason,
                        "type": "Sell" # Added type explicitly
                    })
                    
                    if stock_name in last_reason_map:
                        del last_reason_map[stock_name]

    # Sort Descending (Newest first)
    buys.sort(key=lambda x: x['time'], reverse=True)
    sells.sort(key=lambda x: x['time'], reverse=True)
    
    return {'buys': buys, 'sells': sells}


def _read_file_safe(path):
    encodings = ['utf-8', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except: continue
    try:
        with open(path, 'rb') as f:
            return f.read().decode('utf-8', errors='ignore')
    except:
        return None

if __name__ == "__main__":
    logs = get_trading_logs()
    print(f"Buys: {len(logs['buys'])}")
    for b in logs['buys']: print(b)
    print("-" * 20)
    print(f"Sells: {len(logs['sells'])}")
    for s in logs['sells']: print(s)
