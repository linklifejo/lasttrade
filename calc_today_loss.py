import sqlite3
import datetime

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

today = datetime.date.today().strftime('%Y-%m-%d')
print(f"=== {today} 손절(Loss Cut) 내역 집계 ===\n")

# 손실 매도만 조회 (수익률 < 0 또는 사유에 '손절' 포함)
cursor.execute("""
    SELECT timestamp, name, qty, amt, profit_rate, reason 
    FROM trades 
    WHERE type='sell' 
      AND timestamp LIKE ? 
      AND mode='REAL' 
      AND (profit_rate < 0 OR reason LIKE '%손절%')
    ORDER BY timestamp
""", (f"{today}%",))

rows = cursor.fetchall()
total_loss_sell_amt = 0
total_loss_amt = 0 # 실제 손실액(추정)

print(f"총 {len(rows)}건의 손절이 감지되었습니다.\n")

for row in rows:
    ts, name, qty, amt, profit_rate, reason = row
    ts_time = ts.split(' ')[1]
    
    # 손실액 역산 (매도금액 / (1 + 수익률/100) = 매입원금)
    # 매도금액 - 매입원금 = 손실액
    try:
        p1 = 1 + (profit_rate / 100.0)
        principal = amt / p1
        loss = amt - principal
    except:
        loss = 0
        
    total_loss_sell_amt += amt
    total_loss_amt += loss
    
    print(f"- {ts_time} | {name} {qty}주 | 매도액 {amt:,.0f}원 | {profit_rate}% ({loss:,.0f}원) | {reason}")

print(f"\n📉 손절 매도 총액: {total_loss_sell_amt:,.0f}원")
print(f"💸 확정 손실 금액: {total_loss_amt:,.0f}원")

conn.close()
