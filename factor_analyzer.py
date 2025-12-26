import sqlite3
import pandas as pd
import json
import os
from logger import logger

def analyze_factors():
    """수집된 시그널 스냅샷과 대응 데이터를 수학적으로 분석"""
    db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
    
    try:
        conn = sqlite3.connect(db_file)
        
        # 1. 데이터 로드 (시그널 + 대응 결과 조인)
        query = '''
            SELECT s.factors_json, r.interval_1m_change, r.interval_5m_change, r.max_profit, r.max_drawdown
            FROM signal_snapshots s
            JOIN response_metrics r ON s.id = r.signal_id
        '''
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("❌ 분석할 데이터가 부족합니다. 장중에 시그널이 쌓여야 합니다.")
            return

        # 2. JSON 팩터 풀기
        factors_df = df['factors_json'].apply(lambda x: pd.Series(json.loads(x)))
        analysis_df = pd.concat([factors_df, df.drop('factors_json', axis=1)], axis=1)
        
        print("\n" + "="*50)
        print("📊 [Last Trade] 수학적 팩터 분석 리포트")
        print("="*50)
        
        # 3. 상관관계 분석 (RSI와 5분 수익률의 관계 등)
        target_col = 'interval_5m_change'
        correlations = analysis_df.corr()[target_col].sort_values(ascending=False)
        
        print(f"\n✅ 5분 뒤 수익률({target_col})과 가장 상관관계가 높은 팩터 순위:")
        print(correlations.drop([target_col, 'interval_1m_change', 'max_profit', 'max_drawdown'], errors='ignore'))
        
        # 4. 구간별 최적 기대값 도출 (예: RSI 1m 구간별 평균 수익률)
        if 'rsi_1m' in analysis_df.columns:
            analysis_df['rsi_group'] = (analysis_df['rsi_1m'] // 10) * 10
            rsi_stats = analysis_df.groupby('rsi_group')[target_col].mean()
            print(f"\n📈 RSI 1분봉 구간별 평균 수익률 (기대값):")
            print(rsi_stats)
            
        # 5. 수학적 결론
        best_rsi = rsi_stats.idxmax() if 'rsi_group' in locals() and not rsi_stats.empty else "N/A"
        print(f"\n💡 [수학적 제안] 현재 데이터 기준, RSI 1분봉이 {best_rsi}대일 때 승률이 가장 높습니다.")
        print("="*50 + "\n")
        
        conn.close()
    except Exception as e:
        print(f"분석 중 오류 발생: {e}")

if __name__ == "__main__":
    analyze_factors()
