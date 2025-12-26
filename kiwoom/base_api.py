"""
키움 API 추상 기본 클래스

모든 키움 API 구현체가 따라야 하는 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional


class KiwoomAPI(ABC):
    """키움 API 추상 기본 클래스"""
    
    @abstractmethod
    def get_token(self) -> Optional[str]:
        """
        인증 토큰 발급
        
        Returns:
            str: 접근 토큰
        """
        pass
    
    @abstractmethod
    def get_balance(self, token: str) -> Tuple[int, int, int]:
        """
        예수금 상세 현황 조회
        
        Args:
            token: 인증 토큰
            
        Returns:
            tuple: (주문가능금액, 총평가금액, 예수금)
        """
        pass
    
    @abstractmethod
    def get_account_data(self, token: str) -> Tuple[List[Dict], Dict]:
        """
        계좌 평가 현황 조회
        
        Args:
            token: 인증 토큰
            
        Returns:
            tuple: (종목 리스트, 계좌 요약 데이터)
        """
        pass
    
    @abstractmethod
    def get_my_stocks(self, token: str, print_df: bool = False) -> List[Dict]:
        """
        보유 종목 조회 (보유수량 0인 종목 제외)
        
        Args:
            token: 인증 토큰
            print_df: 데이터프레임 출력 여부
            
        Returns:
            List[Dict]: 보유 종목 리스트
        """
        pass
    
    @abstractmethod
    def get_total_eval_amt(self, token: str) -> int:
        """
        보유 주식의 총 평가금액 계산
        
        Args:
            token: 인증 토큰
            
        Returns:
            int: 총 평가금액
        """
        pass
    
    @abstractmethod
    def buy_stock(self, stk_cd: str, ord_qty: str, ord_uv: str, token: str) -> Tuple[str, str]:
        """
        주식 매수 주문
        
        Args:
            stk_cd: 종목코드
            ord_qty: 주문수량
            ord_uv: 주문단가
            token: 인증 토큰
            
        Returns:
            tuple: (return_code, return_msg)
        """
        pass
    
    @abstractmethod
    def sell_stock(self, stk_cd: str, ord_qty: str, token: str) -> Tuple[str, str]:
        """
        주식 매도 주문 (시장가)
        
        Args:
            stk_cd: 종목코드
            ord_qty: 주문수량
            token: 인증 토큰
            
        Returns:
            tuple: (return_code, return_msg)
        """
        pass
    
    @abstractmethod
    def get_current_price(self, stk_cd: str, token: str) -> Optional[int]:
        """
        실시간 현재가 조회
        
        Args:
            stk_cd: 종목코드
            token: 인증 토큰
            
        Returns:
            int: 현재가 (조회 실패 시 None)
        """
        pass
