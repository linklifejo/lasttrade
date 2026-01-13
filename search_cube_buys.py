import os
log_file = r'c:\lasttrade\logs\trading_20260113.log'
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '013720' in line and (('신규 매수' in line) or ('추가 매수' in line) or ('주문 전송' in line)):
                print(line.strip())
else:
    print("Log file not found.")
