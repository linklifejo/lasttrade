import sqlite3
try:
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades WHERE timestamp LIKE '2026-01-07%'")
    conn.commit()
    print("✅ Deleted all trade records for 2026-01-07.")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")
