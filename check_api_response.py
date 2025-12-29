"""
API 응답 데이터 확인
"""
import requests
import json

print("=" * 60)
print("API 응답 데이터 확인")
print("=" * 60)

try:
    r = requests.get('http://localhost:8080/api/status')
    data = r.json()
    
    if 'holdings' in data and len(data['holdings']) > 0:
        print(f"\n총 {len(data['holdings'])}개 종목")
        print("\n첫 번째 종목 데이터:")
        print("-" * 60)
        
        first = data['holdings'][0]
        for key, value in first.items():
            print(f"  {key}: {value} (type: {type(value).__name__})")
        
        print("\n" + "=" * 60)
        print("수익률 계산 검증:")
        print("-" * 60)
        
        avg_prc = first.get('avg_prc', 0)
        cur_prc = first.get('cur_prc', 0)
        qty = first.get('qty', 0)
        pl_rt = first.get('pl_rt', '0')
        
        print(f"평균단가: {avg_prc:,}원")
        print(f"현재가: {cur_prc:,}원")
        print(f"수량: {qty:,}주")
        print(f"서버 수익률: {pl_rt}%")
        
        if avg_prc > 0:
            pur_amt = avg_prc * qty
            evlt_amt = cur_prc * qty
            pl_amt = evlt_amt - pur_amt
            calc_rate = (pl_amt / pur_amt * 100) if pur_amt > 0 else 0
            
            print(f"\n재계산 수익률: {calc_rate:.2f}%")
            print(f"차이: {abs(float(pl_rt) - calc_rate):.4f}%")
    else:
        print("보유 종목 없음")
        
except Exception as e:
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
