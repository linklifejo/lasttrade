import os
log_file = r'c:\lasttrade\logs\trading_20260113.log'
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            if '013720' in line:
                print(f"[{i}] {line.strip()}")
                if i > 50000: # Limit output
                     break
else:
    print("Log file not found.")
