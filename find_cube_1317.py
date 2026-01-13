import os
log_file = r'c:\lasttrade\logs\trading_20260113.log'
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        found = False
        for line in f:
            if '013720' in line and '13:17' in line:
                print(line.strip())
                found = True
            elif found and '013720' in line:
                print(line.strip())
            else:
                found = False
else:
    print("Log file not found.")
