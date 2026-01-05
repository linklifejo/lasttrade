
import sqlite3
import os
import json

DB_PATH = 'c:/lasttrade/trading.db'

def check_integrity():
    if not os.path.exists(DB_PATH):
        print("❌ DB file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔍 Checking Settings Integrity...")
    
    # 1. Check SL_RATE
    cursor.execute("SELECT value FROM settings WHERE key = 'stop_loss_rate'")
    row_sl = cursor.fetchone()
    sl_val = row_sl[0] if row_sl else "N/A"
    
    # 2. Check Target Stock Count
    cursor.execute("SELECT value FROM settings WHERE key = 'target_stock_count'")
    row_target = cursor.fetchone()
    target_val = row_target[0] if row_target else "N/A"
    
    # 3. Check Strategy
    cursor.execute("SELECT value FROM settings WHERE key = 'single_stock_strategy'")
    row_strat = cursor.fetchone()
    strat_val = row_strat[0] if row_strat else "N/A"

    print(f"  - [DB] Stop Loss Rate: {sl_val}")
    print(f"  - [DB] Target Stock Count: {target_val}")
    print(f"  - [DB] Strategy: {strat_val}")
    
    conn.close()

if __name__ == "__main__":
    check_integrity()
