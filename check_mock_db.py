import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print("=== Mock Stocks ===")
cursor.execute('SELECT code, name, base_price FROM mock_stocks LIMIT 10')
for row in cursor.fetchall():
    print(row)

print("\n=== Mock Prices ===")
cursor.execute('SELECT code, current FROM mock_prices LIMIT 10')
for row in cursor.fetchall():
    print(row)

conn.close()
