import sqlite3
import os

def check_db(db_name):
    if not os.path.exists(db_name):
        return
    print(f"\n=== DATABASE: {db_name} ===")
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        for t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            count = cursor.fetchone()[0]
            print(f"Table: {t:20} | Rows: {count}")
            if count > 0 and t == 'trades':
                cursor.execute("SELECT DISTINCT mode FROM trades")
                modes = [r[0] for r in cursor.fetchall()]
                print(f"  Modes found in trades: {modes}")
        conn.close()
    except Exception as e:
        print(f"Error checking {db_name}: {e}")

dbs = [f for f in os.listdir('.') if f.endswith('.db') or '.db.' in f]
for db in dbs:
    check_db(db)
