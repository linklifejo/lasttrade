import sqlite3
import datetime
import json
db_path = r'c:\lasttrade\trading.db'
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO web_commands (command, params, status, timestamp)
        VALUES (?, ?, 'pending', ?)
    ''', ('reinit', None, timestamp))
    conn.commit()
    conn.close()
    print("✅ 'reinit' 명령을 봇 명령 대기열에 추가했습니다. 잠시 후 봇이 재로그인 및 초기화를 수행합니다.")
except Exception as e:
    print(f"❌ 명령 전송 오류: {e}")
