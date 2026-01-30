
import os
import sqlite3
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import IterableDataset, DataLoader
from logger import logger
import math
import time

# [Safety Settings]
TARGET_RISE_RATE = 0.07  
WINDOW_SIZE = 60         
PREDICTION_HORIZON = 60  
BATCH_SIZE = 32
EPOCHS = 100
DB_PATH = "deep_learning.db"
MODEL_PATH = "DL_stock_model.pth"

# [모델 구조 유지 - Transformer]
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=5000):
        super(PositionalEncoding, self).__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0).transpose(0, 1)
        self.register_buffer('pe', pe)

    def forward(self, x):
        return x + self.pe[:x.size(0), :]

class HunterTransformer(nn.Module):
    def __init__(self, input_dim=5, d_model=64, nhead=4, num_layers=2, dim_feedforward=128, dropout=0.1):
        super(HunterTransformer, self).__init__()
        self.input_embedding = nn.Linear(input_dim, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layers = nn.TransformerEncoderLayer(d_model, nhead, dim_feedforward, dropout, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers)
        self.decoder = nn.Sequential(nn.Linear(d_model, 64), nn.ReLU(), nn.Linear(64, 1), nn.Sigmoid())
        self.d_model = d_model

    def forward(self, src):
        src = self.input_embedding(src) * math.sqrt(self.d_model)
        src = self.pos_encoder(src)
        output = self.transformer_encoder(src)
        output = output[:, -1, :] 
        return self.decoder(output)

# [Memory Safe Dataset] 스트리밍 방식
class StreamingStockDataset(IterableDataset):
    def __init__(self, db_path, table_name, window_size, horizon, target_rise, recent_days=1):
        self.db_path = db_path
        self.table_name = table_name
        self.window_size = window_size
        self.horizon = horizon
        self.target_rise = target_rise
        self.recent_days = recent_days # [New] 최근 며칠치 학습할지
        self.codes = self._get_codes()

    def _get_codes(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # [Optimization] 최근 데이터가 있는 종목만 조회하여 속도 향상
            # (sqlite의 date 함수 사용. 실행 환경의 로컬 타임존 이슈가 있을 수 있으니 여유있게)
            query = f"SELECT DISTINCT code FROM {self.table_name} WHERE timestamp >= date('now', '-{self.recent_days + 2} days')"
            cursor.execute(query)
            codes = [r[0] for r in cursor.fetchall()]
            conn.close()
            if not codes: 
                # 만약 최근 데이터가 없으면 혹시 모르니 전체 조회 (Fallback)
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(f"SELECT DISTINCT code FROM {self.table_name}")
                codes = [r[0] for r in cursor.fetchall()]
                conn.close()
            return codes
        except:
            return []

    def _process_code_data(self, code):
        """종목 하나씩 처리 (최근 데이터 위주)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. 데이터 조회 (메모리 부담 적음 - 종목 1개니까)
        # [Incremental Learning] 최근 N일 + 윈도우 확보용 버퍼(2일)
        query = f"SELECT * FROM {self.table_name} WHERE code = '{code}' AND timestamp >= date('now', '-{self.recent_days + 2} days') ORDER BY timestamp"
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # 숫자 파싱
            raw_data = []
            for r in rows:
                nums = [x for x in r if isinstance(x, (int, float))]
                if len(nums) >= 5: raw_data.append(nums[-5:])
            
            data = np.array(raw_data, dtype=np.float32)
            
            if len(data) < self.window_size + self.horizon:
                conn.close()
                return

            # 슬라이딩 윈도우 생성 & Yield
            for i in range(0, len(data) - (self.window_size + self.horizon), 1): # Stride 1 (꼼꼼하게)
                current_close = data[i + self.window_size - 1][3]
                future_window = data[i + self.window_size : i + self.window_size + self.horizon]
                future_high = np.max(future_window[:, 1])
                
                max_return = (future_high - current_close) / (current_close + 1e-8)
                is_skyrocket = 1.0 if max_return >= self.target_rise else 0.0

                # [Under-Sampling] 안 오른 데이터는 확률적으로 버림 (메모리/시간 절약)
                if is_skyrocket == 0.0:
                    if np.random.rand() > 0.05: continue # 95% Drop

                # 정규화
                window_data = data[i:i+self.window_size]
                base = window_data[0] + 1e-8
                norm_window = (window_data / base) - 1.0
                
                yield torch.tensor(norm_window, dtype=torch.float32), torch.tensor([is_skyrocket], dtype=torch.float32)

        except Exception as e:
            # logger.error(f"Error processing {code}: {e}")
            pass
        finally:
            conn.close()

    def __iter__(self):
        # 종목을 하나씩 순회하며 제너레이터 실행
        for code in self.codes:
            yield from self._process_code_data(code)

def get_table_name():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        for t in ['ohlcv_1m', 'data_1m', 'candles_1m', 'candles', 'candle_history']:
            if t in tables: return t
        return tables[0] if tables else None
    except: return None

def train():
    logger.info("🔥 [Safe Training] 메모리 안전 모드 시작 (Streaming)")
    table_name = get_table_name()
    if not table_name:
        logger.error("❌ 테이블 못 찾음")
        return

    # [Dataset & DataLoader]
    # num_workers=0 (DB 동시접속 충돌 방지 위해 싱글 프로세스 로딩 권장)
    dataset = StreamingStockDataset(DB_PATH, table_name, WINDOW_SIZE, PREDICTION_HORIZON, TARGET_RISE_RATE)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"💻 Device: {device}")

    model = HunterTransformer(input_dim=5).to(device)
    
    # [수정] 1. 기존 모델 로드 (이어서 학습)
    if os.path.exists(MODEL_PATH):
        try:
            # CPU/GPU 호환성 고려하여 map_location 사용
            model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
            logger.info(f"💾 기존 모델 로드 성공: {MODEL_PATH} (이어서 학습합니다)")
        except Exception as e:
            logger.warning(f"⚠️ 기존 모델 로드 실패 (새로 시작): {e}")

    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.0001)

    model.train()
    
    # [Epoch Loop]
    # IterableDataset은 len()이 없으므로, 데이터가 끝날 때까지 돕니다.
    for epoch in range(EPOCHS):
        total_loss = 0
        batch_count = 0
        start_time = time.time()
        
        for batch_X, batch_y in dataloader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            batch_count += 1
            
            # [Log] 너무 조용하면 불안하니까 100배치마다 생존신고
            if batch_count % 100 == 0:
                print(f"Epoch {epoch+1} | Batch {batch_count} | Loss: {loss.item():.4f}", end='\r')

        # 에포크 종료 후 중간 저장 (매우 중요 - 중간에 죽어도 살릴 수 있게)
        epoch_model_path = f"DL_model_epoch_{epoch+1}.pth"
        torch.save(model.state_dict(), epoch_model_path) # 체크포인트
        torch.save(model.state_dict(), MODEL_PATH)       # 메인 파일 갱신
        
        avg_loss = total_loss / (batch_count + 1e-8)
        elapsed = time.time() - start_time
        logger.info(f"✅ Epoch {epoch+1}/{EPOCHS} 완료 | Loss: {avg_loss:.4f} | Time: {elapsed:.1f}s")
        
    logger.info("🎉 모든 학습 정상 종료!")

if __name__ == "__main__":
    train()
