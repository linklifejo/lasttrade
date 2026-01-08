import re
import os
import glob

log_dir = r"c:\lasttrade\logs"
# 가장 최신 로그 파일 찾기
list_of_files = glob.glob(os.path.join(log_dir, "trading_*.log"))
latest_file = max(list_of_files, key=os.path.getctime)

print(f"📂 분석 대상 로그: {latest_file}\n")

pattern = r"Math Filter.*매수 취소"
count = 0

print("=== AI 필터링(매수 거절) 이력 ===\n")

try:
    with open(latest_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if "Math Filter" in line:
                print(line.strip())
                if "매수 취소" in line:
                    count += 1

    print(f"\n🔍 총 {count}건의 종목이 AI(수학적 필터)에 의해 매수 거절되었습니다.")

except Exception as e:
    print(f"Log Read Error: {e}")
