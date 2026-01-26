import requests
import sqlite3
import datetime
import time
import json
import sys
import os
import config

# [설정] DB 파일 경로
DB_FILE = "c:/lasttrade/deep_learning.db"

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv_1m (
            code TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            open INTEGER,
            high INTEGER,
            low INTEGER,
            close INTEGER,
            volume INTEGER,
            PRIMARY KEY (code, timestamp)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_time ON ohlcv_1m (timestamp)")
    conn.commit()
    conn.close()

def get_token():
    try:
        url = f"{config.host_url}/oauth2/token"
        headers = {'Content-Type': 'application/json;charset=UTF-8'}
        data = {
            'grant_type': 'client_credentials',
            'appkey': config.app_key,
            'secretkey': config.app_secret,
        }
        res = requests.post(url, headers=headers, json=data, timeout=10)
        return res.json().get('access_token') or res.json().get('token')
    except:
        return None

def get_all_stocks():
    stocks = []
    try:
        conn = sqlite3.connect("c:/lasttrade/trading.db")
        cur = conn.cursor()
        # 모든 종목 가져오기
        cur.execute("SELECT code, name FROM mock_stocks")
        rows = cur.fetchall()
        for r in rows:
            stocks.append({'code': r[0], 'name': r[1]})
        conn.close()
    except Exception as e:
        print(f"⚠️ 타겟 추출 실패: {e}")
    return stocks

def fetch_vi_kiwoom(code, token):
    url = f"{config.host_url}/api/dostk/chart"
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'api-id': 'ka10080',
    }
    params = {
        'stk_cd': code,
        'tic_scope': '1',
        'upd_stkpc_tp': '1',
    }

    try:
        res = requests.post(url, headers=headers, json=params, timeout=10)
        if res.status_code != 200: return []
        data = res.json()
        raw_data = data.get('stk_min_pole_chart_qry', [])
        if not raw_data: raw_data = data.get('output', [])
        rows = []
        for item in raw_data:
            ts = item.get('cntr_tm', '')[:12]
            if not ts: continue
            o = abs(int(float(item.get('open_pric', 0))))
            h = abs(int(float(item.get('high_pric', 0))))
            l = abs(int(float(item.get('low_pric', 0))))
            c = abs(int(float(item.get('cur_prc', 0))))
            v = abs(int(float(item.get('trde_qty', 0))))
            if o > 0:
                rows.append((code, ts, o, h, l, c, v))
        return rows
    except:
        return []

def save_to_db(rows):
    if not rows: return 0
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executemany("INSERT OR IGNORE INTO ohlcv_1m VALUES (?,?,?,?,?,?,?)", rows)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()

def main():
    init_db()
    print("🚀 [Full Fetcher] 전 종목(2600+) 데이터 수집 및 학습 준비 시작")
    token = get_token()
    if not token:
        print("❌ 토큰 발급 실패")
        return

    stocks = get_all_stocks()
    print(f"📊 대상 종목: {len(stocks)}개")
    
    total_saved = 0
    start_time = time.time()
    
    for idx, s in enumerate(stocks):
        code = s['code']
        name = s['name']
        
        rows = fetch_vi_kiwoom(code, token)
        saved = save_to_db(rows)
        total_saved += saved
        
        if (idx + 1) % 10 == 0 or idx == len(stocks) - 1:
            elapsed = time.time() - start_time
            print(f"   [{idx+1}/{len(stocks)}] {name}({code}): {len(rows)}개 수신 (누적 신규저장: {total_saved}) | 시간: {elapsed:.1f}s")
        
        # API 호흡 조절
        time.sleep(0.05)
        
        # 토큰 갱신 (1시간마다)
        if int(time.time() - start_time) % 3600 == 0 and idx > 0:
            token = get_token()

    print(f"\n✅ 수집 완료: 총 {total_saved}개 신규 데이터 확보")
    print("🧠 이제 AI 학습을 시작합니다...")

if __name__ == "__main__":
    main()
