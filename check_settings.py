"""
현재 설정 확인
"""
from database_helpers import get_setting

print("=" * 60)
print("현재 설정 확인")
print("=" * 60)

target_stock_count = get_setting('target_stock_count', 5)
print(f"\n목표 종목 수: {target_stock_count}개")

print("\n" + "=" * 60)
