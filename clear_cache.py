"""
DB에서 오래된 system_status 캐시 삭제
"""
import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

print("=" * 60)
print("system_status 캐시 삭제")
print("=" * 60)

try:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 현재 저장된 데이터 확인
    cursor.execute("SELECT api_mode, updated_at FROM system_status")
    rows = cursor.fetchall()
    
    print(f"\n삭제 전: {len(rows)}개의 캐시 데이터")
    for row in rows:
        print(f"  - Mode: {row[0]}, Updated: {row[1]}")
    
    # 모든 캐시 삭제
    cursor.execute("DELETE FROM system_status")
    conn.commit()
    
    print(f"\n✅ 모든 캐시 데이터 삭제 완료!")
    print("봇이 다음 업데이트 시 새로운 데이터를 생성합니다.")
    
    conn.close()
    
except Exception as e:
    print(f"❌ 오류: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
