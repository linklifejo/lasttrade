"""
실시간 콘솔 모니터링 스크립트
웹 대시보드 대신 터미널에서 직접 확인
"""
import json
import time
import os
from datetime import datetime

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def format_number(num):
    return f"{int(num):,}"

def monitor():
    while True:
        try:
            clear_screen()
            
            # 현재 시간
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("=" * 80)
            print(f"🚀 Kiwoom Trading Bot Monitor - {now}")
            print("=" * 80)
            
            # status.json 읽기
            with open('status.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            summary = data.get('summary', {})
            holdings = data.get('holdings', [])
            
            # 요약 정보
            print(f"\n💰 총 자산: {format_number(summary.get('total_asset', 0))} 원")
            print(f"💳 총 매입: {format_number(summary.get('total_buy', 0))} 원")
            print(f"💵 예수금: {format_number(summary.get('deposit', 0))} 원")
            
            pl = summary.get('total_pl', 0)
            pl_sign = '+' if pl >= 0 else ''
            print(f"📈 총 손익: {pl_sign}{format_number(pl)} 원")
            
            yld = summary.get('total_yield', 0)
            yld_sign = '+' if yld >= 0 else ''
            print(f"📊 수익률: {yld_sign}{yld:.2f}%")
            
            bot_status = "🟢 실행중" if summary.get('bot_running') else "🔴 정지"
            print(f"🤖 봇 상태: {bot_status}")
            
            # 보유 종목
            print(f"\n{'=' * 80}")
            print("📊 현재 보유 종목")
            print(f"{'=' * 80}")
            
            if holdings:
                print(f"{'종목명':<15} {'수익률':>8} {'평가손익':>12} {'수량':>6} {'현재가':>10} {'시간':>6} {'단계':>8}")
                print("-" * 80)
                
                for h in holdings:
                    name = h.get('stk_nm', 'Unknown')[:15]
                    pl_rt = float(h.get('pl_rt', 0))
                    pl_amt = int(h.get('pl_amt', 0))
                    qty = h.get('rmnd_qty', 0)
                    cur_prc = int(h.get('cur_prc', 0))
                    hold_time = h.get('hold_time', '0분')
                    step = h.get('watering_step', '-')
                    
                    pl_sign = '+' if pl_rt >= 0 else ''
                    pl_color = '🔴' if pl_rt >= 0 else '🔵'
                    
                    print(f"{name:<15} {pl_color}{pl_sign}{pl_rt:>6.2f}% {pl_sign}{format_number(pl_amt):>12} {qty:>6} {format_number(cur_prc):>10} {hold_time:>6} {step:>8}")
            else:
                print("보유 종목이 없습니다.")
            
            # 최근 거래 내역
            print(f"\n{'=' * 80}")
            print("📝 최근 거래 내역 (최근 5건)")
            print(f"{'=' * 80}")
            
            try:
                with open('trading_log.json', 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                
                buys = log_data.get('buys', [])[-5:]
                sells = log_data.get('sells', [])[-5:]
                
                all_trades = []
                for b in buys:
                    all_trades.append(('매수', b))
                for s in sells:
                    all_trades.append(('매도', s))
                
                all_trades.sort(key=lambda x: x[1].get('time', ''), reverse=True)
                all_trades = all_trades[:5]
                
                if all_trades:
                    print(f"{'시간':<20} {'구분':<6} {'종목명':<15} {'수량':>6} {'가격':>10}")
                    print("-" * 80)
                    
                    for trade_type, trade in all_trades:
                        time_str = trade.get('time', '')[:19]
                        name = trade.get('name', 'Unknown')[:15]
                        qty = trade.get('qty', 0)
                        price = int(trade.get('price', 0))
                        
                        type_emoji = '🟢' if trade_type == '매수' else '🔴'
                        print(f"{time_str:<20} {type_emoji}{trade_type:<6} {name:<15} {qty:>6} {format_number(price):>10}")
                else:
                    print("거래 내역이 없습니다.")
            except:
                print("거래 내역을 불러올 수 없습니다.")
            
            print(f"\n{'=' * 80}")
            print("Press Ctrl+C to exit | 3초마다 자동 갱신")
            print(f"{'=' * 80}")
            
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\n\n모니터링을 종료합니다.")
            break
        except Exception as e:
            print(f"\n오류 발생: {e}")
            time.sleep(3)

if __name__ == '__main__':
    monitor()
