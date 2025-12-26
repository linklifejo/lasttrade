import sqlite3
import os

DB_FILE = 'trading.db'

def normalize():
    if not os.path.exists(DB_FILE):
        print("DB not found")
        return
        
    try:
        conn = sqlite3.connect(DB_FILE, timeout=60)
        cursor = conn.cursor()
        
        # Normalize SELL -> sell
        cursor.execute("UPDATE trades SET type = 'sell' WHERE type = 'SELL'")
        count_sell = cursor.rowcount
        
        # Normalize BUY -> buy
        cursor.execute("UPDATE trades SET type = 'buy' WHERE type = 'BUY'")
        count_buy = cursor.rowcount
        
        conn.commit()
        print(f"Normalized: {count_sell} sells, {count_buy} buys")
        
    except Exception as e:
        print(f"Error during normalization: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    normalize()
