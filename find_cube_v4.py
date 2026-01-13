import os

log_file = r'c:\lasttrade\logs\trading_20260113.log'

if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            if '-9.' in line or '013720' in line:
                if '매도' in line or '체결' in line or '손절' in line or '주문' in line:
                    print(f"[{line_num}] {line.strip()}")
            if line_num > 1000000:
                break
else:
    print("Log file not found.")
