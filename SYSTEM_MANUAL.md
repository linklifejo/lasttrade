# 📘 LASTTRADE 시스템 매뉴얼 (System Architecture Manual)

> **Core Philosophy**: "Server is Server." 
> 핵심 로직은 UI와 독립적으로 작동하며, 원칙(Principles)을 최우선으로 수행한다.

---

## 🏗️ 1. 시스템 아키텍처 (System Architecture)

전체 시스템은 **3개의 독립된 프로세스**로 구동되며, 각 프로세스는 명확한 역할 분담을 가집니다.

### A. Trading Core (Bot) - `bot.py`
*   **역할**: 주식 매매를 담당하는 **진짜 '서버'**.
*   **기능**: 장 시간 관리, 매수/매도 로직 수행, 자금 관리, API 통신.
*   **특징**: UI가 꺼져 있어도 백그라운드에서 묵묵히 원칙대로 매매를 수행함.

### B. Web Dashboard (Viewer) - `web_server.py`
*   **역할**: 현재 상태를 시각화하는 **'모니터'**.
*   **기능**: 실시간 잔고/보유종목 표시, 매매 로그 출력, 설정값 변경 UI.
*   **특징**: 트레이딩 코어에 직접 개입하지 않고, DB와 파일을 통해 데이터를 읽어서 보여줌.

### C. Watchdog (Guardian) - `watchdog.py`
*   **역할**: 사령관.
*   **기능**: `bot.py`와 `web_server.py`의 생존 여부를 2초마다 체크.
*   **특징**: 프로세스가 비정상 종료되거나 멈꾸면 즉시 재시작하여 골든타임을 사수함.

---

## 📂 2. 소스 코드 분류 (Source Code Map)

### 🧠 핵심 매매 엔진 (Logic & Brain)
가장 중요한 로직들이 모여 있는 영역입니다.
*   **`bot.py`**: 시스템의 메인 루프. 전체 흐름 제어, 모드 전환(Real/Mock), 스케줄링.
*   **`check_n_buy.py`**: **매수 판단**. 물타기 단계 계산(1:1:2:4), 불타기, 진입 금지 필터링.
*   **`check_n_sell.py`**: **매도 판단**. 조기 손절(4차), 익절, MAX 단계 손절, 장 마감 청산.
*   **`optimize_settings.py`**: **자금 최적화**. 예수금 부족 시 목표 종목 수를 자동으로 줄여서 분할 매수 원칙을 사수함.
*   **`kiwoom_adapter.py`**: **통신**. 키움 실전/모의투자 및 자체 Mock 서버와의 통신을 표준화하여 연결.

### 🖥️ 웹 대시보드 (UI & Client)
사용자가 보는 화면과 관련된 영역입니다.
*   **`web_server.py`**: Flask 웹 서버 구동.
*   **`rt_search.py`**: 실시간 시세 조회 및 Dashboard용 데이터 가공.
*   **`templates/index.html`**: 메인 대시보드 화면 HTML.
*   **`templates/settings.html`**: 설정 변경 화면 HTML.
*   **`static/script_final.js`**: 깜빡임 방지, 데이터 갱신 Ajax 처리.

### 💾 데이터 및 설정 (Storage & Config)
*   **`trading.db`**: 모든 거래 내역, 체결 기록, 자산 변동 내역이 저장되는 SQLite DB.
*   **`database.py`**: DB 연결 및 쿼리 관리.
*   **`LASTTRADE_PRINCIPLES.md`**: **[헌법]** 매매 원칙, 자금 관리 철학을 정의한 문서.
*   **`logger.py`**: 시스템 로그 관리 (인코딩 처리 포함).

### 🚀 운영 및 관리 (Operations)
*   **`start.py`**: **시스템 시작점**. 좀비 프로세스를 정리하고 서버와 워치독을 실행.
*   **`stop.py`**: 시스템 안전 종료.

---

## ⚙️ 3. 핵심 프로세스 흐름 (Workflow)

1.  **시작 (`start.py`)**: 
    *   기존 프로세스 정리 -> 워치독 실행 -> 봇 실행 -> 웹 서버 실행.
2.  **초기화 (`bot.py` Startup)**:
    *   `optimize_settings.py` 호출 -> 자금 대비 종목 수 최적화 수행.
3.  **장중 루프**:
    *   `check_market_timing`: 장 시작/마감/휴장 체크.
    *   `check_n_buy` / `check_n_sell`: 매수/매도 로직 반복 수행.
    *   `watchdog`: 봇이 살아있는지 계속 감시.
4.  **장 마감**:
    *   보유 종목 일괄 청산 (설정에 따라).
    *   `learn_daily.py`: 하루 매매 복기 및 AI 학습 (15:40).
    *   자동 종료.
