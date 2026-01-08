import os

log_file = 'logs/trading_20260108.log'
if not os.path.exists(log_file):
    print("로그 파일이 없습니다.")
else:
    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        # 파일 끝으로 이동 후 마지막 부분 읽기
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        seek_pos = max(0, file_size - 4000) # 마지막 4KB 정도만 읽음
        f.seek(seek_pos)
        content = f.read()
        print("=== LOG RECENT ===")
        print(content)
