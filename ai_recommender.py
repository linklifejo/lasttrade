import time
import threading
import random
from logger import logger
import config # [Queue Access]

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
        self.model_name = "PatternMatch_v1"

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
        while self.running:
            try:
                logger.info("🤖 [AI Recommender] 스캔 시작...")
                # 1. 대상 종목 선정
                targets = ['032830', '005490', '012450', '005380', '000270'] 
                
                for code in targets:
                    if not self.running: break
                    
                    # 2. AI 분석 (Predict)
                    score, reason = self.predict(code)
                    
                    if score >= 10:
                        logger.info(f"🤖 [AI 추천] {code} 발굴! (점수:{score}) -> Queue 등록")
                        
                        # [Direct Queue] 콜백 실패 대비 직접 큐에 삽입
                        item = {'code': code, 'source': 'AI_Model', 'ai_score': score, 'ai_reason': reason}
                        config.ai_recommendation_queue.append(item)
                        
                        # callback도 호환성 유지 위해 호출
                        if self.callback:
                             try: self.callback(code, source='AI_Model', ai_score=score, ai_reason=reason)
                             except: pass
                        
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"AI 추천 루프 오류: {e}")
                time.sleep(5)

    def predict(self, code):
        """
        개별 종목에 대한 AI 예측 수행
        """
        try:
            # 기술적 지표 조회 (1분봉, 없으면 일봉 대체)
            indicators = get_technical_indicators(code, '1m')
            
            # [Data Validation] 데이터가 없으면 패스
            if not indicators: 
                return 0, "No Data"
            
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
            if score >= 60:
                return score, ", ".join(reasons)
            else:
                return score, "" # 탈락

        except Exception as e:
            logger.error(f"AI 분석 중 에러({code}): {e}")
            return 0, str(e)
