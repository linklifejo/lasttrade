# 프로젝트 규칙 (AI 모델용)

---

## 🚨 **절대 규칙 (MUST FOLLOW)**

### **0. 코드 수정 전 반드시 사용자 승인 필요** ⭐⭐⭐
```
절대 원칙:
  - 모든 코드 수정은 사용자에게 먼저 물어보고 승인받아야 함
  - 파일 생성, 수정, 삭제 모두 해당
  - 설정값 변경도 사용자 승인 필요

승인 요청 방법:
  1. 수정 내용 명확히 설명
  2. 수정 이유 설명
  3. 영향 범위 설명
  4. 사용자 승인 대기

예외 (승인 없이 가능):
  - 문서 읽기 (view_file, grep_search 등)
  - 로그 확인 (read_terminal 등)
  - 정보 조회 (list_dir 등)
  - 사용자가 명시적으로 "자동으로 해라" 지시한 경우

위반 시: 즉시 중단 및 사용자에게 사과
```

**예시:**
```
❌ 나쁜 예:
  "check_n_buy.py를 수정하겠습니다."
  → 바로 수정 시작

✅ 좋은 예:
  "check_n_buy.py의 initial_buy_ratio 로직을 수정하려고 합니다.
   
   수정 내용:
     - Line 312: initial_buy_ratio 로드 로직 추가
   
   수정 이유:
     - 초기 매수 비율 설정 적용
   
   영향 범위:
     - 1차 매수 금액 계산 방식 변경
   
   수정하시겠습니까?"
  → 사용자 승인 대기
```

---

### **0-1. 인수인계 시 문서 및 소스 학습 필수** ⭐⭐⭐
```
절대 원칙:
  - 새로운 AI 모델이 프로젝트를 인수받을 때 반드시 문서와 소스를 먼저 학습
  - 학습 완료 후에만 수정 작업 가능
  - 수정이 필요한 경우 반드시 사용자 허락 득함

인수인계 절차:
  1. 필수 문서 읽기 (순서대로)
     └─ 전략별_설정_팩터_기술서.md
     └─ 불타기_물타기_전략_가이드.md
     └─ 미체결_로직_기술서.md
     └─ 트러블슈팅_가이드.md
     └─ README.md
  
  2. .gemini 디렉토리 문서 읽기
     └─ .gemini/rules.md (현재 문서)
     └─ .gemini/context.md
     └─ .gemini/project_guide.md
  
  3. 핵심 소스 파일 파악
     └─ check_n_buy.py (매수 로직)
     └─ check_n_sell.py (매도 로직)
     └─ settings_ui.py (설정 UI 및 프리셋)
     └─ bot.py (메인 루프)
  
  4. 학습 완료 보고
     └─ "문서 및 소스 학습 완료했습니다" 사용자에게 보고
  
  5. 수정 필요 시
     └─ 수정 내용, 이유, 영향 범위 설명
     └─ 사용자 허락 대기
     └─ 승인 후 작업 진행

위반 시: 즉시 중단 및 학습 재진행
```

**인수인계 체크리스트:**
```
□ 전략별_설정_팩터_기술서.md 읽음
□ 불타기_물타기_전략_가이드.md 읽음
□ 미체결_로직_기술서.md 읽음
□ 트러블슈팅_가이드.md 읽음
□ README.md 읽음
□ .gemini/rules.md 읽음
□ .gemini/context.md 읽음
□ .gemini/project_guide.md 읽음
□ check_n_buy.py 파악
□ check_n_sell.py 파악
□ settings_ui.py 파악
□ bot.py 파악
□ 사용자에게 학습 완료 보고
```

**예시:**
```
✅ 좋은 예:
  "안녕하세요. 프로젝트를 인수받았습니다.
   
   학습 완료 내역:
     ✅ 전략별_설정_팩터_기술서.md
     ✅ 불타기_물타기_전략_가이드.md
     ✅ 미체결_로직_기술서.md
     ✅ 트러블슈팅_가이드.md
     ✅ README.md
     ✅ .gemini 디렉토리 문서
     ✅ 핵심 소스 파일 (check_n_buy.py, check_n_sell.py 등)
   
   주요 파악 사항:
     - 불타기/물타기 전략 이해
     - 프리셋 자동 설정 시스템 파악
     - 미체결 주문 관리 로직 이해
     - 트러블슈팅 절차 숙지
   
   무엇을 도와드릴까요?"
  → 사용자 확인 대기
```

---

### **1. 문서 우선 읽기**
```
코드 수정 전 반드시 읽어야 할 문서:
  1. 전략별_설정_팩터_기술서.md (최우선)
  2. 불타기_물타기_전략_가이드.md
  3. 미체결_로직_기술서.md
  4. README.md

위반 시: 전략 로직 파괴 가능
```

### **2. 팩터 변경 시 상호작용 확인**
```
팩터 변경 전 확인:
  - 전략별_설정_팩터_기술서.md의 "팩터 간 상호작용" 섹션
  - 다른 팩터에 미치는 영향
  - 프리셋 값과의 일관성

예시:
  split_buy_cnt 변경 시:
    └─ initial_buy_ratio와의 조합 확인
    └─ cumulative_ratios 계산 영향 확인
    └─ 프리셋 값 일관성 확인
```

### **3. 프리셋 일관성 유지**
```
프리셋 변경 시:
  - 4가지 프리셋 모두 확인 (몰빵 물타기, 몰빵 불타기, 분산 물타기, 분산 불타기)
  - 전략별 특성 유지 (불타기: 빠른 집중, 물타기: 세밀한 분할)
  - 추천값 범위 내에서 조정

위반 시: 사용자 혼란 초래
```

### **4. 미체결 주문 관리 로직 보존**
```
절대 수정 금지:
  - stocks_being_sold 세트 관리 로직
  - 매도 중 종목 매수 금지 로직
  - accumulated_purchase_amt 동기화 로직

이유: 주문 충돌 및 중복 매수 방지
```

### **5. 물타기 손절 보호 로직 보존**
```
절대 수정 금지:
  - check_n_sell.py의 물타기 매집 중 손절 스킵 로직
  - pchs_amt < alloc_per_stock * 0.95 조건

이유: 물타기 전략의 핵심 로직
```

---

## ⚠️ **주의 규칙 (SHOULD FOLLOW)**

### **1. 설정값 변경 시 DB 우선**
```
설정 우선순위:
  DB (trading.db) > 기본값

변경 방법:
  - settings_ui.py를 통한 UI 변경 (권장)
  - database_helpers.py의 save_all_settings() 사용

직접 코드 수정 금지:
  - get_setting()의 기본값만 변경 가능
  - 실제 동작 값은 DB에서 로드
```

### **2. 로그 메시지 명확성**
```
로그 작성 시:
  - 어떤 팩터가 적용되었는지 명시
  - 계산 과정 표시 (금액, 비율 등)
  - 조건 충족/미충족 이유 명시

예시:
  logger.info(f"[초기 매수] {stk_cd}: 초기 매수 비율 {initial_buy_ratio*100:.1f}% 적용")
  logger.info(f"[{msg_reason}] {stk_cd}: 매수 진행 (목표: {one_shot_amt:,.0f}원, 전체 할당: {alloc_per_stock:,.0f}원)")
```

### **3. 에러 처리 강화**
```
try-except 사용 시:
  - 구체적인 예외 타입 지정
  - 에러 메시지 명확히 로깅
  - 기본값 또는 안전한 동작 보장

예시:
  try:
      initial_buy_ratio = float(get_setting('initial_buy_ratio', 10.0)) / 100.0
  except Exception as e:
      logger.error(f"initial_buy_ratio 로드 실패: {e}")
      initial_buy_ratio = 0.1  # 기본값 10%
```

### **4. 코드 주석 작성**
```
주석 필수 항목:
  - 새로운 팩터 추가 시
  - 복잡한 계산 로직
  - 전략별 분기 처리
  - 안전장치 로직

예시:
  # [신규] 초기 매수 비율 설정 로드 (기본 10%)
  initial_buy_ratio = float(get_setting('initial_buy_ratio', 10.0)) / 100.0
```

---

## 💡 **권장 규칙 (RECOMMENDED)**

### **1. 테스트 주도 개발**
```
코드 변경 후:
  1. 단위 테스트 작성 (가능한 경우)
  2. 로그 확인
  3. 실제 동작 검증
  4. 엣지 케이스 확인
```

### **2. 문서 업데이트**
```
코드 변경 시 문서 업데이트:
  - 전략별_설정_팩터_기술서.md (팩터 추가/변경 시)
  - 불타기_물타기_전략_가이드.md (전략 로직 변경 시)
  - 미체결_로직_기술서.md (주문 로직 변경 시)
  - README.md (사용법 변경 시)
```

### **3. 변경 이력 기록**
```
.gemini/context.md에 기록:
  - 변경 날짜
  - 변경 내용
  - 변경 이유
  - 영향 범위
```

### **4. 코드 리뷰 체크리스트**
```
변경 전 확인:
  □ 관련 문서 읽음
  □ 팩터 상호작용 확인
  □ 프리셋 일관성 확인
  □ 미체결 로직 영향 확인
  □ 로그 메시지 추가
  □ 에러 처리 추가
  □ 주석 작성
  □ 테스트 계획 수립
```

---

## 🔒 **보안 규칙**

### **1. API 키 보호**
```
절대 금지:
  - config.py를 Git에 커밋
  - 로그에 API 키 출력
  - 하드코딩된 API 키

권장:
  - .gitignore에 config.py 추가
  - 환경 변수 사용 (선택)
  - DB에 암호화 저장 (선택)
```

### **2. 민감 정보 로깅 금지**
```
로그에 출력 금지:
  - API 키
  - 계좌 번호 (마스킹 권장)
  - 비밀번호
  - 토큰

예시:
  logger.info(f"계좌: {account_no[:4]}****{account_no[-4:]}")
```

---

## 📊 **성능 규칙**

### **1. API 호출 최소화**
```
원칙:
  - 한 번 조회한 데이터는 재사용
  - 루프 내 API 호출 금지
  - 배치 처리 우선

예시:
  # 나쁜 예
  for stock in stocks:
      balance = get_balance(token)  # 매번 호출
  
  # 좋은 예
  balance = get_balance(token)  # 한 번만 호출
  for stock in stocks:
      # balance 재사용
```

### **2. DB 쿼리 최적화**
```
원칙:
  - 필요한 필드만 조회
  - 인덱스 활용
  - 트랜잭션 사용 (대량 작업 시)

예시:
  # 나쁜 예
  for setting in settings:
      save_setting(key, value)  # 매번 커밋
  
  # 좋은 예
  save_all_settings(settings)  # 한 번에 커밋
```

### **3. 메모리 관리**
```
원칙:
  - 불필요한 전역 변수 최소화
  - 큰 데이터는 즉시 해제
  - 순환 참조 방지

예시:
  # 매도 완료 후 데이터 정리
  if stk_cd in accumulated_purchase_amt:
      del accumulated_purchase_amt[stk_cd]
```

---

## 🐛 **디버깅 규칙**

### **1. 로그 레벨 활용**
```
로그 레벨 가이드:
  - DEBUG: 상세한 디버깅 정보
  - INFO: 일반 정보 (매수/매도, 설정 로드 등)
  - WARNING: 경고 (예수금 부족, 조건 미달 등)
  - ERROR: 에러 (API 실패, DB 오류 등)
  - CRITICAL: 치명적 에러 (시스템 중단 등)
```

### **2. 에러 추적**
```
에러 발생 시:
  1. 에러 메시지 명확히 로깅
  2. 스택 트레이스 포함
  3. 관련 변수 값 로깅
  4. 복구 시도 또는 안전한 종료

예시:
  try:
      result = some_function()
  except Exception as e:
      logger.error(f"함수 실행 실패: {e}", exc_info=True)
      logger.error(f"관련 변수: stk_cd={stk_cd}, amt={amt}")
```

### **3. 상태 추적**
```
중요 상태 변경 시 로깅:
  - stocks_being_sold 추가/제거
  - accumulated_purchase_amt 업데이트
  - 설정값 변경
  - 전략 전환

예시:
  logger.info(f"[stocks_being_sold] 추가: {stk_cd}")
  logger.info(f"[데이터 업데이트] {stk_cd}: 누적 매수금 {amt:,.0f}원")
```

---

## 📝 **코딩 스타일 규칙**

### **1. 네이밍 컨벤션**
```
변수명:
  - snake_case 사용
  - 의미 있는 이름 사용
  - 약어 최소화

함수명:
  - snake_case 사용
  - 동사로 시작 (get_, set_, check_, update_ 등)

상수:
  - UPPER_CASE 사용
  - 의미 명확히

예시:
  initial_buy_ratio  # 좋음
  ibr  # 나쁨
  
  get_setting()  # 좋음
  setting()  # 나쁨
  
  MIN_PURCHASE_AMOUNT  # 좋음
  min_amt  # 나쁨
```

### **2. 함수 길이**
```
원칙:
  - 한 함수는 한 가지 일만
  - 최대 50줄 이내 권장
  - 복잡한 로직은 분리

예시:
  # 나쁜 예
  def process_buy():
      # 100줄의 복잡한 로직
  
  # 좋은 예
  def process_buy():
      validate_conditions()
      calculate_amount()
      execute_order()
```

### **3. 주석 스타일**
```
주석 작성:
  - 한글 사용 (한국어 프로젝트)
  - 간결하고 명확하게
  - 왜(Why)를 설명 (무엇(What)은 코드로)

예시:
  # [신규] 초기 매수 비율 설정 로드 (기본 10%)
  # 불타기 전략: 10% 테스트 → 90% 집중
  initial_buy_ratio = float(get_setting('initial_buy_ratio', 10.0)) / 100.0
```

---

## 🎯 **우선순위 규칙**

### **매도 로직 우선순위 (절대 변경 금지)**
```
1순위: 상한가 (upper_limit_rate)
2순위: 타임컷 (time_cut_minutes + time_cut_profit)
3순위: 트레일링 스탑 (TS) ⭐ 핵심
4순위: 목표 익절 (take_profit_rate)
5순위: 손절 (stop_loss_rate)
```

### **매수 로직 우선순위 (절대 변경 금지)**
```
1순위: 종목 수 제한 (target_stock_count)
2순위: 매도 중 종목 (stocks_being_sold)
3순위: 미체결 확인 (outstanding_orders)
4순위: 전략 조건 (single_stock_strategy + single_stock_rate)
5순위: 예수금 확인 (balance)
```

---

## ⚡ **긴급 상황 대응**

### **1. 봇 멈춤 시**
```
체크 순서:
  1. 로그 확인 (trading_bot.log, error.log)
  2. DB 상태 확인 (trading.db)
  3. API 연결 확인
  4. 설정값 검증
  5. 재시작
```

### **2. 주문 실패 시**
```
체크 순서:
  1. stocks_being_sold 확인
  2. 미체결 주문 확인
  3. 예수금 확인
  4. API 상태 확인
  5. 로그 확인
```

### **3. 설정 반영 안 될 시**
```
체크 순서:
  1. DB 저장 확인
  2. cached_setting() 사용 확인
  3. 봇 재시작
  4. 로그 확인
```

---

**마지막 업데이트:** 2025-12-26

**준수 필수:** 이 규칙들은 시스템 안정성과 전략 로직 보존을 위해 반드시 지켜야 합니다.
