import sqlite3

# 가마우지 원본 키
original_paper_key = "NvakSJnJlaAvppzWP16MT2VcaXgzPK6UIvm9j_1DH_Y"
original_paper_secret = "Hq3xyuICuP95_W0m7VO2NmqiZDz5e5WghWi3p9ZfM7Y"

# DB 업데이트
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

cursor.execute("UPDATE settings SET value = ? WHERE key = 'paper_app_key'", (original_paper_key,))
cursor.execute("UPDATE settings SET value = ? WHERE key = 'paper_app_secret'", (original_paper_secret,))

conn.commit()
conn.close()

print("✅ 가마우지 원본 Paper API 키로 업데이트 완료!")
print(f"paper_app_key    : {original_paper_key}")
print(f"paper_app_secret : {original_paper_secret[:20]}...")
