import sqlite3

def update_db_setting():
    db_path = 'trading.db'
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 현재 값 확인
        cursor.execute("SELECT value FROM settings WHERE key='single_stock_rate'")
        row = cursor.fetchone()
        current_val = row[0] if row else "None"
        print(f"[Before] single_stock_rate: {current_val}")
        
        # 2. 값 5.0으로 강제 업데이트 (없으면 INSERT)
        # UPSERT 구문 대신 안전한 방식 사용
        if row:
            cursor.execute("UPDATE settings SET value=? WHERE key='single_stock_rate'", ('5.0',))
        else:
            cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ('single_stock_rate', '5.0'))
            
        conn.commit()
        print(f"[Success] Updated 'single_stock_rate' to 5.0")
        
    except Exception as e:
        print(f"[Error] {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    update_db_setting()
