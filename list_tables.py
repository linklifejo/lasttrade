import sqlite3
import os

DB_FILE = 'trading.db'

def list_tables():
    if not os.path.exists(DB_FILE):
        print(f"❌ DB 파일 없음: {DB_FILE}")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📅 Tables in {DB_FILE}:")
        for t in tables:
            print(f" - {t[0]}")
        conn.close()
    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    list_tables()
