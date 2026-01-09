
import sqlite3
import json

def check_settings():
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        print("--- CURRENT SETTINGS IN DB ---")
        for key, value in rows:
            print(f"{key}: {value}")
        conn.close()
    except Exception as e:
        print(f"Error checking settings: {e}")

if __name__ == "__main__":
    check_settings()
