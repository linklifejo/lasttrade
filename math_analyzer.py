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
        def extract_step(reason):
            if not reason: return 1
            match = re.search(r'STEP_(\d+)', str(reason))
            return int(match.group(1)) if match else 1
        
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
        factors_df = df_sig['factors_json'].apply(lambda x: pd.Series(json.loads(x)))
        df_sig = pd.concat([df_sig.drop('factors_json', axis=1), factors_df], axis=1)
        
        df_sig['rsi_bin'] = pd.cut(df_sig['rsi_1m'], bins=range(0, 105, 10))
        rsi_stats = df_sig.groupby('rsi_bin')['interval_5m_change'].agg(['count', 'mean']).rename(columns={'mean': 'avg_profit'})
        rsi_stats['win_rate'] = df_sig.groupby('rsi_bin')['interval_5m_change'].apply(lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0)
        
        report.append(f" ✅ 시그널 표본: {len(df_sig)}건")
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
    from get_setting import get_setting
    global _cache_data, _last_cache_time
    if _cache_data is None or (time.time() - _last_cache_time > 1800):
        update_cache()
    if _cache_data is None or _cache_data.empty:
        return 0.5, 0
    base_prob = 0.5
    total_count = 0
    try:
        rsi_margin = int(get_setting('math_rsi_margin', 5))
        rsi_group = _cache_data[(_cache_data.get('rsi_1m', 0) >= rsi_1m - rsi_margin) & (_cache_data.get('rsi_1m', 0) <= rsi_1m + rsi_margin)]
        if not rsi_group.empty:
            rsi_prob = (rsi_group['interval_5m_change'] > 0).sum() / len(rsi_group)
            total_count = len(rsi_group)
            base_prob = rsi_prob
    except Exception as e:
        logger.error(f"승률 계산 오류: {e}")
    return base_prob, total_count

def evaluate_exit_strength(rsi_1m, profit_rate):
    from get_setting import get_setting
    tp_rate = float(get_setting('take_profit_rate', 10.0))
    target_70_rt = float(get_setting('exit_profit_ratio_70', 0.7))
    target_90_rt = float(get_setting('exit_profit_ratio_90', 0.9))
    critical_rsi = float(get_setting('exit_rsi_critical', 75.0))
    high_rsi = float(get_setting('exit_rsi_high', 70.0))
    min_exit_profit = float(get_setting('exit_min_profit_limit', 1.0))
    
    target_threshold = tp_rate * target_70_rt 
    
    if rsi_1m >= critical_rsi:
        if profit_rate >= target_threshold:
            return 'PARTIAL_SELL', f'AI판단: RSI 극과열({rsi_1m:.0f} > {critical_rsi}) & 목표치 {target_70_rt*100:.0f}% 도달 분할익절'
        if profit_rate >= min_exit_profit:
            return 'PARTIAL_SELL', f'AI판단: RSI 과열({rsi_1m:.0f}) 및 최소수익({min_exit_profit}%) 확보 분할익절'
            
    if rsi_1m >= high_rsi and profit_rate >= tp_rate * target_90_rt:
        return 'PARTIAL_SELL', f'AI판단: RSI 과열({rsi_1m:.0f}) & 목표가 근접({target_90_rt*100:.0f}% 도달) 분할익절'
    
    return 'HOLD', '상승 여력 충분 (설정 범위 내)'

def evaluate_risk_strength(rsi_1m, profit_rate, current_step):
    """
    AI 및 사용자 원칙 기반 리스크 판독
    유저 원칙: 1~3차는 물타기 집중(손절 금지), 오직 MAX 단계에서만 보루 작동
    """
    from get_setting import get_setting
    
    # 설정 로드
    sl_rate = float(get_setting('stop_loss_rate', -5.0))
    sb_cnt = int(get_setting('split_buy_cnt', 5))
    
    # 조기 손절 단계(MAX) 판별
    try:
        default_early = sb_cnt - 1
        if default_early < 1: default_early = 1
        early_stop_limit = int(get_setting('early_stop_step', default_early))
    except:
        early_stop_limit = 4

    # [대원칙] 1~3차 단계는 무조건 물타기 구간 (AI 리스크 관리 차단)
    if current_step < early_stop_limit:
        return 'HOLD', f'{current_step}단계 물타기 집중 구간'

    # --- 여기서부터는 MAX(보루) 단계 로직 ---
    
    if current_step >= early_stop_limit:
        # 1. 사용자 설정 최종 손절가 (-5.0% 등) 체크 (최우선 순위)
        if profit_rate <= sl_rate:
             return 'FULL_SELL', f'상황: MAX단계 최종 손절가({sl_rate}%) 도달. 전량 매도'

        # 2. MAX 단계 데드라인 (-4.0%) 체크 (50% 비중 축소)
        max_risk_limit = float(get_setting('max_step_risk_limit', -4.0))
        if profit_rate <= max_risk_limit:
            return 'PARTIAL_SELL', f'상황: MAX({early_stop_limit}차) 단계 데드라인({max_risk_limit}%) 도달. 50% 비중 축소'
        
        # 3. MAX 단계 추세 이탈 감지 (RSI 기반)
        risk_trend_break_rsi = float(get_setting('risk_trend_break_rsi', 30.0))
        risk_trend_break_pl = float(get_setting('risk_trend_break_pl', -2.0))
        if rsi_1m is not None:
            if rsi_1m < risk_trend_break_rsi and profit_rate < risk_trend_break_pl:
                return 'PARTIAL_SELL', f'AI판단: MAX단계 추세 이탈(RSI {rsi_1m:.0f}) 감지. 50% 매도'

    return 'HOLD', 'MAX단계 리스크 감내 구간'

if __name__ == "__main__":
    analyze_signals()
