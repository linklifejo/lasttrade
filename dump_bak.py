import sqlite3
db = 'trading.db.bak_20251231'
conn = sqlite3.connect(db)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"{t}: {cursor.fetchone()[0]}")
    if t == 'trades':
        cursor.execute("SELECT * FROM trades")
        print(cursor.fetchall())
conn.close()
