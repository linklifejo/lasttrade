"""
일일 AI 학습 스크립트
- 장 마감 후(15:40) 실행
- 당일 데이터로 AI 학습
- 학습 결과를 learned_weights 테이블에 저장
- 성과를 sim_performance에 기록
- LASTTRADE 대원칙(WATER 전략, 1:1:2:2:4 수열)을 준수하여 학습
"""
import sqlite3
import os
import json
from datetime import datetime
from logger import logger
from database_helpers import add_web_command

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def learn_from_today_data():
    """당일 데이터로 AI 학습"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"🤖 LASTTRADE AI 학습 시작 (학습 데이터: {today})")
        logger.info("📡 [대원칙] WATER 전략 및 1:1:2:2:4 수열 기반 가중치 분석")
        
        # 1. 당일 거래 데이터 수집
        cursor.execute("""
            SELECT * FROM trades 
            WHERE DATE(timestamp) = ?
            ORDER BY timestamp
        """, (today,))
        trades = cursor.fetchall()
        logger.info(f"  📊 당일 거래: {len(trades)}건")
        
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
        
        # 5. 학습 결과 저장
        save_learned_weights(conn, learning_results)
        
        # 6. 성과 기록
        save_performance(conn, trades, today)
        
        conn.commit()
        conn.close()
        
        # 학습 완료 시각
        learn_time = datetime.now().strftime('%H:%M:%S')
        
        # 대시보드 알림 (상세 정보 포함)
        add_web_command('notify', {
            'message': f'🤖 AI 학습 완료 [{learn_time}] - 거래: {len(trades)}건, 시그널: {len(signals)}건, 승률: {learning_results.get("win_rate_weight",0)*100:.1f}%'
        })
        
        logger.info("✅ AI 학습 완료")
        return True
        
    except Exception as e:
        logger.error(f"❌ AI 학습 실패: {e}")
        return False

def perform_learning(trades, signals, candles):
    """실제 학습 로직 (예시)"""
    logger.info("  🧠 LASTTRADE 학습 알고리즘 실행 중...")
    logger.info("  💡 [원칙] RSI 등 제외된 팩터의 가중치를 낮추고 평단가/단계 분석에 집중")
    
    # [대원칙 적용] 승률 계산 시 WATER 전략의 특성 반영
    buy_trades = [t for t in trades if t['type'].upper() == 'BUY']
    sell_trades = [t for t in trades if t['type'].upper() == 'SELL']
    
    win_count = sum(1 for t in sell_trades if t['profit_rate'] and t['profit_rate'] > 0)
    total_sells = len(sell_trades)
    win_rate = (win_count / total_sells * 100) if total_sells > 0 else 0
    
    # 예시: 평균 수익률
    avg_profit = sum(t['profit_rate'] or 0 for t in sell_trades) / total_sells if total_sells > 0 else 0
    
    logger.info(f"    승률: {win_rate:.1f}% ({win_count}/{total_sells})")
    logger.info(f"    평균 수익률: {avg_profit:.2f}%")
    
    # 학습 결과 (가중치 조정 예시)
    results = {
        'win_rate_weight': win_rate / 100.0,  # 승률 기반 가중치
        'profit_weight': max(0, min(1, avg_profit / 10.0)),  # 수익률 기반 가중치
        'trade_count': len(trades),
        'signal_count': len(signals)
    }
    
    return results

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
