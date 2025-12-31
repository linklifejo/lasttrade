import sys
import os

# 디렉토리를 경로에 추가
sys.path.append(os.path.abspath('.'))

from kiwoom.mock_api import MockKiwoomAPI
from logger import logger

if __name__ == "__main__":
    print("Initializing Mock Data...")
    api = MockKiwoomAPI()
    print("Mock Data Initialized (mock_prices, mock_stocks, etc.)")
