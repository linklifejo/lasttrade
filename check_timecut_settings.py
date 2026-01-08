import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print("=== 타임컷(Time-Cut) 설정 확인 ===\n")

# settings 테이블에서 관련 값 조회
keys = ['time_cut_minutes', 'time_cut_profit']
for key in keys:
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    val = row[0] if row else "설정없음 (기본값 사용)"
    
    if key == 'time_cut_minutes':
        if row: val = f"{val}분"
        else: val = "30분 (기본)"
        print(f"⏱️ 경과 시간 제한: {val}")
        
    elif key == 'time_cut_profit':
        if row: val = f"{val}%"
        else: val = "1.0% (기본)"
        print(f"💰 목표 수익률: {val}")

conn.close()
