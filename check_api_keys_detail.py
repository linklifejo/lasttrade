import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# Real API 키 조회
cursor.execute("SELECT value FROM settings WHERE key = 'real_app_key'")
real_key = cursor.fetchone()[0]
cursor.execute("SELECT value FROM settings WHERE key = 'real_app_secret'")
real_secret = cursor.fetchone()[0]

conn.close()

print("=" * 60)
print("DB에 저장된 실전 API 키 확인")
print("=" * 60)
print()
print(f"real_app_key:")
print(f"  전체: {real_key}")
print(f"  길이: {len(real_key)}")
print(f"  앞 10자: {real_key[:10]}")
print(f"  뒤 10자: {real_key[-10:]}")
print(f"  공백 포함: {' ' in real_key}")
has_newline = '\n' in real_key or '\r' in real_key
print(f"  줄바꿈 포함: {has_newline}")
print()
print(f"real_app_secret:")
print(f"  전체: {real_secret}")
print(f"  길이: {len(real_secret)}")
print(f"  앞 10자: {real_secret[:10]}")
print(f"  뒤 10자: {real_secret[-10:]}")
print(f"  공백 포함: {' ' in real_secret}")
has_newline2 = '\n' in real_secret or '\r' in real_secret
print(f"  줄바꿈 포함: {has_newline2}")
print()
print("=" * 60)
print("키움증권에서 발급받은 키와 정확히 일치하는지 확인하세요!")
print("=" * 60)
