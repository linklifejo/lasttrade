import os

log_file = r'c:\lasttrade\logs\trading_20260113.log'
target_code = '013720'

if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            if target_code in line:
                # Print only the first 50 relevant lines to see the initial activity
                print(f"[{line_num}] {line.strip()}")
                if '매수' in line or 'buy' in line.lower() or 'sell' in line.lower() or '주문' in line:
                     # Stop after finding the first few trade-related lines
                     pass
            if line_num > 100000: # Safety cap
                break
else:
    print("Log file not found.")
