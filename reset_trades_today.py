import sqlite3
import datetime
db_path = r'c:\lasttrade\trading.db'
today_str = datetime.date.today().strftime('%Y-%m-%d')
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Delete today's trades to clear "Deep Count" memory
    cursor.execute("DELETE FROM trades WHERE timestamp LIKE ?", (f"{today_str}%",))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"✅ 오늘({today_str})의 매매 내역 {count}건을 초기화했습니다. (Deep Count 리셋 완료)")
except Exception as e:
    print(f"❌ 초기화 오류: {e}")
