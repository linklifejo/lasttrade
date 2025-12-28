import sqlite3

try:
    conn = sqlite3.connect('trading.db', timeout=10)
    conn.execute("UPDATE trades SET mode='PAPER' WHERE mode='MOCK'")
    conn.commit()
    print("Successfully converted MOCK logs to PAPER logs.")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
