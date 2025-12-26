import sqlite3
import os

db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
conn = sqlite3.connect(db_file)
conn.execute("UPDATE settings SET value = 'false' WHERE key = 'use_mock_server'")
conn.execute("UPDATE settings SET value = 'REAL' WHERE key = 'trading_mode'")
conn.commit()
conn.close()

print("✅ REAL 모드로 변경 완료")
