import sqlite3
import os

dbs = ['trading.db', 'trading.db.old', 'trading.db.bak_20251231']

for db_name in dbs:
    if not os.path.exists(db_name):
        continue
    print(f"--- {db_name} ---")
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for t in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {t}")
                cnt = cursor.fetchone()[0]
                if cnt > 0:
                    print(f"  {t}: {cnt} rows")
                    if t == 'trades':
                        cursor.execute("SELECT mode, count(*) FROM trades GROUP BY mode")
                        m = cursor.fetchall()
                        print(f"    Modes: {m}")
                    if t in ['mock_holdings', 'mock_account', 'settings']:
                        # only print sample if requested or useful
                        pass
            except:
                pass
        conn.close()
    except Exception as e:
        print(f"  Error: {e}")
