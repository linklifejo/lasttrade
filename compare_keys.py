import sqlite3
import os

keys = ['real_app_key', 'real_app_secret', 'paper_app_key', 'paper_app_secret', 'my_account']
dbs = ['trading.db', 'trading.db.bak_20251231', 'trading.db.old']

for db in dbs:
    if not os.path.exists(db):
        continue
    print(f"--- {db} ---")
    conn = sqlite3.connect(db)
    for k in keys:
        r = conn.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
        print(f"  {k}: {r[0] if r else 'N/A'}")
    conn.close()
