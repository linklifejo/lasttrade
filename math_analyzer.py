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

if __name__ == "__main__":
    analyze_signals()
