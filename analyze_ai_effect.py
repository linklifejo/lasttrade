import sqlite3
import pandas as pd
import json

def analyze_effectiveness():
    conn = sqlite3.connect('c:/lasttrade/trading.db')
    
    # 1. 시뮬레이션 성과 히스토리 조회
    print("=== [1] 성과 기록 추이 ===")
    try:
        perf_df = pd.read_sql_query("""
            SELECT start_time as date, win_rate, total_return, trade_count 
            FROM sim_performance 
            ORDER BY start_time DESC LIMIT 10
        """, conn)
        if not perf_df.empty:
            print(perf_df)
        else:
            print("성과 기록이 없습니다.")
    except Exception as e:
        print(f"성과 조회 에러: {e}")

    # 2. 필터링 효과 확인 (Math Filter에 의해 걸러진 시그널 추정)
    print("\n=== [2] 수학적 엔진 적용 사례 (최근 로그 기반) ===")
    # 로그 파일에서 Math Filter나 Math Weight 관련 내용을 찾는 것은 수동으로 해야 하니 일단 DB만 확인
    
    # 3. 현재 적용된 유의미한 가중치들
    print("\n=== [3] 현재 시스템이 학습한 핵심 지표 ===")
    try:
        weights_df = pd.read_sql_query("SELECT * FROM learned_weights", conn)
        print(weights_df)
    except Exception as e:
        print(f"가중치 조회 에러: {e}")

    conn.close()

if __name__ == "__main__":
    analyze_effectiveness()
