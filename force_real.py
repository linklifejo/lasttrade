import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
print(f"Opening DB: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Trading Mode = REAL
    cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('trading_mode', 'REAL', datetime('now'))")
    
    # 2. use_mock_server = false
    cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('use_mock_server', 'false', datetime('now'))")
    
    # 3. is_paper_trading = false
    cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('is_paper_trading', 'false', datetime('now'))")
    
    conn.commit()
    print("DB Forced Update: REAL MODE ACTIVATED")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
