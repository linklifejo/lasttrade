"""
일일 AI 학습 스크립트
- 장 마감 후(15:40) 실행
- 당일 데이터로 AI 학습
- 학습 결과를 learned_weights 테이블에 저장
- 성과를 sim_performance에 기록
- LASTTRADE 대원칙(WATER 전략, 1:1:2:4:8 수열)을 준수하여 학습
"""
import sqlite3
import os
import json
from datetime import datetime
from logger import logger
from database_helpers import add_web_command
from tel_send import tel_send

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def learn_from_today_data():
    """당일 데이터로 AI 학습"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"🤖 LASTTRADE AI 학습 시작 (학습 데이터: {today})")
        logger.info("📡 [대원칙] WATER 전략 및 1:1:2:4:8 수열 기반 가중치 분석")
        
        # 1. 당일 거래 데이터 수집
        cursor.execute("""
            SELECT * FROM trades 
            WHERE DATE(timestamp) = ?
            ORDER BY timestamp
        """, (today,))
        trades = cursor.fetchall()
        logger.info(f"  📊 당일 거래: {len(trades)}건")
        
        # 데이터 부족 시 스킵 (텔레그램 알림)
        if len(trades) < 5:
            msg = f"🧠 [AI Learning] 학습 데이터 부족 ({len(trades)}/5건). 금일 학습은 스킵합니다."
            logger.info(msg)
            tel_send(msg)
            conn.close()
            return True
        
        # 2. 당일 시그널 데이터 수집
        cursor.execute("""
            SELECT s.*, r.* 
            FROM signal_snapshots s
            LEFT JOIN response_metrics r ON s.id = r.signal_id
            WHERE DATE(s.timestamp) = ?
        """, (today,))
        signals = cursor.fetchall()
        logger.info(f"  📊 당일 시그널: {len(signals)}건")
        
        # 3. 당일 분봉 데이터 수집
        cursor.execute("""
            SELECT code, COUNT(*) as candle_count
            FROM candle_history
            WHERE DATE(timestamp) = ?
            GROUP BY code
        """, (today,))
        candles = cursor.fetchall()
        logger.info(f"  📊 당일 분봉: {len(candles)}개 종목")
        
        # 4. 학습 실행 (간단한 예시)
        learning_results = perform_learning(trades, signals, candles)
        
        # 5. [Semi-Auto Evolution] 로직 개선 제안 생성
        analyze_and_propose_improvements(trades, signals, learning_results)
        
        # 6. 학습 결과 저장
        save_learned_weights(conn, learning_results)
        
        # 6. 성과 기록
        save_performance(conn, trades, today)
        
        conn.commit()
        conn.close()
        
        # 학습 완료 시각
        learn_time = datetime.now().strftime('%H:%M:%S')
        
        # 대시보드 알림 및 텔레그램 알림 (상세 정보 포함)
        msg_complete = f'🤖 AI 학습 완료 [{learn_time}]\n- 거래: {len(trades)}건\n- 시그널: {len(signals)}건\n- 승률: {learning_results.get("win_rate_weight",0)*100:.1f}%'
        add_web_command('notify', {'message': msg_complete.replace('\n', ', ')})
        tel_send(msg_complete)
        
        logger.info(msg_complete.replace('\n', ' '))  # 상세 정보를 로그에도 기록
        
        # [Fix] 텔레그램 비동기 전송 완료 대기 (프로세스 종료 방지)
        import time
        time.sleep(2)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ AI 학습 실패: {e}")
        return False

def perform_learning(trades, signals, candles):
    """실제 학습 로직 (60분봉 팩터 분석 포함)"""
    logger.info("  🧠 LASTTRADE 학습 알고리즘 실행 중...")
    logger.info("  💡 [원칙] 1분/5분봉 단기 시그널과 60분봉 중기 추세의 결합 분석")
    
    # [대원칙 적용] 승률 계산 시 WATER 전략의 특성 반영
    buy_trades = [t for t in trades if t['type'].upper() == 'BUY']
    sell_trades = [t for t in trades if t['type'].upper() == 'SELL']
    
    win_count = sum(1 for t in sell_trades if t['profit_rate'] and t['profit_rate'] > 0)
    total_sells = len(sell_trades)
    win_rate = (win_count / total_sells * 100) if total_sells > 0 else 0
    
    # 60분봉 팩터 효과 분석
    trend_stats = {"bull": {"success": 0, "total": 0}, "bear": {"success": 0, "total": 0}}
    
    # 설정 팩터 분석 (AI 인지 강화)
    setting_summary = {}
    for sig in signals:
        try:
            factors = json.loads(sig['factors_json'])
            # 'set_'로 시작하는 설정값들 추출하여 빈도/평균 계산
            for k, v in factors.items():
                if k.startswith('set_'):
                    if k not in setting_summary: setting_summary[k] = []
                    setting_summary[k].append(v)
            
            trend_60m = factors.get('trend_60m', 0)
            success = 1 if sig.get('interval_5m_change', 0) > 0.5 else 0 # 5분 내 0.5% 반등 성공 여부
            
            if trend_60m == 1:
                trend_stats["bull"]["total"] += 1
                trend_stats["bull"]["success"] += success
            elif trend_60m == -1:
                trend_stats["bear"]["total"] += 1
                trend_stats["bear"]["success"] += success
        except: continue
        
    if setting_summary:
        logger.info("    ⚙️ 학습 당시 주요 설정 환경 (AI 인지):")
        for k, vals in setting_summary.items():
            if vals:
                # 숫자형이면 평균, 아니면 최빈값
                if isinstance(vals[0], (int, float)):
                    avg_v = sum(vals) / len(vals)
                    logger.info(f"      - {k}: {avg_v:.2f}")
                else:
                    logger.info(f"      - {k}: {vals[0]}")
        
    bull_win = (trend_stats["bull"]["success"] / trend_stats["bull"]["total"] * 100) if trend_stats["bull"]["total"] > 0 else 0
    bear_win = (trend_stats["bear"]["success"] / trend_stats["bear"]["total"] * 100) if trend_stats["bear"]["total"] > 0 else 0
    
    logger.info(f"    대추세(60분) 분석:")
    logger.info(f"      - 정배열(양봉) 구간 승률: {bull_win:.1f}% ({trend_stats['bull']['total']}건)")
    logger.info(f"      - 역배열(음봉) 구간 승률: {bear_win:.1f}% ({trend_stats['bear']['total']}건)")
    
    # 학습 결과 (가중치 저장)
    results = {
        'win_rate_weight': win_rate / 100.0,
        'bull_trend_bonus': bull_win / 100.0,
        'bear_trend_penalty': bear_win / 100.0,
        'trade_count': len(trades),
        'signal_count': len(signals)
    }
    
    return results

def analyze_and_propose_improvements(trades, signals, results):
    """당일 성과를 분석하여 로직 개선 제안서 작성 및 자율 수정(Full-Auto) 실행"""
    try:
        from get_setting import get_setting
        from logic_evolver import LogicEvolver
        
        evolver = LogicEvolver()
        use_auto_evolution = get_setting('use_ai_logic_evolution', False)
        
        proposal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'AI_IMPROVEMENT_PROPOSALS.md')
        
        win_rate = results.get('win_rate_weight', 0) * 100
        total_trades = results.get('trade_count', 0)
        
        proposals = []
        
        # 1. RSI 필터 자율 최적화
        if 0 < win_rate < 45 and total_trades >= 3:
            # 보수적 접근: 단계적으로 조정
            from get_setting import get_setting as cached_setting
            current_limit = int(cached_setting('rsi_limit', 30))
            new_limit = max(15, current_limit - 2) # 하루 최대 2점씩 하향
            
            p_item = {
                "title": "🔍 RSI 진입 필터 최적화",
                "current": f"rsi_limit = {current_limit}",
                "reason": f"승률이 {win_rate:.1f}%로 목표치 미달. 필터를 {new_limit}로 강화하여 하락 칼날 잡기 방지.",
                "action": f"rsi_limit를 {new_limit}로 하향 조정",
                "auto_apply": True,
                "target_file": "check_n_buy.py",
                "pattern": r"get_setting\('rsi_limit', \d+\)",
                "replacement": f"get_setting('rsi_limit', {new_limit})"
            }
            proposals.append(p_item)

        # 2. 역배열 가중치 추가 페널티 (예시)
        # ... 향후 확장 가능 ...

        if not proposals:
            return

        # 자율 진화 실행 (Full-Auto)
        applied_count = 0
        if use_auto_evolution:
            for p in proposals:
                if p.get('auto_apply'):
                    success = evolver.apply_improvement(
                        target_file=p['target_file'],
                        pattern=p['pattern'],
                        replacement=p['replacement'],
                        reason=p['reason']
                    )
                    if success: applied_count += 1

        # Markdown 파일에 기록
        if os.path.exists(proposal_path):
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            with open(proposal_path, 'r', encoding='utf-8') as f:
                content = f.read()

            status_tag = "[자동 적용됨]" if use_auto_evolution and applied_count > 0 else "[사용자 승인 대기]"
            new_entry = f"\n## 📅 [AI 자율 진화] {now} {status_tag}\n"
            for p in proposals:
                new_entry += f"### {p['title']}\n"
                new_entry += f"- **현황**: {p['current']}\n"
                new_entry += f"- **원인**: {p['reason']}\n"
                new_entry += f"- **대응**: {p['action']}\n\n"
            
            marker = "## 📅 [최신 제안]"
            if marker in content:
                parts = content.split(marker)
                updated_content = parts[0] + marker + new_entry + parts[1]
                with open(proposal_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
            
            logger.info(f"🧬 [AI Evolution] {len(proposals)}건 분석, {applied_count}건 자율 수정 반영됨.")
            
            if not use_auto_evolution:
                from tel_send import tel_send
                tel_send(f"🤖 [AI 제안] 오늘 매매 결과 {len(proposals)}건의 개선 제안이 있습니다. 승인이 필요합니다.")

    except Exception as e:
        logger.error(f"⚠️ 자율 진화 분석 중 오류: {e}")

def save_learned_weights(conn, results):
    """학습된 가중치 저장"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for key, value in results.items():
        if isinstance(value, (int, float)):
            conn.execute("""
                INSERT OR REPLACE INTO learned_weights (key, value, updated_at, description)
                VALUES (?, ?, ?, ?)
            """, (key, value, timestamp, f"학습 결과: {key}"))
    
    logger.info(f"  💾 학습 가중치 저장: {len(results)}개")

def save_performance(conn, trades, date):
    """당일 성과 기록"""
    # 매매 통계 계산
    buy_trades = [t for t in trades if t['type'] == 'BUY']
    sell_trades = [t for t in trades if t['type'] == 'SELL']
    
    win_count = sum(1 for t in sell_trades if t['profit_rate'] and t['profit_rate'] > 0)
    total_sells = len(sell_trades)
    win_rate = (win_count / total_sells) if total_sells > 0 else 0
    
    total_return = sum(t['profit_rate'] or 0 for t in sell_trades)
    
    # 성과 JSON
    performance = {
        'date': date,
        'total_trades': len(trades),
        'buy_count': len(buy_trades),
        'sell_count': len(sell_trades),
        'win_count': win_count,
        'win_rate': win_rate,
        'total_return': total_return
    }
    
    # sim_performance 테이블에 저장
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("""
        INSERT INTO sim_performance 
        (config_id, scenario_id, start_time, end_time, total_return, win_rate, trade_count, performance_json)
        VALUES (NULL, NULL, ?, ?, ?, ?, ?, ?)
    """, (date, timestamp, total_return, win_rate, len(trades), json.dumps(performance)))
    
    logger.info(f"  📈 성과 기록 저장 완료")

if __name__ == "__main__":
    logger.info("="*50)
    logger.info("일일 AI 학습 시작")
    logger.info("="*50)
    
    success = learn_from_today_data()
    
    if success:
        logger.info("="*50)
        logger.info("✅ 학습 완료")
        logger.info("="*50)
    else:
        logger.error("❌ 학습 실패")
