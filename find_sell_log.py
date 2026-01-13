import os
log_file = r'c:\lasttrade\logs\trading_20260113.log'
lines = []
with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        lines.append(line.strip())
        if len(lines) > 5000: lines.pop(0)

found = False
for i, line in enumerate(lines):
    if '09:06:52' in line or '매도 완료' in line:
        for j in range(max(0, i-10), min(len(lines), i+10)):
            print(lines[j])
        found = True
        break

if not found:
    print("Not found in the last 5000 lines.")
