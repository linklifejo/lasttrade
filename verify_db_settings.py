
import sqlite3
import os

DB_PATH = 'c:/lasttrade/trading.db'

def verify_all_settings():
    if not os.path.exists(DB_PATH):
        print("❌ DB file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n📊 [DB 검증] 현재 저장된 모든 설정값 (trading.db/settings)")
    print("=" * 60)
    print(f"{'Key (설정 항목)':<35} | {'Value (값)':<20}")
    print("-" * 60)
    
    try:
        cursor.execute("SELECT key, value FROM settings ORDER BY key")
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ 설정 테이블이 비어있습니다!")
        
        for row in rows:
            key = row['key']
            val = row['value']
            
            # 중요 항목 강조
            marker = ""
            if key in ['stop_loss_rate', 'sl_rate', 'take_profit_rate', 'single_stock_strategy', 'target_stock_count']:
                marker = "👈 (확인)"
                
            print(f"{key:<35} | {val:<20} {marker}")
            
    except Exception as e:
        print(f"❌ DB 조회 오류: {e}")
        
    print("=" * 60)
    conn.close()

if __name__ == "__main__":
    verify_all_settings()
