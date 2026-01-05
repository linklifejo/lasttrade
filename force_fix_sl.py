
import sqlite3

def fix_all_sl():
    conn = sqlite3.connect('c:/lasttrade/trading.db')
    cursor = conn.cursor()
    
    # 1. 존재하는 모든 키 확인
    cursor.execute("SELECT key, value FROM settings WHERE key LIKE '%loss%' OR key LIKE '%sl%'")
    rows = cursor.fetchall()
    print("🔍 현재 DB에 있는 손절 관련 키:")
    for key, val in rows:
        print(f"  [{key}] = {val}")
        
    # 2. 무조건 업데이트 (존재하든 말든 일단 다 때려박음)
    keys_to_fix = ['stop_loss_rate', 'sl_rate', 'SL_RATE', 'STOP_LOSS_RATE']
    
    for k in keys_to_fix:
        # INSERT OR REPLACE로 없으면 만들고 있으면 덮어씀
        cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, '-1.0', datetime('now'))", (k,))
        
    conn.commit()
    print("\n✅ 모든 손절 키를 -1.0으로 강제 통일했습니다.")
    
    # 3. 확인
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('stop_loss_rate', 'sl_rate')")
    final_rows = cursor.fetchall()
    for row in final_rows:
        print(f"  ✅ 검증: {row[0]} -> {row[1]}")
        
    conn.close()

if __name__ == "__main__":
    fix_all_sl()
