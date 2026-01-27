
# 📅 개발 및 업데이트 로그 (2026-01-27)

## 🚀 1. AI Recommendation Engine Upgrade (Deep Learning)
- **Model Architecture**: 기존 규칙 기반(RSI) 로직을 폐기하고, **Transformer (Self-Attention)** 기반의 시계열 예측 모델 도입.
- **Objective**: 향후 **60분 이내 +7% 이상 급등**하거나 **상한가**에 도달할 패턴을 사전 포착.
- **Data Source**: `deep_learning.db` 내 3개월치 분봉 데이터 (`ohlcv_1m` 등).
- **Training Strategy**:
  - Positive Sample (급등 패턴)은 전수 학습.
  - Negative Sample (횡보/하락)은 95% 이상 다운샘플링하여 데이터 불균형 해소.
  - **Memory Safety**: 대용량 처리를 위해 종목별/배치별 순차 로딩 방식 적용.

## ⚙️ 2. System Pipeline Optimization
- **Dual Radar System**:
  - **Channel A**: 기존 키움 조건검색식 (안정적 포착)
  - **Channel B**: 신규 AI 모델 (공포 구간 매수 및 급등 선취매)
- **Queue Processing**: 스레드 간 통신 오류 방지를 위해 `config.ai_recommendation_queue` 도입. (추천 -> 큐 적재 -> 봇이 여유 될 때 즉시 매수)
- **Source Tagging**: 매매 로그 및 UI에 `[모델추천]`, `[검색식추천]`을 명확히 구분하여 성과 추적 가능.

## 🛡️ 3. Trading Logic & Risk Management
- **Restriction Removal**: AI 성능 테스트를 위해 '15시 이후 매수 금지', '보유 종목 수 제한' 코드 해제. (Mock 모드 24시간 매수 가능)
- **Bad Inventory Clearance**: 손실 누적된 `RISE AI반도체TOP10` ETF 전량 강제 매도 처리.
- **Water Strategy Integration**: AI 추천 종목도 기존의 4단계 물타기(1:1:2:4:8) 로직을 그대로 따르며, 물타기 시에도 출처(Source) 태그 유지.

## 🎯 4. Target Filtering
- **Top 500 Filter**: AI 모델이 잡주에 속지 않도록, **'실시간 거래대금 상위 500위'** 종목군 내에서만 분석하도록 로직 제약 설정.

---
**Next Action**: 
- 메인 장(09:00) 시작 전 학습 완료된 `DL_stock_model.pth` 파일 자동 로드 확인.
- `kiwoom_adapter.py` 내 `get_top_500()` 함수 실구현 확인.

## 🤖 5. Final AI Model Artifacts
- **Model File Name**: `DL_stock_model.pth`
- **Location**: `c:\lasttrade\DL_stock_model.pth` (Project Root)
- **Architecture**: HunterTransformer (Input: OHLCV 5-dim, Output: 1-dim Sigmoid Probability)
- **Checkpoint Files**: `c:\lasttrade\DL_model_epoch_{N}.pth` (Generated during training for crash recovery)
- **Usage**: Automatically loaded by `ai_recommender.py` upon startup.
