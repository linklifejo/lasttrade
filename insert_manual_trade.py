import sqlite3
from datetime import datetime

db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 우리로 (046970) 매수 정보 (이전 조회 결과 기반)
code = '046970'
name = '우리로'
qty = 1
buy_price = 1436.0
sell_price = 1443.0 # +0.5% 수준 계산 (1436 * 1.005)
profit_rate = 0.5
sell_reason = '수동익절(Force)'
timestamp = '2026-01-12 15:10:48'
mode = 'REAL'

try:
    cursor.execute('''
        INSERT INTO trades (timestamp, code, name, type, qty, price, amt, profit_rate, reason, mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, code, name, 'sell', qty, sell_price, sell_price * qty, profit_rate, sell_reason, mode))
    
    conn.commit()
    print(f"✅ {name}({code}) 수동 매도 기록 DB 반영 완료 (+0.5% 익절)")
except Exception as e:
    print(f"❌ DB 기록 중 오류 발생: {e}")
finally:
    conn.close()
