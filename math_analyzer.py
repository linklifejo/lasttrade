import time
import sqlite3
import json
import pandas as pd
from database import DB_FILE
from logger import logger

def analyze_signals():
    """기존 분석 로직을 수행하고 결과를 출력합니다."""
    report = get_analysis_report()
    print(report)
    return report

def get_analysis_report():
    """분석 성과 요약을 문자열로 반환합니다."""
    conn = sqlite3.connect(DB_FILE)
    query = '''
    SELECT 
        s.id, s.timestamp, s.code, s.factors_json, 
        r.interval_1m_change, r.interval_5m_change, r.max_drawdown, r.max_profit
    FROM signal_snapshots s
    JOIN response_metrics r ON s.id = r.signal_id
    '''
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        return f"❌ 데이터 로드 실패: {e}"
    finally:
        conn.close()
    
    if df.empty:
        return "❌ 분석할 데이터가 부족합니다."
    
    # 2. JSON 형태의 팩터들을 개별 컬럼으로 확장
    factors_df = df['factors_json'].apply(lambda x: pd.Series(json.loads(x)))
    df = pd.concat([df.drop('factors_json', axis=1), factors_df], axis=1)
    
    report = []
    report.append(f"📊 [LASTTRADE 수학적 엔진 심화 분석 리포트]")
    report.append(f"✅ 총 분석 표본: {len(df)}건")
    report.append(f"📡 [대원칙] RSI 필터링보다 WATER 전략(평단가/수열) 관점에서 성과 분석\n")
    
    # --- RSI_1m 분석 ---
    df['rsi_bin'] = pd.cut(df['rsi_1m'], bins=range(0, 105, 10))
    rsi_stats = df.groupby('rsi_bin')['interval_5m_change'].agg(['count', 'mean']).rename(columns={'mean': 'avg_profit'})
    rsi_stats['win_rate'] = df.groupby('rsi_bin')['interval_5m_change'].apply(lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0)
    
    report.append("[1. RSI 1m 구간별 성과]")
    for idx, row in rsi_stats.dropna().iterrows():
        if row['count'] > 0:
            report.append(f" • {idx}: {int(row['count']):3d}건 | 승률 {row['win_rate']*100:4.1f}% | 수익 {row['avg_profit']:5.2f}%")
    
    # --- RSI Diff (1m - 3m) 분석 ---
    if 'rsi_diff' in df.columns:
        df['diff_bin'] = pd.cut(df['rsi_diff'], bins=[-100, -5, -2, 0, 2, 5, 100])
        diff_stats = df.groupby('diff_bin')['interval_5m_change'].agg(['count', 'mean']).rename(columns={'mean': 'avg_profit'})
        diff_stats['win_rate'] = df.groupby('diff_bin')['interval_5m_change'].apply(lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0)
        
        report.append("\n[2. RSI Difference (1m-3m) 성과]")
        for idx, row in diff_stats.dropna().iterrows():
            if row['count'] > 0:
                report.append(f" • {idx}: {int(row['count']):3d}건 | 승률 {row['win_rate']*100:4.1f}% | 수익 {row['avg_profit']:5.2f}%")

    # 4. 결합 최적 조합 추천
    report.append(f"\n💡 [엔진 최적화 제언]")
    best_rsi = rsi_stats[rsi_stats['count'] >= 3]['win_rate'].idxmax() if not rsi_stats[rsi_stats['count'] >= 3].empty else "N/A"
    report.append(f" - 최고 승률 RSI 구간: {best_rsi}")
    
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
            factors_df = df['factors_json'].apply(lambda x: pd.Series(json.loads(x)))
            _cache_data = pd.concat([df.drop('factors_json', axis=1), factors_df], axis=1)
            _last_cache_time = time.time()
            logger.info(f"🔄 [LASTTRADE Math] {len(_cache_data)}건의 데이터를 기반으로 지식 베이스(대원칙 기반) 갱신 완료")
    except Exception as e:
        logger.error(f"지식 베이스 갱신 실패: {e}")

def get_win_probability(rsi_1m, rsi_diff=None):
    """
    RSI와 RSI 차이를 결합하여 예상 승률을 계산합니다.
    """
    global _cache_data, _last_cache_time
    
    # 30분마다 캐시 갱신
    if _cache_data is None or (time.time() - _last_cache_time > 1800):
        update_cache()
    
    if _cache_data is None or _cache_data.empty:
        return 0.5, 0 # 데이터 없으면 50%
        
    # 기본값 설정
    base_prob = 0.5
    total_count = 0
    
    try:
        # 1. RSI 기반 확률 필터링
        rsi_margin = 5
        rsi_group = _cache_data[(_cache_data['rsi_1m'] >= rsi_1m - rsi_margin) & (_cache_data['rsi_1m'] <= rsi_1m + rsi_margin)]
        
        if not rsi_group.empty:
            rsi_prob = (rsi_group['interval_5m_change'] > 0).sum() / len(rsi_group)
            total_count = len(rsi_group)
            
            # 2. RSI Diff 보정 (있을 경우)
            if rsi_diff is not None and 'rsi_diff' in rsi_group.columns:
                diff_margin = 2
                diff_group = rsi_group[(rsi_group['rsi_diff'] >= rsi_diff - diff_margin) & (rsi_group['rsi_diff'] <= rsi_diff + diff_margin)]
                if len(diff_group) >= 3:
                    diff_prob = (diff_group['interval_5m_change'] > 0).sum() / len(diff_group)
                    # RSI 확률과 Diff 확률의 가중 평균
                    base_prob = (rsi_prob * 0.4) + (diff_prob * 0.6)
                    total_count = len(diff_group)
                else:
                    base_prob = rsi_prob
            else:
                base_prob = rsi_prob
                
    except Exception as e:
        logger.error(f"승률 계산 중 오류: {e}")
        
    return base_prob, total_count

if __name__ == "__main__":
    analyze_signals()
