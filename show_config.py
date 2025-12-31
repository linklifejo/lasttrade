import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

keys = ['target_stock_count', 'split_buy_cnt', 'single_stock_rate', 
        'mock_volatility_rate', 'single_stock_strategy', 'take_profit_rate', 'stop_loss_rate']

print("=== 현재 트레이딩 설정 ===\n")
for key in keys:
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    if row:
        print(f"{key}: {row[0]}")

conn.close()
