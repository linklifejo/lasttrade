import os
log_file = r'c:\lasttrade\logs\trading_20260113.log'
count = 0
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '013720' in line or '더큐브' in line or 'THE CUBE' in line:
                print(line.strip())
                count += 1
                if count > 100: break
else:
    print("Log file not found.")
