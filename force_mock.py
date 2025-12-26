import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
print(f"Opening DB: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Trading Mode = MOCK
    cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('trading_mode', 'MOCK', datetime('now'))")
    
    # 2. use_mock_server = true
    cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('use_mock_server', 'true', datetime('now'))")
    
    # 3. is_paper_trading = false
    cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('is_paper_trading', 'false', datetime('now'))")
    
    conn.commit()
    print("DB Forced Update: MOCK MODE ACTIVATED")
    
    # Verify
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('trading_mode', 'use_mock_server')")
    rows = cursor.fetchall()
    print("Verification:", rows)
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
