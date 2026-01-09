import sqlite3
conn = sqlite3.connect('trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.execute("SELECT timestamp, type, code, name, qty, profit_rate, reason FROM trades ORDER BY id DESC LIMIT 20")
print("Latest 20 Trades (Including type):")
for r in cursor.fetchall():
    print(f"[{r['type'].upper()}] {r['timestamp']} | {r['code']} | {r['name']} | {r['qty']}주 | {r['profit_rate']}% | {r['reason']}")
conn.close()
