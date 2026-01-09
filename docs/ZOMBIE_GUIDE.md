# 좀비 프로세스 해결 가이드

## 🧟 문제 상황
트레이딩 봇을 종료했는데도 백그라운드에서 프로세스가 계속 실행되는 경우

## ✅ 해결 방법

### 방법 1: 일반 종료 (권장)
```bash
python stop.py
```
- 정상적인 종료 스크립트
- bot.py, web_server.py, watchdog.py, start.py 모두 종료
- 포트 8080 정리
- 모든 락 파일 삭제

### 방법 2: 강력한 종료 (좀비가 남아있을 때)
```bash
python kill_zombies.py
```
- 모든 좀비 프로세스를 강제 종료
- 4단계 정리 프로세스:
  1. WMIC로 프로세스 종료
  2. 포트 8080 점유 프로세스 종료
  3. 고아 Python 프로세스 검색 및 종료
  4. 락 파일 정리
- 최종 확인 및 검증

### 방법 3: 수동 확인
PowerShell에서 실행:
```powershell
# 실행 중인 봇 프로세스 확인
Get-WmiObject Win32_Process | Where-Object {
    $_.CommandLine -match "bot\.py|web_server\.py|watchdog\.py|start\.py"
} | Select-Object ProcessId, CommandLine

# 포트 8080 사용 프로세스 확인
Get-NetTCPConnection -LocalPort 8080 | Select-Object OwningProcess
```

## 🔧 개선 사항

### stop.py 개선
- ✅ `bot.py` 프로세스 종료 추가
- ✅ PowerShell 명령 안정성 개선 (`-NoProfile`, 에러 핸들링)
- ✅ 모든 락 파일 정리 (`main.lock`, `web.lock`, `bot.lock`, `trading.lock`)
- ✅ 고아 Python 프로세스 정리 추가

### start.py 개선
- ✅ `cleanup_before_start()` 함수에 `bot.py` 종료 추가
- ✅ 모든 락 파일 정리

### 새로운 kill_zombies.py
- ✅ 4단계 정리 프로세스
- ✅ 최종 검증 단계
- ✅ 상세한 로그 출력

## 🚀 사용 시나리오

### 정상 시작/종료
```bash
# 시작
python start.py

# 종료
python stop.py
```

### 좀비 프로세스가 남아있을 때
```bash
# 강력한 정리
python kill_zombies.py

# 재시작
python start.py
```

### Watchdog 모드 (자동 재시작)
```bash
# Watchdog로 시작 (비정상 종료 시 자동 재시작)
python watchdog.py

# 종료 (Ctrl+C 또는 stop.py)
python stop.py
```

## 💡 팁

1. **시작 전 항상 정리**: `start.py`는 자동으로 이전 프로세스를 정리합니다
2. **좀비가 의심될 때**: `kill_zombies.py`를 실행하여 완전히 정리
3. **포트 충돌**: 8080 포트가 이미 사용 중이면 `stop.py` 또는 `kill_zombies.py` 실행
4. **락 파일 에러**: 수동으로 `*.lock` 파일 삭제 가능

## 🔍 트러블슈팅

### "Port 8080 already in use" 에러
```bash
python kill_zombies.py
```

### 프로세스가 계속 살아있음
1. `kill_zombies.py` 실행
2. 작업 관리자에서 수동으로 Python 프로세스 종료
3. 시스템 재시작 (최후의 수단)

### 락 파일 에러
```bash
# Windows
del *.lock

# 또는 Python으로
python -c "import os, glob; [os.remove(f) for f in glob.glob('*.lock')]"
```
