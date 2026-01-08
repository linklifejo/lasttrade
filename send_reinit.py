import sqlite3
import datetime
import os

db_path = 'c:/lasttrade/trading.db'
conn = sqlite3.connect(db_path)
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
conn.execute("INSERT INTO web_commands (command, status, timestamp) VALUES (?, ?, ?)", ('reinit', 'pending', now))
conn.commit()
conn.close()
print("Reinit command successfully inserted.")
