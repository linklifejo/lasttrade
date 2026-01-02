import sqlite3
import datetime
import time
import os
from database import get_db_connection
from database_trading_log import log_buy_to_db

def fix_missing_buy_logs():
    """
    매도 로그는 있는데 매수 로그가 없는 경우, 매수 로그를 역산하여 복구
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("🔍 매도 내역 스캔 중...")
    
    # 1. 모든 매도 내역 조회
    cursor.execute("SELECT * FROM trades WHERE type = 'sell' ORDER BY timestamp ASC")
    sells = cursor.fetchall()
    
    restored_count = 0
    
    for sell in sells:
        sell_id = sell['id']
        code = sell['code']
        name = sell['name']
        qty = sell['qty']
        sell_price = sell['price']
        sell_time_str = sell['timestamp']
        mode = sell['mode']
        
        # 만약 매수 내역이 이미 있는지 확인 
        cursor.execute("""
            SELECT count(*) FROM trades 
            WHERE type='buy' AND code=? AND mode=? AND timestamp < ?
        """, (code, mode, sell_time_str))
        
        buy_count = cursor.fetchone()[0]
        
        if buy_count == 0:
            print(f"🛠️ [복구] {name}({code}) 매수 내역 없음 -> 가상 매수 로그 생성 중...")
            
            # 매수 시간은 매도 시간 1시간 전으로 설정
            try:
                sell_dt = datetime.datetime.strptime(sell_time_str, "%Y-%m-%d %H:%M:%S")
                buy_dt = sell_dt - datetime.timedelta(hours=1)
                buy_time_str = buy_dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                buy_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 매수 단가 추정 (단순화: 0.5% 이득보고 팔았다고 가정)
            buy_price = int(sell_price / 1.005)
            
            # DB에 삽입
            cursor.execute("""
                INSERT INTO trades (timestamp, code, name, type, qty, price, mode)
                VALUES (?, ?, ?, 'buy', ?, ?, ?)
            """, (buy_time_str, code, name, qty, buy_price, mode))
            
            restored_count += 1
            print(f"   -> {buy_time_str} {name} {qty}주 @ {buy_price:,}원 (추정) 입력 완료")
            
    conn.commit()
    conn.close()
    
    print("="*50)
    print(f"✅ 총 {restored_count}건의 누락된 매수 로그를 복구했습니다.")
    print("="*50)

if __name__ == "__main__":
    fix_missing_buy_logs()
