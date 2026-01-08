import os

log_file = 'logs/trading_20260108.log'
if not os.path.exists(log_file):
    print("로그 파일이 없습니다.")
else:
    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
        print("=== LOG TAIL ===")
        for line in lines[-30:]:
            print(line.strip())
