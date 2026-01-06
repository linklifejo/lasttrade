# 텔레그램/웹 대시보드 Stop 명령 테스트 가이드

## 🎯 테스트 목적
텔레그램과 웹 대시보드에서 `stop` 명령이 정상적으로 작동하여 프로그램을 종료하는지 확인

## ✅ 사전 준비
1. 시스템이 정상적으로 실행 중인지 확인
   - 웹 대시보드: http://localhost:8080
   - 봇 프로세스: `bot.py` 실행 중
   - 웹 서버: `web_server.py` 실행 중

## 📱 테스트 1: 텔레그램 Stop 명령

### 실행 방법
1. 텔레그램 앱 열기
2. 봇과 연결된 채팅방으로 이동
3. 다음 명령어 전송:
   ```
   stop
   ```

### 예상 결과
1. **텔레그램 응답**:
   - "✅ 실시간 검색과 자동 매도 체크가 중지되었습니다" 메시지 수신

2. **봇 로그** (콘솔 확인):
   ```
   텔레그램 메시지 수신: stop
   🛑 텔레그램 stop 명령 수신 - 프로그램을 종료합니다.
   사용자 요청으로 프로그램을 종료합니다.
   ```

3. **프로세스 종료**:
   - `bot.py` 프로세스 종료 (exit code 0)
   - 웹 서버는 계속 실행 중 (정상)

4. **Watchdog 동작**:
   - 정상 종료(exit code 0)이므로 재시작하지 않음

### 확인 방법
```powershell
# 프로세스 확인
Get-Process python | Where-Object { $_.CommandLine -match "bot.py" }

# 결과: 아무것도 나오지 않아야 함 (bot.py 종료됨)
```

## 🌐 테스트 2: 웹 대시보드 Stop 버튼

### 실행 방법
1. 브라우저에서 http://localhost:8080 접속
2. 대시보드 상단의 **"Stop"** 버튼 클릭

### 예상 결과
1. **웹 UI 변화**:
   - "Stop" 버튼 → "Start" 버튼으로 변경
   - 봇 상태: "실행 중" → "중지됨"

2. **봇 로그** (콘솔 확인):
   ```
   🚀 [Web Dashboard] 명령 수신됨 (DB): stop
   ⚙️ 명령 실행 중: stop...
   ✅ 명령 실행 완료: stop
   🛑 웹 대시보드 stop 명령 수신 - 프로그램을 종료합니다.
   ```

3. **프로세스 종료**:
   - `bot.py` 프로세스 종료 (exit code 0)
   - 웹 서버는 계속 실행 중

### 확인 방법
```powershell
# 프로세스 확인
tasklist /FI "IMAGENAME eq python.exe" | findstr bot.py

# 결과: 아무것도 나오지 않아야 함
```

## 🔍 추가 확인 사항

### 1. 로그 파일 확인
```powershell
# 최근 로그 확인
Get-Content -Path "logs\bot.log" -Tail 50
```

**확인할 내용**:
- "🛑 텔레그램 stop 명령 수신" 또는 "🛑 웹 대시보드 stop 명령 수신"
- "사용자 요청으로 프로그램을 종료합니다"
- 에러 없이 정상 종료

### 2. Exit Code 확인
```powershell
# 마지막 명령의 종료 코드 확인
$LASTEXITCODE

# 예상 결과: 0 (정상 종료)
```

### 3. 데이터베이스 확인
```powershell
# 웹 명령 처리 상태 확인
python -c "import sqlite3; conn = sqlite3.connect('trading.db'); cursor = conn.execute('SELECT * FROM web_commands ORDER BY id DESC LIMIT 5'); print([dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()])"
```

**확인할 내용**:
- `command`: "stop"
- `status`: "completed"
- `created_at`: 최근 시간

## ⚠️ 문제 해결

### 문제 1: stop 명령 후에도 프로세스가 계속 실행됨
**원인**: 코드 수정이 적용되지 않음
**해결**:
```powershell
# 강제 종료 후 재시작
python kill_zombies.py
python start.py
```

### 문제 2: 텔레그램 메시지가 수신되지 않음
**원인**: 텔레그램 토큰 또는 채팅 ID 설정 오류
**확인**:
```powershell
# config.py 확인
python -c "from config import telegram_token, telegram_chat_id; print(f'Token: {telegram_token[:10]}..., Chat ID: {telegram_chat_id}')"
```

### 문제 3: 웹 대시보드 버튼이 작동하지 않음
**원인**: 웹 서버와 봇 간 DB 통신 문제
**확인**:
```powershell
# DB 연결 테스트
python -c "from database_helpers import get_pending_web_command; print(get_pending_web_command())"
```

## 📊 테스트 체크리스트

- [ ] 시스템 정상 시작 확인
- [ ] 웹 대시보드 접속 확인 (http://localhost:8080)
- [ ] 텔레그램 stop 명령 테스트
  - [ ] 텔레그램 응답 메시지 확인
  - [ ] 봇 로그에 종료 메시지 확인
  - [ ] bot.py 프로세스 종료 확인
  - [ ] exit code 0 확인
- [ ] 웹 대시보드 Stop 버튼 테스트
  - [ ] UI 상태 변경 확인
  - [ ] 봇 로그에 종료 메시지 확인
  - [ ] bot.py 프로세스 종료 확인
  - [ ] exit code 0 확인
- [ ] Watchdog 재시작 안 함 확인
- [ ] 로그 파일 정상 종료 확인

## 🎉 성공 기준

✅ **모든 테스트 통과 조건**:
1. 텔레그램 `stop` 명령 → bot.py 정상 종료 (exit code 0)
2. 웹 대시보드 Stop 버튼 → bot.py 정상 종료 (exit code 0)
3. 종료 후 Watchdog가 재시작하지 않음
4. 로그에 에러 없이 정상 종료 메시지 기록
5. 웹 서버는 계속 실행 중 (독립적 운영)

## 💡 참고 사항

- **정상 종료 vs 비정상 종료**:
  - 정상 종료 (exit code 0): Watchdog 재시작 안 함
  - 비정상 종료 (exit code 1): Watchdog가 5초 후 재시작

- **웹 서버 독립성**:
  - 봇이 종료되어도 웹 서버는 계속 실행
  - 대시보드에서 언제든지 "Start" 버튼으로 봇 재시작 가능

- **재시작 방법**:
  ```powershell
  # 전체 시스템 재시작
  python start.py
  
  # 또는 웹 대시보드에서 "Start" 버튼 클릭
  ```
