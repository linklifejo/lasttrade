import sqlite3
import pandas as pd
from database import DB_FILE
from math_analyzer import analyze_signals

def check_status():
    print("🔍 [학습 데이터 현황 점검]")
    conn = sqlite3.connect(DB_FILE)
    
    try:
        # 1. 시그널 스냅샷 확인
        cursor = conn.execute("SELECT count(*) FROM signal_snapshots")
        signals = cursor.fetchone()[0]
        print(f"- 수집된 시그널(Snapshots): {signals}건")
        
        # 2. 성과 지표(Metrics) 확인
        cursor = conn.execute("SELECT count(*) FROM response_metrics")
        metrics = cursor.fetchone()[0]
        print(f"- 학습된 성과(Metrics): {metrics}건")
        
        if metrics > 0:
            cursor = conn.execute("SELECT * FROM response_metrics ORDER BY id DESC LIMIT 3")
            print("  (최근 3건 데이터 예시)")
            for row in cursor.fetchall():
                print("  ", row)
    except Exception as e:
        print(f"❌ DB 조회 오류: {e}")
    finally:
        conn.close()
        
    print("\n📊 [엔진 분석 리포트 실행]")
    try:
        analyze_signals()
    except Exception as e:
        print(f"❌ 분석 실행 중 오류: {e}")

if __name__ == "__main__":
    check_status()
