import sqlite3
import time

try:
    conn = sqlite3.connect('trading.db', timeout=10)
    cursor = conn.cursor()
    
    # trading_mode
    cursor.execute("SELECT key, value FROM settings WHERE key='trading_mode'")
    res1 = cursor.fetchone()
    print(f"trading_mode: {res1}")
    
    # use_mock_server
    cursor.execute("SELECT key, value FROM settings WHERE key='use_mock_server'")
    res2 = cursor.fetchone()
    print(f"use_mock_server: {res2}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
