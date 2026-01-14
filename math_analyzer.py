import time
import sqlite3
import json
import pandas as pd
import re
from database import DB_FILE
from logger import logger

def analyze_signals():
    """기존 분석 로직을 수행하고 결과를 출력합니다."""
    report = get_analysis_report()
    print(report)
    return report

def get_analysis_report():
    """LASTTRADE 원칙 기반 성과 요약을 반환합니다."""
    conn = sqlite3.connect(DB_FILE)
    
    # 1. 시그널 데이터 (RSI 등)
    signal_query = '''
    SELECT 
        s.id, s.timestamp, s.code, s.factors_json, 
        r.interval_1m_change, r.interval_5m_change, r.max_drawdown, r.max_profit
    FROM signal_snapshots s
    JOIN response_metrics r ON s.id = r.signal_id
    '''
    
    # 2. 실제 매매 데이터 (WATER 단계 분석용)
    trade_query = 'SELECT * FROM trades WHERE type = "SELL" OR type = "sell"'
    
    try:
        df_sig = pd.read_sql_query(signal_query, conn)
        df_trades = pd.read_sql_query(trade_query, conn)
    except Exception as e:
        return f"❌ 데이터 로드 실패: {e}"
    finally:
        conn.close()
    
    report = []
    report.append(f"📊 [LASTTRADE 수학적 엔진 원칙 분석 리포트]")
    
    # --- [섹션 1. WATER 전략 단계별 성과] ---
    report.append(f"\n🌊 [1. WATER 전략 (물타기) 효율 분석]")
    if not df_trades.empty:
        # reason에서 Step 정보 추출 (예: "WATER_STEP_2" -> 2)
        def extract_step(reason):
            if not reason: return 1
            match = re.search(r'STEP_(\d+)', str(reason))
            return int(match.group(1)) if match else 1
        
        # 실제로는 매도 시점의 reason에는 매수 단계가 없을 수도 있으므로 
        # 매수 기록을 찾아 해당 종목의 최대 단계를 계산하는 것이 정확함
        # 여기서는 단순화를 위해 memo/reason에 기록된 값을 우선 사용
        df_trades['step'] = df_trades['reason'].apply(extract_step)
        
        step_stats = df_trades.groupby('step')['profit_rate'].agg(['count', 'mean']).rename(columns={'mean': 'avg_profit'})
        step_stats['win_rate'] = df_trades.groupby('step')['profit_rate'].apply(lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0)
        
        for step, row in step_stats.iterrows():
            report.append(f" • {int(step)}단계 탈출: {int(row['count']):3d}건 | 승률 {row['win_rate']*100:4.1f}% | 평균수익 {row['avg_profit']:5.2f}%")
        
        if len(step_stats) > 0:
            best_step = step_stats['win_rate'].idxmax()
            report.append(f" 💡 최적 탈출 구간: {best_step}단계 (물타기 원칙의 승리)")
    else:
        report.append("  (매도 데이터가 부족하여 분석 불가)")

    # --- [섹션 2. 시그널 필터링 성과 (Secondary)] ---
    report.append(f"\n📡 [2. 시그널 필터링 성과 (RSI 등)]")
    if not df_sig.empty:
        # JSON 형태의 팩터들을 개별 컬럼으로 확장
        factors_df = df_sig['factors_json'].apply(lambda x: pd.Series(json.loads(x)))
        df_sig = pd.concat([df_sig.drop('factors_json', axis=1), factors_df], axis=1)
        
        # RSI 분석
        df_sig['rsi_bin'] = pd.cut(df_sig['rsi_1m'], bins=range(0, 105, 10))
        rsi_stats = df_sig.groupby('rsi_bin')['interval_5m_change'].agg(['count', 'mean']).rename(columns={'mean': 'avg_profit'})
        rsi_stats['win_rate'] = df_sig.groupby('rsi_bin')['interval_5m_change'].apply(lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0)
        
        report.append(f" ✅ 시그널 표본: {len(df_sig)}건")
        # 승률이 높은 상위 3개 구간만 출력 (요약)
        top_rsi = rsi_stats.sort_values('win_rate', ascending=False).head(3)
        for idx, row in top_rsi.iterrows():
            if row['count'] > 0:
                report.append(f" • RSI {idx}: 승률 {row['win_rate']*100:4.1f}% | 예상수익 {row['avg_profit']:5.2f}%")
    else:
        report.append("  (시그널 데이터가 부족합니다.)")

    # --- [섹션 3. 대원칙 가이드] ---
    report.append(f"\n💡 [엔진 최적화 제언]")
    report.append(f" - 1:1:2:4:8 수열에 따른 자금 배분은 현재 유효합니다.")
    report.append(f" - 자금 부족 시 종목 수를 줄여서라도 MAX 단계 물타기를 사수하십시오.")
    
    return "\n".join(report)

_cache_data = None
_last_cache_time = 0

def update_cache():
    global _cache_data, _last_cache_time
    try:
        conn = sqlite3.connect(DB_FILE)
        query = '''
        SELECT s.factors_json, r.interval_5m_change
        FROM signal_snapshots s
        JOIN response_metrics r ON s.id = r.signal_id
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            def safe_json_load(x):
                try: return pd.Series(json.loads(x))
                except: return pd.Series()
            
            factors_df = df['factors_json'].apply(safe_json_load)
            _cache_data = pd.concat([df.drop('factors_json', axis=1), factors_df], axis=1)
            _last_cache_time = time.time()
            logger.info(f"🔄 [LASTTRADE Math] {len(_cache_data)}건의 시그널 캐시 갱신 완료")
    except Exception as e:
        logger.error(f"지식 베이스 갱신 실패: {e}")

def get_win_probability(rsi_1m, rsi_diff=None):
    """
    RSI 기반 예상 승률을 계산합니다.
    (추후 WATER 단계 데이터와 연동하여 보정 가능)
    """
    global _cache_data, _last_cache_time
    
    if _cache_data is None or (time.time() - _last_cache_time > 1800):
        update_cache()
    
    if _cache_data is None or _cache_data.empty:
        return 0.5, 0
        
    base_prob = 0.5
    total_count = 0
    
    try:
        # 데이터가 충분한지 확인
        rsi_margin = 5
        rsi_group = _cache_data[(_cache_data.get('rsi_1m', 0) >= rsi_1m - rsi_margin) & (_cache_data.get('rsi_1m', 0) <= rsi_1m + rsi_margin)]
        
        if not rsi_group.empty:
            rsi_prob = (rsi_group['interval_5m_change'] > 0).sum() / len(rsi_group)
            total_count = len(rsi_group)
            base_prob = rsi_prob
                
    except Exception as e:
        logger.error(f"승률 계산 오류: {e}")
        
    return base_prob, total_count

def evaluate_exit_strength(rsi_1m, profit_rate):
    """
    AI 기반 실시간 익절 강도 판독 (설정창 팩터 인지 버전)
    반환값 (action, reason): 
      - action: 'PARTIAL_SELL'(분할매도 권장), 'HOLD'(보유), 'FULL_SELL'(완전매도)
    """
    from get_setting import get_setting
    
    # 설정창의 익절/손절 기준 파악 (AI 인지 핵심)
    tp_rate = float(get_setting('take_profit_rate', 2.0))
    sl_rate = float(get_setting('stop_loss_rate', -3.0))
    
    # 1. 과매수 구간 진입 패턴 분석 (목표 수익률의 70% 이상 도달 시 RSI 과열 체크)
    target_threshold = tp_rate * 0.7 # 목표의 70%
    
    if rsi_1m >= 75: # 매우 강력한 과매수
        if profit_rate >= target_threshold:
            return 'PARTIAL_SELL', f'AI판단: RSI 극과열({rsi_1m:.0f} > 75) & 목표치 70% 도달 분할익절'
        if profit_rate >= 1.0:
            return 'PARTIAL_SELL', f'AI판단: RSI 과열({rsi_1m:.0f}) 및 최소수익(1%) 확보 분할익절'
            
    if rsi_1m >= 70 and profit_rate >= tp_rate * 0.9: # 목표가 근접 & 과매수
        return 'PARTIAL_SELL', f'AI판단: RSI 과열({rsi_1m:.0f}) & 목표가 근접(90% 도달) 분할익절'
    
    # 2. 손절 방어 AI (나중에 확장 가능)
    return 'HOLD', '상승 여력 충분 (설정 범위 내)'

def evaluate_risk_strength(rsi_1m, profit_rate, current_step):
    """
    AI 기반 실시간 리스크(손절) 강도 판독
    조기 손절 단계에서 단순히 전량 매도하기보다 AI가 추세를 판단하여 비중을 조절합니다.
    """
    from get_setting import get_setting
    
    sl_rate = float(get_setting('stop_loss_rate', -3.0))
    split_buy_cnt = int(get_setting('split_buy_cnt', 5))
    
    # 1. 치명적 위기 판단 (전역 손절 근접 또는 RSI 붕괴)
    if rsi_1m <= 20: # 극심한 침체
        if profit_rate <= sl_rate * 1.2: # 손절가보다 20% 더 빠짐
            return 'FULL_SELL', f'AI판단: RSI 지지선 붕괴({rsi_1m:.0f}) 및 과도 하락. 전량 매도'
            
    # 2. 전 단계(Step 1~)에서의 선제적 리스크 관리 (신고가 추세 추종 전략)
    # 사장님 지시: RSI 40까진 물타기/홀딩, 35 붕괴 시 추세 이탈로 보고 선제적 비중 축소
    if current_step >= 1: 
        # 신고가 종목 원칙: RSI 35 미만은 '위험 신호' (40대 반등 실패로 간주)
        if rsi_1m is not None and rsi_1m < 35:
             return 'PARTIAL_SELL', f'AI판단: 신고가 추세 붕괴(RSI {rsi_1m:.0f} < 35). {current_step}단계 비중 50% 축소'

    # 3. 조기 손절 단계(MAX)에서의 추가 방어 (신고가 특성 반영)
    if current_step >= split_buy_cnt - 1: # 마지막 단계 근접
         # -3% 도달 시 대응 (이미 RSI 30 미만은 위에서 처리됨)
         # RSI가 30 이상인데도 -3%까지 밀렸다면?? -> 이건 힘이 빠진 것. 
         # 신고가 종목이라도 MAX 단계에서 -3%면 위험 관리 필요
         warning_rate = -3.0 
         if profit_rate <= warning_rate:
             if rsi_1m is not None and rsi_1m >= 30:
                 return 'PARTIAL_SELL', f'AI판단: MAX단계 위험 수위({profit_rate}%) 도달. (RSI {rsi_1m:.0f} >= 30 이지만 손실 확대로 축소)'
             
             # 혹시 RSI 데이터 없으면 안전하게 축소
             if rsi_1m is None:
                 return 'PARTIAL_SELL', f'AI판단: MAX단계 위험 수위 도달(데이터 없음). 안전상 50% 축소'
             
         if profit_rate <= sl_rate:
             return 'PARTIAL_SELL', f'AI판단: MAX단계 손절가({sl_rate}%) 도달. 최후의 보루 50% 축소'

    # 3. 추세 이탈 감지
    if rsi_1m < 30 and profit_rate < -2.0:
        return 'PARTIAL_SELL', f'AI판단: 단기 추세 이탈(RSI {rsi_1m:.0f}) 감지. 리스크 관리차원 50% 매도'

    return 'HOLD', '리스크 감내 가능 구간'

if __name__ == "__main__":
    analyze_signals()
