import sqlite3
import pandas as pd

try:
    conn = sqlite3.connect('c:/lasttrade/trading.db')
    
    # 1. 오늘 날짜의 거래 유형별 개수 확인
    query = "SELECT type, COUNT(*) as count FROM trades WHERE DATE(timestamp) = '2026-01-11' GROUP BY type"
    df = pd.read_sql_query(query, conn)
    print("=== 오늘(2026-01-11) 거래 유형 통계 ===")
    print(df)
    
    # 2. 최근 5개 거래 확인 (데이터 샘플)
    query_sample = "SELECT * FROM trades WHERE DATE(timestamp) = '2026-01-11' ORDER BY timestamp DESC LIMIT 5"
    df_sample = pd.read_sql_query(query_sample, conn)
    print("\n=== 최근 거래 샘플 (5건) ===")
    if not df_sample.empty:
        print(df_sample[['timestamp', 'code', 'name', 'type', 'price', 'quantity']])
    else:
        print("샘플 데이터 없음")

    conn.close()

except Exception as e:
    print(f"오류 발생: {e}")
