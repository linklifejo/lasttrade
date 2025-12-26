import re
import os
import datetime

# 기본 로그 파일 경로 (설정에서 변경 가능하도록 하면 더 좋음)
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, 'logs', f'trading_{datetime.datetime.now().strftime("%Y%m%d")}.log')

def get_sold_logs(days_to_check=3):
    """
    최근 N일간의 로그 파일을 파싱하여 매도된 종목 리스트를 반환합니다.
    (기본값: 최근 3일)
    """
    sold_stocks = []
    seen_entries = set() # 중복 제거용 (시간+종목명+수량)

    # 오늘부터 과거로 N일 조회
    today = datetime.datetime.now()
    
    # 사유 감지용 맵 (전역적으로 유지)
    last_reason_map = {}
    
    # 날짜별 조회 (과거 -> 현재 순으로 처리하여 last_reason_map 히스토리 유지)
    target_dates = []
    for i in range(days_to_check - 1, -1, -1):
        target_date = today - datetime.timedelta(days=i)
        target_dates.append(target_date)

    # 로그 패턴 정규식
    # 2025-12-18 11:28:44 - trading_bot - INFO - 🔵 엔젯 13주 손절 완료 (수익율: -2.35%)
    sell_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*INFO - [🔵🔴] (.*?) (\d+)주 (.*?) 완료 \(수익율: (.*?)%\)')
    
    # 사유 감지용 정규식
    time_cut_pattern = re.compile(r'\[Time-Cut\] (.*?):')
    sl_pattern = re.compile(r'\[손절 진행\] (.*?):')
    ts_pattern = re.compile(r'\[트레일링 스탑 발동\] (.*?):')

    for date_obj in target_dates:
        date_str = date_obj.strftime("%Y%m%d")
        
        # 파일 목록 수집 (기본 로그 + 로테이션 로그)
        # 예: trading_20251220.log, trading_20251220.log.1, ...
        # 로테이션 파일은 .1 이 가장 최신일 수도 있고 아닐 수도 있음 (RotatingFileHandler 동작에 따름)
        # 보통 .log 가 최신, .log.1 이 그 직전...
        # 시간 순서대로 파싱하는 것이 중요하므로, index가 큰 것부터 읽어야 함 (.log.5 -> .log.4 -> ... -> .log)
        
        candidates = []
        base_name = f'trading_{date_str}.log'
        
        # 로테이션 파일 찾기 (최대 10개 가정)
        for k in range(10, 0, -1):
            rotated_name = f"{base_name}.{k}"
            full_path = os.path.join(LOG_DIR, 'logs', rotated_name)
            if os.path.exists(full_path):
                candidates.append(full_path)
                
        # 기본 파일 (가장 최신)
        base_path = os.path.join(LOG_DIR, 'logs', base_name)
        if os.path.exists(base_path):
            candidates.append(base_path)
            
        # 파일 내용 읽기 및 파싱
        for file_path in candidates:
            content = _read_file_safe(file_path)
            if not content: continue
            
            lines = content.splitlines()
            
            for line in lines:
                line = line.strip()
                
                # 사유 업데이트
                tc_match = time_cut_pattern.search(line)
                if tc_match: last_reason_map[tc_match.group(1).strip()] = "TimeCut (지루함)"
                
                sl_match = sl_pattern.search(line)
                if sl_match: last_reason_map[sl_match.group(1).strip()] = "StopLoss (물타기 실패)"

                ts_match = ts_pattern.search(line)
                if ts_match: last_reason_map[ts_match.group(1).strip()] = "TrailingStop (추세추종)"

                # 매도 감지
                sell_match = sell_pattern.search(line)
                if sell_match:
                    time_str = sell_match.group(1)
                    stock_name = sell_match.group(2).strip()
                    qty = sell_match.group(3)
                    type_str = sell_match.group(4)
                    profit_rate = sell_match.group(5)
                    
                    # 중복 체크 키
                    unique_key = f"{time_str}_{stock_name}_{qty}"
                    if unique_key in seen_entries:
                        continue
                    seen_entries.add(unique_key)

                    if "익절" in type_str:
                        reason = "TakeProfit (익절)"
                    elif "상한가" in type_str:
                        reason = "UpperLimit (상한가)"
                    else:
                        reason = last_reason_map.get(stock_name, "StopLoss (일반 손절)")

                    sold_stocks.append({
                        "time": time_str,
                        "name": stock_name,
                        "qty": qty,
                        "profit_rate": profit_rate,
                        "reason": reason
                    })
                    
                    # 맵 정리 (해당 종목 사유 소모)
                    if stock_name in last_reason_map:
                        del last_reason_map[stock_name]

    # 시간 역순 정렬 (최신이 위로) - 이미 위에서 날짜 순으로 했으나 안전하게 재정렬
    sold_stocks.sort(key=lambda x: x['time'], reverse=True)
    return sold_stocks

def _read_file_safe(path):
    encodings = ['utf-8', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except: continue
    # Binary fallback
    try:
        with open(path, 'rb') as f:
            return f.read().decode('utf-8', errors='ignore')
    except:
        return None

if __name__ == "__main__":
    logs = get_sold_logs()
    print(f"# 📄 금일 매도 종목 보고서 (found {len(logs)})")
    print()
    if not logs:
        print("금일 매도된 종목이 없습니다.")
    else:
        print("| 시간 | 종목명 | 수량 | 수익률 | 매도 사유 |")
        print("|---|---|---|---|---|")
        for s in logs:
            print(f"| {s['time']} | {s['name']} | {s['qty']}주 | {s['profit_rate']}% | {s['reason']} |")
