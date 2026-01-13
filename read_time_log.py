import os
log_file = r'c:\lasttrade\logs\trading_20260113.log'
count = 0
with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if '09:06' in line:
            print(line.strip())
            count += 1
            if count > 50: break
