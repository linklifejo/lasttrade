import sqlite3
import os

dbs = ['trading.db', 'trading.db.old', 'trading.db.bak_20251231']

for db_name in dbs:
    if not os.path.exists(db_name):
        continue
    print(f"--- Checking {db_name} ---")
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        # Check if trades table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if cursor.fetchone():
            cursor.execute("SELECT mode, COUNT(*) FROM trades GROUP BY mode")
            rows = cursor.fetchall()
            for row in rows:
                print(f"  MODE: {row[0]}, COUNT: {row[1]}")
                if row[0] != 'MOCK' and row[1] > 0:
                    print(f"  Sample {row[0]} trades:")
                    cursor.execute(f"SELECT * FROM trades WHERE mode = '{row[0]}' LIMIT 2")
                    for t in cursor.fetchall():
                        print(f"    {t}")
        else:
            print("  No trades table found.")
        conn.close()
    except Exception as e:
        print(f"  Error: {e}")
