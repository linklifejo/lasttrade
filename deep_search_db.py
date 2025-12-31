import sqlite3
import os

def search_text_in_db(db_name, search_text):
    if not os.path.exists(db_name):
        return
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    for t in tables:
        try:
            cursor.execute(f"SELECT * FROM {t}")
            rows = cursor.fetchall()
            for i, row in enumerate(rows):
                if any(search_text in str(cell) for cell in row):
                    print(f"Found '{search_text}' in {db_name}, table '{t}', row {i}: {row}")
        except:
            pass
    conn.close()

search_text = "REAL"  # or "PAPER"
dbs = [f for f in os.listdir('.') if f.endswith('.db') or '.db.' in f]
for db in dbs:
    search_text_in_db(db, "REAL")
    search_text_in_db(db, "PAPER")
