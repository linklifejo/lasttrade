
import requests
import json

try:
    print("📡 웹 서버(API)에 설정값 요청 중... (http://localhost:8080/api/settings)")
    response = requests.get('http://localhost:8080/api/settings', timeout=5)
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ [API 응답 성공] 웹 서버가 보내주는 실제 데이터:")
        print("=" * 60)
        
        # 주요 팩터 확인
        keys_to_check = {
            'stop_loss_rate': '개별 손절률',
            'sl_rate': '개별 손절률(백업)',
            'trading_mode': '거래 모드',
            'target_stock_count': '목표 종목 수',
            'take_profit_rate': '익절 수익률',
            'split_buy_cnt': '분할 매수 횟수',
            'single_stock_strategy': '전략',
            'real_app_key': '실전 앱키',
            'real_app_secret': '실전 시크릿',
            'paper_app_key': '모의 앱키',
            'paper_app_secret': '모의 시크릿'
        }
        
        for key, label in keys_to_check.items():
            val = data.get(key, '❌ 없음')
            print(f"  - {label} ({key}): {val}")
            
        print("=" * 60)
        
        if str(data.get('stop_loss_rate')) == '-1.0':
             print("🎉 결론: 웹 서버는 정확히 '-1.0'을 보내고 있습니다.")
        else:
             print(f"⚠️ 경고: 웹 서버가 엉뚱한 값({data.get('stop_loss_rate')})을 보내고 있습니다!")
             
    else:
        print(f"❌ API 요청 실패: Status {response.status_code}")

except Exception as e:
    print(f"❌ 연결 실패: {e}")
    print("  (웹 서버가 켜져 있는지 확인해주세요)")
