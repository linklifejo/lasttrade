import sqlite3

def check_trades():
    try:
        conn = sqlite3.connect('trading.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("--- Trades for 005930 ---")
        cursor.execute("SELECT * FROM trades WHERE code='005930' ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        for row in rows:
            print(dict(row))
            
        print("\n--- Mock Holdings for 005930 ---")
        try:
            cursor.execute("SELECT * FROM mock_holdings WHERE code='005930'")
            rows = cursor.fetchall()
            for row in rows:
                print(dict(row))
        except:
            print("mock_holdings table not found or error")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_trades()
