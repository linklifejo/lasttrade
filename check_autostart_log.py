import os
import time

log_file = 'logs/trading_20260108.log'
target_keyword = "[AutoStart Check]"

print(f"로그 파일 '{log_file}'에서 '{target_keyword}' 검색 중...")

if os.path.exists(log_file):
    found = False
    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        # 파일 끝에서부터 역순으로 읽으면 좋겠지만 간단히 전체 읽고 마지막 매칭 확인
        lines = f.readlines()
        for line in reversed(lines):
            if target_keyword in line:
                print(f"✅ 발견: {line.strip()}")
                found = True
                break
    
    if not found:
        print("❌ 아직 로그에 해당 키워드가 기록되지 않았습니다.")
else:
    print("❌ 로그 파일이 없습니다.")
