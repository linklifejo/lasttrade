import os

log_file = 'logs/trading_20260108.log'
if not os.path.exists(log_file):
    print("로그 파일이 없습니다.")
else:
    try:
        with open(log_file, 'rb') as f:  # 바이너리 모드로 읽기 (인코딩 무시)
            f.seek(0, os.SEEK_END)
            filesize = f.tell()
            seek_pos = max(0, filesize - 5000)
            f.seek(seek_pos)
            content = f.read()
            # 디코딩 시도 (깨진 글자는 무시)
            text = content.decode('utf-8', errors='ignore')
            
            print("=== LOG LAST 50 LINES ===")
            lines = text.splitlines()[-50:]
            for line in lines:
                print(line)
                
            # AutoStart 체크
            if "[AutoStart Check]" not in text: # logger.info로 바꿨던 내용 확인
                print("\n⚠️ [AutoStart] 관련 로그가 아직 파일에 기록되지 않았습니다.")
    except Exception as e:
        print(f"로그 읽기 실패: {e}")
