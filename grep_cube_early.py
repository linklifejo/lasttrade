import os
log_file = r'c:\lasttrade\logs\trading_20260113.log'
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # Check for the stock code or name and look around the 09:00 - 09:10 range
            if '09:0' in line and ('013720' in line or '더큐브' in line or 'THE CUBE' in line):
                print(line.strip())
else:
    print("Log file not found.")
