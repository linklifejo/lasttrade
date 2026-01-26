import requests
import time
import os

print("🔍 Checking API Status Stability...")
last_mode = None
last_asset = None

for i in range(20):
    try:
        resp = requests.get('http://localhost:8080/api/status', timeout=1)
        data = resp.json()
        mode = data['summary']['api_mode']
        asset = data['summary']['total_asset']
        
        if last_mode and mode != last_mode:
            print(f"⚠️ FLIPPING DETECTED! {last_mode} -> {mode}")
        if last_asset and asset != last_asset:
             pass # 자산 변동은 있을 수 있음 (하지만 급격한 차이는 문제)

        print(f"[{i+1}] Mode: {mode}, Asset: {asset}")
        
        last_mode = mode
        last_asset = asset
    except Exception as e:
        print(f"[{i+1}] Error: {e}")
    
    time.sleep(0.5)
