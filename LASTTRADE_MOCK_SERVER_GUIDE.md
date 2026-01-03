# 🎮 키움 가상서버 (Mock Server) 사용 가이드

## 📚 목차

1. [개요](#개요)
2. [설치 및 설정](#설치-및-설정)
3. [사용 방법](#사용-방법)
4. [테스트 시나리오](#테스트-시나리오)
5. [기존 코드 통합](#기존-코드-통합)
6. [API 레퍼런스](#api-레퍼런스)

---

## 개요

### 왜 가상서버가 필요한가?

실제 키움 API는 **장 시간에만 작동**하기 때문에:
- ❌ 주말이나 밤에 테스트 불가능
- ❌ 장 종료 후 버그 수정 및 검증 불가능
- ❌ 특정 시장 상황(급등/급락) 재현 어려움

**가상서버(Mock Server)를 사용하면:**
- ✅ **24시간 언제든지 테스트 가능**
- ✅ **다양한 시장 상황을 시뮬레이션**
- ✅ **실제 돈을 쓰지 않고 안전하게 테스트**
- ✅ **특정 시나리오를 반복적으로 재현**

---

## 설치 및 설정

### 1. 디렉토리 구조

```
chapter_4/
├── kiwoom/                      # 키움 API 패키지
│   ├── __init__.py
│   ├── base_api.py             # 공통 인터페이스
│   ├── real_api.py             # 실제 키움 API
│   ├── mock_api.py             # 가상 서버 API
│   ├── factory.py              # API 생성 팩토리
│   └── mock_data/              # 가상 데이터 저장소
│       ├── account.json        # 계좌 정보
│       ├── stocks.json         # 종목 리스트
│       ├── prices.json         # 가격 데이터
│       └── orders.json         # 주문 내역
├── kiwoom_adapter.py           # 기존 코드 호환 어댑터
├── test_mock_server.py         # 테스트 스크립트
└── settings.json               # 설정 파일
```

### 2. 설정 파일 (settings.json)

```json
{
  "use_mock_server": false,    // true로 변경하면 가상서버 사용
  ...기존 설정...
}
```

**설정 변경 방법:**

```json
// 실제 서버 사용
{
  "use_mock_server": false
}

// 가상 서버 사용
{
  "use_mock_server": true
}
```

---

## 사용 방법

### 방법 1: 자동 테스트 실행

가상서버의 모든 기능을 자동으로 테스트합니다:

```bash
# 먼저 가상서버 모드로 변경
# settings.json에서 "use_mock_server": true로 설정

# 테스트 실행
python test_mock_server.py
```

**테스트 항목:**
1. ✅ API 상태 확인
2. ✅ 토큰 발급
3. ✅ 잔고 조회
4. ✅ 현재가 조회
5. ✅ 매수 주문
6. ✅ 보유 종목 조회
7. ✅ 시나리오 시뮬레이션 (급등/급락)
8. ✅ 매도 주문
9. ✅ 최종 상태 확인

### 방법 2: 대화형 모드

직접 명령을 입력하며 테스트할 수 있습니다:

```bash
python test_mock_server.py interactive
```

**사용 가능한 명령:**
- `1`: 잔고 조회
- `2`: 보유 종목 조회
- `3`: 현재가 조회
- `4`: 매수
- `5`: 매도
- `6`: Mock 시나리오 (급등/급락 등)
- `7`: Mock 계좌 초기화
- `0`: 종료

### 방법 3: Python 코드에서 직접 사용

```python
from kiwoom_adapter import *

# 토큰 발급
token = fn_au10001()

# 잔고 조회
cash, total, deposit = fn_kt00001(token=token)
print(f"주문가능금액: {cash:,}원")

# 매수
code, msg = fn_kt10000("005930", "10", "70000", token=token)
print(f"매수 결과: {code} - {msg}")

# 보유 종목 조회
stocks = fn_kt00004(print_df=True, token=token)

# 매도
code, msg = fn_kt10001("005930", "10", token=token)
print(f"매도 결과: {code} - {msg}")
```

---

## 테스트 시나리오

### 1. 급등 시나리오 (Surge)

주가가 갑자기 **+5% 상승**하는 상황을 시뮬레이션합니다.

```python
from kiwoom_adapter import mock_simulate_scenario

# 삼성전자 급등 시뮬레이션
mock_simulate_scenario("005930", "surge")
```

**사용 예시:**
- 익절 로직 테스트
- 불타기 전략 검증
- Trailing Stop 동작 확인

### 2. 급락 시나리오 (Crash)

주가가 갑자기 **-5% 하락**하는 상황을 시뮬레이션합니다.

```python
# 삼성전자 급락 시뮬레이션
mock_simulate_scenario("005930", "crash")
```

**사용 예시:**
- 손절 로직 테스트
- 물타기 전략 검증
- 타임컷 동작 확인

### 3. 변동성 시나리오 (Volatile)

주가가 **-3% ~ +3% 범위에서 랜덤하게 변동**합니다.

```python
# 변동성 장세 시뮬레이션
mock_simulate_scenario("005930", "volatile")
```

**사용 예시:**
- 빈번한 매매 상황 테스트
- 물/불타기 트리거 검증

### 4. 안정 시나리오 (Stable)

주가가 **-0.5% ~ +0.5% 범위에서 소폭 변동**합니다.

```python
# 안정적인 장세 시뮬레이션
mock_simulate_scenario("005930", "stable")
```

**사용 예시:**
- 타임컷 로직 테스트
- 장기 보유 전략 검증

### 5. 커스텀 가격 설정

원하는 가격으로 직접 설정할 수 있습니다.

```python
from kiwoom_adapter import mock_set_price

# 삼성전자를 80,000원으로 설정
mock_set_price("005930", 80000)
```

### 6. 계좌 초기화

테스트를 처음부터 다시 시작할 때 사용합니다.

```python
from kiwoom_adapter import mock_reset_account

# 1000만원으로 계좌 초기화
mock_reset_account(10000000)
```

---

## 기존 코드 통합

### 자동 통합 (권장)

`kiwoom_adapter.py`를 사용하면 **기존 코드 수정 없이** 바로 사용 가능합니다!

**Before (기존 코드):**
```python
from login import fn_au10001 as get_token
from check_bal import fn_kt00001 as get_balance
from acc_val import fn_kt00004 as get_my_stocks
from buy_stock import fn_kt10000
from sell_stock import fn_kt10001

token = get_token()
cash, total, deposit = get_balance(token=token)
stocks = get_my_stocks(token=token)
```

**After (가상서버 지원):**
```python
# 단순히 import만 변경!
from kiwoom_adapter import fn_au10001 as get_token
from kiwoom_adapter import fn_kt00001 as get_balance
from kiwoom_adapter import fn_kt00004 as get_my_stocks
from kiwoom_adapter import fn_kt10000
from kiwoom_adapter import fn_kt10001

# 코드는 그대로 사용
token = get_token()
cash, total, deposit = get_balance(token=token)
stocks = get_my_stocks(token=token)
```

settings.json에서 `use_mock_server`만 토글하면 실제/가상 서버를 전환할 수 있습니다!

### 수동 통합

직접 API 인스턴스를 생성하여 사용할 수도 있습니다:

```python
from kiwoom.factory import create_kiwoom_api

# 가상서버 생성
api = create_kiwoom_api(use_mock=True)

# 또는 설정 파일 기반
api = create_kiwoom_api()  # settings.json의 use_mock_server 사용

# 사용
token = api.get_token()
cash, total, deposit = api.get_balance(token)
stocks = api.get_my_stocks(token)
api.buy_stock("005930", "10", "70000", token)
api.sell_stock("005930", "10", token)
```

---

## API 레퍼런스

### 공통 API (Real + Mock)

#### 1. 토큰 발급
```python
fn_au10001() -> str
```
접근 토큰을 발급받습니다.

#### 2. 잔고 조회
```python
fn_kt00001(token=None) -> Tuple[int, int, int]
```
- **반환:** (주문가능금액, 총평가금액, 예수금)

#### 3. 계좌 평가 현황
```python
get_account_data(token=None) -> Tuple[List[Dict], Dict]
```
- **반환:** (종목 리스트, 계좌 요약 데이터)

#### 4. 보유 종목 조회
```python
fn_kt00004(print_df=False, token=None) -> List[Dict]
```
- **print_df:** True면 데이터프레임으로 출력
- **반환:** 보유 종목 리스트

#### 5. 총 평가금액
```python
get_total_eval_amt(token=None) -> int
```
- **반환:** 보유 주식의 총 평가금액

#### 6. 매수 주문
```python
fn_kt10000(stk_cd, ord_qty, ord_uv, token=None) -> Tuple[str, str]
```
- **stk_cd:** 종목코드
- **ord_qty:** 주문수량
- **ord_uv:** 주문단가
- **반환:** (결과코드, 결과메시지)

#### 7. 매도 주문
```python
fn_kt10001(stk_cd, ord_qty, token=None) -> Tuple[str, str]
```
- **stk_cd:** 종목코드
- **ord_qty:** 주문수량
- **반환:** (결과코드, 결과메시지)

#### 8. 현재가 조회
```python
get_current_price(stk_cd, token=None) -> int
```
- **반환:** 현재가

### Mock 전용 API

#### 1. 계좌 초기화
```python
mock_reset_account(initial_cash=10000000)
```
계좌를 초기 상태로 리셋합니다.

#### 2. 종목 추가
```python
mock_add_stock(code, name, base_price)
```
새로운 종목을 추가합니다.

**예시:**
```python
mock_add_stock("999999", "테스트주식", 50000)
```

#### 3. 가격 설정
```python
mock_set_price(code, price)
```
특정 종목의 가격을 강제로 설정합니다.

**예시:**
```python
mock_set_price("005930", 80000)
```

#### 4. 시나리오 시뮬레이션
```python
mock_simulate_scenario(code, scenario)
```
- **scenario:** 'surge', 'crash', 'volatile', 'stable'

**예시:**
```python
# 급등 시뮬레이션
mock_simulate_scenario("005930", "surge")

# 급락 시뮬레이션
mock_simulate_scenario("005930", "crash")
```

---

## 고급 사용법

### 복합 시나리오 테스트

```python
from kiwoom_adapter import *
import time

# 1. 계좌 초기화
mock_reset_account(10000000)

# 2. 매수
token = fn_au10001()
fn_kt10000("005930", "100", "70000", token=token)

# 3. 급락 시뮬레이션
mock_simulate_scenario("005930", "crash")
time.sleep(1)

# 4. 손절 확인
stocks = fn_kt00004(token=token)
for stock in stocks:
    profit_rate = float(stock.get('pl_rt', 0))
    if profit_rate < -3:  # -3% 손절
        fn_kt10001(stock['stk_cd'], stock['rmnd_qty'], token=token)
        print(f"손절: {stock['stk_nm']}")

# 5. 최종 결과
cash, total, _ = fn_kt00001(token=token)
print(f"최종 자산: {total:,}원")
```

### 봇 통합 예시

```python
# bot.py 또는 main.py에서

# Before
# from login import fn_au10001 as get_token

# After
from kiwoom_adapter import fn_au10001 as get_token
from kiwoom_adapter import fn_kt00001 as get_balance
from kiwoom_adapter import fn_kt00004 as get_my_stocks
from kiwoom_adapter import fn_kt10000 as buy_stock
from kiwoom_adapter import fn_kt10001 as sell_stock

# 기존 코드는 그대로 사용!
# settings.json에서 use_mock_server만 변경하면 됨
```

---

## 문제 해결

### Q1: "Mock 모드가 아닙니다" 오류

**해결:** `settings.json`에서 `"use_mock_server": true`로 설정했는지 확인

### Q2: 가격이 변하지 않음

**해결:** `mock_simulate_scenario()` 또는 `mock_set_price()`를 사용하여 가격 변동 시뮬레이션

### Q3: 계좌가 초기화되지 않음

**해결:** Mock 모드인지 확인 후 `mock_reset_account()`를 사용

### Q4: 실제 봇 실행 시 Mock 데이터가 사용됨

**해결:** `settings.json`에서 `"use_mock_server": false`로 변경

---

## 주의사항

⚠️ **중요:**
1. **실제 거래 전에는 반드시 `use_mock_server: false`로 변경**
2. Mock 데이터는 `kiwoom/mock_data/` 디렉토리에 저장됨
3. Mock 모드에서는 실제 주문이 발생하지 않음
4. 가격 변동은 수동으로 시뮬레이션해야 함 (자동 변동 X)

---

## 라이선스

이 가상서버는 테스트 및 개발 목적으로만 사용됩니다.
실제 거래는 반드시 키움증권 공식 API를 사용하세요.

---

## 문의

문제가 발생하거나 추가 기능이 필요하시면 알려주세요! 🚀
