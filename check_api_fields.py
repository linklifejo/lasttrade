"""
키움 API 응답 필드 확인
"""
from kiwoom_adapter import get_account_data
import json

print("=" * 60)
print("키움 API 응답 필드 확인")
print("=" * 60)

holdings, summary = get_account_data()

if holdings and len(holdings) > 0:
    print(f"\n총 {len(holdings)}개 종목 보유 중")
    print("\n첫 번째 종목의 모든 필드:")
    print("-" * 60)
    first_stock = holdings[0]
    for key, value in first_stock.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("평균단가 관련 필드 찾기:")
    print("-" * 60)
    
    avg_price_fields = [k for k in first_stock.keys() if 'avg' in k.lower() or 'pric' in k.lower() or 'pchs' in k.lower()]
    if avg_price_fields:
        print("발견된 필드:")
        for field in avg_price_fields:
            print(f"  {field}: {first_stock.get(field)}")
    else:
        print("평균단가 관련 필드를 찾을 수 없습니다.")
        print("\n전체 필드 목록:")
        print(list(first_stock.keys()))
else:
    print("보유 종목이 없습니다.")

print("\n" + "=" * 60)
