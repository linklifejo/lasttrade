import sqlite3
import os
from datetime import datetime

DB_FILE = 'trading.db'

def check_status():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. 설정 확인
    print("--- Settings ---")
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('target_stock_count', 'trading_capital_ratio', 'auto_start', 'mock_volatility_rate')")
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]}")
        
    # 2. 보유 종목 확인
    print("\n--- Current Mock Holdings ---")
    cursor.execute("SELECT code, qty, avg_price, current_price FROM mock_holdings")
    holdings = cursor.fetchall()
    print(f"Total Holdings: {len(holdings)}")
    for h in holdings:
        print(f"  - {h[0]}: {h[1]} shares (Avg: {h[2]:.0f} / Cur: {h[3]:.0f})")

    # 3. 미체결 주문 확인
    print("\n--- Outstanding Orders ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='web_commands'")
    if cursor.fetchone():
        cursor.execute("SELECT command, status, timestamp FROM web_commands WHERE status='pending'")
        for cmd in cursor.fetchall():
            print(f"  Pending Cmd: {cmd[0]} ({cmd[2]})")
    
    conn.close()

if __name__ == "__main__":
    check_status()
