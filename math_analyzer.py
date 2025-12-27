import sqlite3
import json
import pandas as pd
from database import DB_FILE
from logger import logger

def analyze_signals():
    """
    기존 분석 로직을 수행하고 결과를 출력합니다.
    """
    report = get_analysis_report()
    print(report)
    return report

def get_analysis_report():
    """
    분석 성과 요약을 문자열로 반환합니다.
    """
    conn = sqlite3.connect(DB_FILE)
    
    # 1. 데이터 로드 (시그널 + 성과지표)
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
        return "❌ 분석할 데이터가 부족합니다. 시그널과 대응 데이터가 쌓일 때까지 기다려주세요."
    
    # 2. JSON 형태의 팩터들을 개별 컬럼으로 확장
    factors_df = df['factors_json'].apply(lambda x: pd.Series(json.loads(x)))
    df = pd.concat([df.drop('factors_json', axis=1), factors_df], axis=1)
    
    report = []
    report.append(f"📊 [수학적 엔진 분석 리포트]")
    report.append(f"✅ 분석 대상: {len(df)}건\n")
    
    # 3. RSI_1m 기준 구간별 성과 분석
    df['rsi_bin'] = pd.cut(df['rsi_1m'], bins=range(0, 105, 5))
    
    performance = df.groupby('rsi_bin').agg({
        'id': 'count',
        'interval_1m_change': 'mean',
        'interval_5m_change': 'mean',
        'max_profit': 'mean',
        'max_drawdown': 'min'
    }).rename(columns={'id': 'count'})
    
    win_rate = df.groupby('rsi_bin')['interval_5m_change'].apply(lambda x: (x > 0).sum() / len(x) if len(x) > 0 else 0)
    performance['win_rate'] = win_rate
    
    report.append("[RSI 1m 구간별 성과]")
    perf_clean = performance.dropna()
    if not perf_clean.empty:
        for idx, row in perf_clean.iterrows():
            report.append(f"• {idx}: {int(row['count'])}건 | 승률 {row['win_rate']*100:.1f}% | 수익 {row['interval_5m_change']:.2f}%")
    else:
        report.append("(데이터 없음)")
    
    # 4. 최적 파라미터 추천
    reliable = performance[performance['count'] >= 3] # 최소 건수 완화
    if not reliable.empty:
        best_rsi_bin = reliable['interval_5m_change'].idxmax()
        best_stats = reliable.loc[best_rsi_bin]
        
        report.append(f"\n💡 [추천 파라미터]")
        report.append(f" - 최적 RSI 1m 구간: {best_rsi_bin}")
        report.append(f" - 기대 수익률(5m): {best_stats['interval_5m_change']:.2f}%")
        report.append(f" - 해당 구간 승률: {best_stats['win_rate']*100:.1f}%")
    else:
        report.append("\n💡 유의미한 패턴을 찾기에 데이터가 부족합니다 (최소 3건 필요).")

    return "\n".join(report)

_cache_win_rates = None
_last_cache_time = 0

def get_win_probability(rsi_1m):
    """
    특정 RSI 값에 대한 (기대 승률, 표본 수)를 반환합니다. (캐시 사용)
    """
    global _cache_win_rates, _last_cache_time
    
    # 1시간마다 캐시 갱신
    if _cache_win_rates is None or (time.time() - _last_cache_time > 3600):
        update_cache()
    
    if _cache_win_rates is None or _cache_win_rates.empty:
        return 0.5, 0
        
    # 해당 RSI가 속한 구간 찾기
    for idx, row in _cache_win_rates.iterrows():
        if rsi_1m in idx:
            return float(row['win_rate']), int(row['count'])
            
    return 0.5, 0

def update_cache():
    global _cache_win_rates, _last_cache_time
    conn = sqlite3.connect(DB_FILE)
    query = '''
    SELECT s.factors_json, r.interval_5m_change
    FROM signal_snapshots s
    JOIN response_metrics r ON s.id = r.signal_id
    '''
    try:
        df = pd.read_sql_query(query, conn)
        if df.empty: return
        
        factors_df = df['factors_json'].apply(lambda x: pd.Series(json.loads(x)))
        df = pd.concat([df.drop('factors_json', axis=1), factors_df], axis=1)
        
        df['rsi_bin'] = pd.cut(df['rsi_1m'], bins=range(0, 105, 5))
        _cache_win_rates = df.groupby('rsi_bin')['interval_5m_change'].apply(
            lambda x: pd.Series({'win_rate': (x > 0).sum() / len(x), 'count': len(x)})
        ).unstack()
        _last_cache_time = time.time()
        logger.info(f"🔄 [Math Cache] 승률 캐시 갱신 완료 ({len(df)}건 기반)")
    except Exception as e:
        logger.error(f"캐시 갱신 실패: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_signals()
