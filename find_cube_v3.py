import os

log_file = r'c:\lasttrade\logs\trading_20260113.log'
target_code = '013720'

if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            if target_code in line:
                if any(x in line for x in ['신규 매수', '추가 매수', '매도 완료', '주문 전송', '조기손절', 'TrailingStop']):
                    print(f"[{line_num}] {line.strip()}")
            if line_num > 500000: # Increase range
                break
else:
    print("Log file not found.")
