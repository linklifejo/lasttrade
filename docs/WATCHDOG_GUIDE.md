# 🧟 Watchdog (좀비 서버) 사용 가이드

## ✅ 성공적으로 설정 완료!

Watchdog가 `bot.py`를 감시하며, 비정상 종료 시 자동으로 재시작합니다.

## 🚀 사용 방법

### 시작
```powershell
python watchdog.py
```

### 종료
```powershell
# 방법 1: 텔레그램에서
stop

# 방법 2: 웹 대시보드에서
Stop 버튼 클릭

# 방법 3: 강제 종료
python kill_zombies.py
```

## 📊 동작 방식

### 정상 종료 (Exit Code 0)
- 텔레그램 `stop` 명령
- 웹 대시보드 `Stop` 버튼
- **결과**: Watchdog가 재시작하지 않음 ✓

### 비정상 종료 (Exit Code 1)
- 크래시, 에러 등
- **결과**: Watchdog가 5초 후 자동 재시작 ✓

## 🔍 상태 확인

### 프로세스 확인
```powershell
# Watchdog 실행 중인지 확인
Get-Process python | Where-Object { $_.CommandLine -match "watchdog\.py" }

# bot.py 실행 중인지 확인
Get-Process python | Where-Object { $_.CommandLine -match "bot\.py" }
```

### 생존 신고
Watchdog는 1분마다 콘솔에 생존 신고를 출력합니다:
```
[HH:MM] [WATCHDOG] 👮 이상 무! 봇이 열심히 매매 중입니다.
```

## 🎯 주요 수정 사항

1. **Watchdog 타겟 변경**: `start.py` → `bot.py`
   - 이전: start.py를 감시 (불필요한 중첩)
   - 현재: bot.py를 직접 감시 (효율적)

2. **Stop 명령 개선**: 
   - 텔레그램 stop → 프로그램 종료 (exit code 0)
   - 웹 대시보드 stop → 프로그램 종료 (exit code 0)
   - Watchdog가 정상 종료 감지 → 재시작 안 함

3. **좀비 프로세스 정리**:
   - `stop.py`: bot.py 종료 추가
   - `kill_zombies.py`: 4단계 강력한 정리
   - `start.py`: cleanup 개선

## 📁 관련 파일

- `watchdog.py` - 좀비 서버 메인
- `bot.py` - 트레이딩 봇 (수정: stop 명령 시 종료)
- `stop.py` - 정상 종료 스크립트
- `kill_zombies.py` - 강력한 종료 스크립트
- `ZOMBIE_GUIDE.md` - 좀비 프로세스 해결 가이드
- `STOP_TEST_GUIDE.md` - Stop 명령 테스트 가이드

## 💡 팁

### 시작 시 락 파일 에러
```powershell
# 락 파일 정리
Remove-Item -Path "*.lock" -ErrorAction SilentlyContinue
python watchdog.py
```

### Watchdog 없이 실행
```powershell
# 일반 모드 (자동 재시작 없음)
python start.py

# 또는 bot.py 직접 실행
python bot.py
```

### 로그 확인
```powershell
# 최근 로그 확인
Get-Content -Path "logs\trading_$(Get-Date -Format 'yyyyMMdd').log" -Tail 50
```

## 🎉 테스트 결과

✅ **Watchdog 정상 작동**
- bot.py 감시 중
- 1분마다 생존 신고
- 정상 종료 시 재시작 안 함
- 비정상 종료 시 자동 재시작

✅ **Stop 명령 작동**
- 텔레그램 stop → 프로그램 종료 확인
- 웹 대시보드 stop → 프로그램 종료 확인
- Exit code 0 → Watchdog 재시작 안 함

✅ **좀비 프로세스 정리**
- kill_zombies.py → 모든 프로세스 정리
- stop.py → 정상 종료
- 락 파일 자동 정리

## 🔧 문제 해결

### 문제: Watchdog가 계속 재시작함
**원인**: bot.py가 비정상 종료 (exit code 1)
**해결**: 로그 확인하여 에러 수정

### 문제: Stop 명령이 작동하지 않음
**원인**: bot.py 수정 사항이 적용되지 않음
**해결**: 
```powershell
python kill_zombies.py
python watchdog.py
```

### 문제: 락 파일 에러
**원인**: 이전 프로세스가 비정상 종료
**해결**:
```powershell
Remove-Item -Path "*.lock" -ErrorAction SilentlyContinue
```
