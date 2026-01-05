
import sqlite3
import os

DB_PATH = 'c:/lasttrade/trading.db'

def verify_all_settings_kr():
    if not os.path.exists(DB_PATH):
        print("❌ DB 파일을 찾을 수 없습니다.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 한글 매핑 테이블
    key_map = {
        'stop_loss_rate': '개별 종목 손절률',
        'sl_rate': '개별 종목 손절률(백업)',
        'start_loss_rate': '개별 종목 손절률(전략)',
        'global_loss_rate': '글로벌 자산 손절률',
        'take_profit_rate': '익절 수익률',
        'target_stock_count': '목표 종목 수',
        'single_stock_strategy': '매수 전략(WATER/FIRE)',
        'trading_mode': '거래 모드',
        'process_name': '프로세스 이름',
        'split_buy_cnt': '분할 매수 횟수',
        'min_purchase_amount': '최소 매수 금액',
        'time_cut_minutes': '타임컷 시간(분)',
        'time_cut_profit': '타임컷 수익률',
        'upper_limit_rate': '상한가 매도',
        'use_trailing_stop': '트레일링 스탑 사용',
        'trailing_stop_activation_rate': 'TS 발동 수익률',
        'trailing_stop_callback_rate': 'TS 하락 감지폭',
        'use_rsi_filter': 'RSI 필터 사용',
        'rsi_limit': 'RSI 제한값',
        'trading_capital_ratio': '투자 자금 비율',
        'target_profit_amt': '일일 목표 수익금',
        'liquidation_time': '자동 청산 시간'
    }

    print("\n📊 [DB 설정값 검증 리포트]")
    print("=" * 70)
    print(f"{'설정 항목 (한글)':<30} | {'현재값':<15} | {'DB 키값'}")
    print("-" * 70)
    
    try:
        cursor.execute("SELECT key, value FROM settings ORDER BY key")
        rows = cursor.fetchall()
        
        seen_keys = set()
        
        for row in rows:
            key = row['key']
            val = row['value']
            
            # API 키나 토큰은 너무 길어서 생략
            if 'token' in key or 'key' in key or 'secret' in key or 'account' in key:
                if 'app_key' not in key: # 앱키 제외하고 생략
                     continue

            # 한글 이름 찾기
            kr_name = key_map.get(key, key) # 없으면 영문 그대로
            
            # 중복 출력 방지 (sl_rate 등)
            if key == 'sl_rate': kr_name += " (내부용)"
            
            # 중요 항목 강조
            marker = ""
            if key in ['stop_loss_rate', 'take_profit_rate', 'target_stock_count', 'single_stock_strategy']:
                val = f"👉 {val}"
            
            print(f"{kr_name:<30} | {val:<15} | {key}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        
    print("=" * 70)
    conn.close()

if __name__ == "__main__":
    verify_all_settings_kr()
