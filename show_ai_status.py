import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print("=== AI 학습 시스템 현황 ===\n")

# 학습 데이터
tables = [
    ('signal_snapshots', '시그널 스냅샷 (매수/매도 시점 팩터)'),
    ('response_metrics', '대응 결과 (시그널 후 가격 변화)'),
    ('learned_weights', '학습된 가중치 (최적화 결과)'),
    ('sim_performance', '시뮬레이션 성과 기록')
]

for table, desc in tables:
    count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{desc}: {count}건")

# 학습된 가중치 상세
print("\n=== 현재 학습된 가중치 ===")
cursor.execute("SELECT key, value, updated_at FROM learned_weights ORDER BY updated_at DESC LIMIT 10")
weights = cursor.fetchall()
if weights:
    for key, value, updated_at in weights:
        print(f"  {key}: {value:.4f} (업데이트: {updated_at})")
else:
    print("  (아직 학습된 가중치 없음)")

conn.close()
