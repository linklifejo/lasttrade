from analyze_tools import get_technical_indicators
from logger import logger

class TechnicalJudge:
    """키움 검색식에서 올라온 종목의 '성향'을 분석하여 최종 판단을 내리는 보조 판독기"""
    
    @staticmethod
    def get_weight(key, default):
        """DB에서 학습된 가중치 로드"""
        try:
            from database import get_db_connection
            with get_db_connection() as conn:
                res = conn.execute("SELECT value FROM learned_weights WHERE key = ?", (key,)).fetchone()
                return res[0] if res else default
        except:
            return default

    @staticmethod
    def judge_buy(code):
        """매수 적합성 판독"""
        indicators = get_technical_indicators(code, '1m')
        if not indicators:
            return True, "데이터 부족으로 기본 통과" # 데이터가 아직 안 쌓였으면 일단 통과
            
        score = 0
        reasons = []
        
        # 2. 이격도 체크 (단기 과열 여부)
        disp5 = indicators['disparity_5']
        if disp5 > 105: # MA5보다 5% 이상 높으면 추격 매수 위험
            score -= 20
            reasons.append(f"단기 과열(MA5 이격 {disp5:.1f}%)")
        elif disp5 < 98: # 눌림목 가능성
            score += 15
            reasons.append(f"눌림목 구간(MA5 이격 {disp5:.1f}%)")
            
        # 3. 추세 체크
        if indicators['trend'] == "UP":
            score += 15
            reasons.append("정배열 추세")
        else:
            score -= 10
            reasons.append("역배열/하락 추세")
            
        # 최종 결정
        threshold = 20 # 20점 이상이면 매수 승인
        passed = score >= threshold
        
        status_msg = f"점수: {score} | 사유: {', '.join(reasons)}"
        logger.info(f"⚖️ [Technical Judge] {code} 판독 결과 -> {'✅ 승인' if passed else '❌ 거절'} ({status_msg})")
        
        return passed, status_msg

technical_judge = TechnicalJudge()
