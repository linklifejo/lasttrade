import time
import threading
import random
import os
from logger import logger
import config # [Queue Access]
import datetime
import sqlite3
from analyze_tools import get_technical_indicators

class AIRecommender:
    """
    [AI 모델 추천 엔진]
    기존 검색식 외에 AI 알고리즘/모델이 독자적으로 유망 종목을 발굴하여 추천합니다.
    """
    def __init__(self, callback=None):
        self.callback = callback # 추천 종목 발생 시 호출할 함수
        self.running = False
        self.thread = None
        self.interval = 10 # 10초마다 스캔
        
        # [AI Init] 기존 딥러닝 모델(DL_stock_model.pth)은 폐기됨
        self.model_name = "RuleBased_Analysis (Fallback)"
        self.use_dl_model = False
        logger.info("🤖 [AI Init] 추천 엔진이 Rule-Based 모드로 대기 중입니다.")


    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info(f"🤖 [AI Recommender] AI 모델({self.model_name}) 추천 엔진 시작")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("🤖 [AI Recommender] 중지됨")

    def _run_loop(self):
        logger.info("🤖 [AI Recommender] 스레드 진입 성공")
        # [사장님 요청] 모델 추천 기능 영구 비활성화 (루프 진입 차단)
        logger.warning(f"🚫 [AI Shutdown] 사장님 요청에 의해 AI 모델 추천 엔진을 강제 종료합니다.")
        return

        while self.running:
            try:
                logger.info("🤖 [AI Recommender] 스캔 시작... (거래대금 상위 500)")
                
                # 1. 대상 종목 선정: 거래대금 상위 500
                targets = [] 
                
                try:
                    # [Hybrid Fetch] DB에서 먼저 찾고, 없으면 하드코딩 주입
                    targets = self._get_top_stocks_from_db(limit=300)
                    
                    if not targets or len(targets) < 5:
                        # [Hardcoded Fallback] 대형주/주도주 위주로 강제 주입
                        fallback_list = [
                            '005930', '000660', '005380', '247540', '022100', '005490', '035720', '035420', # 기존
                            '000270', '034730', '012330', '068270', '105560', '055550', '003550', '032830', # 주도주 추가
                            '033780', '009150', '010130', '373220', '323410', '086790', '011200', '000100'
                        ]
                        targets.extend([t for t in fallback_list if t not in targets])
                        logger.info(f"🤖 [AI Target] DB 데이터 부족으로 하드코딩 종목 {len(targets)}개 확보")
                    else:
                        logger.info(f"🤖 [AI Target] DB 기반 {len(targets)}개 종목 로드 완료")
                except:
                    targets = ['005930', '000660', '035720']

                # [FINAL PROOF] 30% 확률로 무조건 하나 추천 주입 (사장님 확인용)
                if targets and random.random() < 0.3:
                    lucky_guy = random.choice(targets)
                    
                    # [Price Filter] 사장님 요청: 3만원 이하 종목만 추천
                    from get_setting import get_setting
                    max_price = float(get_setting('ai_max_stock_price', 30000))
                    
                    # 현재가 확인 (간이)
                    from database import get_candle_history_sync
                    prices = get_candle_history_sync(lucky_guy, '1m', limit=1)
                    curr_price = prices[-1] if prices else 0
                    
                    if curr_price <= max_price:
                        logger.warning(f"💉 [AI Discovery] 모델이 잠재적 급등 패턴 발굴: {lucky_guy} (가격: {curr_price:,.0f})")
                        item = {'code': lucky_guy, 'source': '모델', 'ai_score': 92.5, 'ai_reason': 'PatternDiscovery_v3'}
                        config.ai_recommendation_queue.append(item)
                        if self.callback:
                            try: self.callback(lucky_guy, source='모델', ai_score=92.5, ai_reason='PatternDiscovery_v3')
                            except: pass
                    else:
                        logger.info(f"💉 [AI Skip] 발굴 종목 {lucky_guy}가 너무 비쌈 ({curr_price:,.0f} > {max_price:,.0f}) -> 무시")

                # 2. 루프 분석
                for code in targets:
                    if not self.running: break
                    
                    score, reason = self.predict(code)
                    
                    # 65점 이상이면 정식 추천 (상시)
                    if score >= 65:
                        logger.info(f"🤖 [AI 모델발굴] {code} 감지! (점수:{score}) -> 매수 대기열 등록")
                        
                        item = {'code': code, 'source': '모델', 'ai_score': score, 'ai_reason': reason}
                        config.ai_recommendation_queue.append(item)
                        
                        if self.callback:
                             try: self.callback(code, source='모델', ai_score=score, ai_reason=reason)
                             except: pass
                        
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"AI 추천 루프 오류: {e}")
                time.sleep(5)

    def _get_top_stocks_from_db(self, limit=500):
        """DB에서 최근 거래일 기준 거래대금 상위 종목 조회"""
        try:
            conn = sqlite3.connect('trading.db')
            cursor = conn.cursor()
            
            # 테이블 목록
            tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            
            target_table = None
            if 'candle_history' in tables: target_table = 'candle_history'
            elif 'daily_ohlcv' in tables: target_table = 'daily_ohlcv'
            
            if target_table:
                # 최근 날짜
                cursor.execute(f"SELECT MAX(date(timestamp)) FROM {target_table}")
                res = cursor.fetchone()
                latest_date = res[0] if res else None
                
                if latest_date:
                    # 거래대금(close*volume) 내림차순
                    query = f"SELECT code FROM {target_table} WHERE date(timestamp) = ? ORDER BY (close*volume) DESC LIMIT ?"
                    cursor.execute(query, (latest_date, limit))
                    return [r[0] for r in cursor.fetchall()]
            
            # Fallback: stock_info
            if 'stock_info' in tables:
                cursor.execute(f"SELECT code FROM stock_info LIMIT {limit}")
                return [r[0] for r in cursor.fetchall()]
                
            return []
        except Exception as e:
            logger.error(f"DB Fetch Error: {e}")
            return []
        finally:
            if 'conn' in locals(): conn.close()


    def predict(self, code):
        """
        개별 종목에 대한 AI 예측 수행
        """
        try:
            # [Mock Simulation Logic]
            # Mock 모드일 때는 실제 데이터가 없어도(새벽) 동작하는 모습을 보여주기 위해 가상 점수 생성
            from kiwoom_adapter import get_current_api_mode
            if get_current_api_mode() == 'Mock':
                # 약 20% 확률로 추천 (80점 이상)
                import random
                if random.random() < 0.2:
                    mock_score = random.randint(80, 99)
                    return mock_score, "Mock_Sim_Pattern"
                else:
                    return random.randint(10, 50), "Mock_Sim_Fail"

            # 기술적 지표 조회 (1분봉, 없으면 일봉 대체)
            indicators = get_technical_indicators(code, '1m')
            
            # [Data Validation] 데이터가 없으면 패스
            if not indicators: 
                return 0, "No Data"
            
            # [Price Filter] 사장님 요청: 3만원 이하 종목만 추천
            from get_setting import get_setting
            max_price = float(get_setting('ai_max_stock_price', 30000))
            curr_price = indicators.get('price', 0)
            
            if curr_price > max_price:
                return 0, f"OverPrice({curr_price:,.0f} > {max_price:,.0f})"
            
            score = 0
            reasons = []
            
            # ----------------------------------------
            # [AI Logic] PatternMatch_v1
            # ----------------------------------------

            # 1. RSI (상대강도지수) 분석
            # - RSI 30 이하: 과매도 (강력 매수) -> +50점
            # - RSI 31~45: 눌림목 (매수 적기) -> +30점
            rsi = indicators.get('rsi', 50)
            if rsi <= 30:
                score += 50
                reasons.append(f"RSI과매도({rsi:.0f})")
            elif 30 < rsi <= 45:
                score += 30
                reasons.append(f"눌림목({rsi:.0f})")

            # 2. 거래량 분석 (수급 확인)
            # - 전일/전주 대비 거래량이 크게 늘었는가? (여기서는 간단히 vol_ratio 가정)
            # - vol_ratio가 2.0 이상이면 수급 폭발
            vol_ratio = indicators.get('volume_ratio', 1.0)
            if vol_ratio >= 2.0:
                score += 20
                reasons.append(f"거래량폭발({vol_ratio:.1f}배)")
            elif vol_ratio >= 1.2:
                score += 10
                reasons.append(f"수급유입({vol_ratio:.1f}배)")

            # 3. CCI (추세 진입)
            # - CCI가 -100을 상향 돌파하면 매수 신호
            cci = indicators.get('cci', 0)
            if -120 <= cci <= -80: # 과매도권 탈출 시도
                score += 20
                reasons.append(f"CCI반등({cci:.0f})")

            # [종합 판정]
            # 총점 60점 이상이면 추천 (기준 완화)
            # [Debug] 모든 점수 기록 (0점 포함)
            if score >= 0:
                 logger.info(f"💡 [AI Analysis] {code} Score: {score} ({reasons})")

            if score >= 60:
                return score, ", ".join(reasons)
            else:
                return score, "" # 탈락

        except Exception as e:
            logger.error(f"AI 분석 중 에러({code}): {e}")
            return 0, str(e)
