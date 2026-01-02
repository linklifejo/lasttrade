from database import get_db_connection

conn = get_db_connection()
c = conn.cursor()
c.execute('SELECT key, value FROM settings')

print("=" * 60)
print("현재 설정 (Current Settings)")
print("=" * 60)

important_keys = [
    'split_buy_cnt',
    'single_stock_strategy', 
    'single_stock_rate',
    'stop_loss_rate',
    'take_profit_rate',
    'trading_capital_ratio',
    'target_stock_count',
    'time_cut_minutes',
    'use_trailing_stop',
    'trailing_stop_activation_rate',
    'trailing_stop_callback_rate'
]

settings = {}
for row in c.fetchall():
    settings[row[0]] = row[1]

for key in important_keys:
    if key in settings:
        value = settings[key]
        if key == 'split_buy_cnt':
            print(f"분할 매수 횟수: {value}회")
        elif key == 'single_stock_strategy':
            print(f"매수 전략: {value}")
        elif key == 'single_stock_rate':
            print(f"전략 기준 수익률: {value}%")
        elif key == 'stop_loss_rate':
            print(f"손절률: {value}%")
        elif key == 'take_profit_rate':
            print(f"익절률: {value}%")
        elif key == 'trading_capital_ratio':
            print(f"매매 자금 비율: {value}%")
        elif key == 'target_stock_count':
            print(f"목표 종목 수: {value}개")
        elif key == 'time_cut_minutes':
            print(f"타임컷 시간: {value}분")
        elif key == 'use_trailing_stop':
            print(f"트레일링 스탑 사용: {value}")
        elif key == 'trailing_stop_activation_rate':
            print(f"트레일링 스탑 활성화: {value}%")
        elif key == 'trailing_stop_callback_rate':
            print(f"트레일링 스탑 하락률: {value}%")

print("=" * 60)
conn.close()
