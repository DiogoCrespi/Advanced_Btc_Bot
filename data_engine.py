import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time

class DataEngine:
    def __init__(self, symbol="BTC-USD", secondary_symbol="ETH-USD", period="720d", interval="1h"):
        self.symbol = symbol
        self.secondary_symbol = secondary_symbol
        self.period = period
        self.interval = interval
        self.funding_url = "https://fapi.binance.com/fapi/v1/fundingRate"

    def fetch_data(self):
        """
        Fetches historical data for the main and secondary symbols.
        Using yfinance for robust 5-year historical daily data.
        """
        print(f"Fetching data for {self.symbol} and {self.secondary_symbol}...")
        df_main = yf.download(self.symbol, period=self.period, interval=self.interval, progress=False)
        df_sec = yf.download(self.secondary_symbol, period=self.period, interval=self.interval, progress=False)
        
        # Handle MultiIndex columns if present
        if isinstance(df_main.columns, pd.MultiIndex):
            df_main.columns = df_main.columns.droplevel(1)
        if isinstance(df_sec.columns, pd.MultiIndex):
            df_sec.columns = df_sec.columns.droplevel(1)
            
        df_main.dropna(inplace=True)
        df_sec.dropna(inplace=True)
        
        # Align dataframes
        combined = pd.concat([df_main, df_sec], axis=1, keys=['main', 'sec'], join='inner')
        df_main = combined['main']
        df_sec = combined['sec']
        
        return df_main, df_sec

    def fetch_funding_history(self, symbol="BTCUSDT", startTime=None, limit=1000):
        """
        Busca o histórico de Funding Rates da Binance Futures de forma paginada para obter mais dados.
        """
        all_funding = []
        current_start = startTime
        
        # Binance permite buscar blocos de 1000. Vamos tentar buscar até 5 blocos (5000 records ~ 4.5 anos)
        for _ in range(5):
            print(f"Fetching funding batch for {symbol} (start: {current_start})...")
            params = {"symbol": symbol, "limit": 1000}
            if current_start:
                params["startTime"] = int(current_start)
                
            try:
                response = requests.get(self.funding_url, params=params)
                data = response.json()
                if not isinstance(data, list) or not data:
                    break
                    
                df_batch = pd.DataFrame(data)
                all_funding.append(df_batch)
                
                # O endpoint retorna do mais antigo para o mais novo? 
                # Se não passar startTime, ele retorna os últimos? 
                # Na verdade, se passar startTime ele retorna cronológico.
                # Para paginar: o próximo startTime é o tempo do último record + 1ms
                current_start = int(df_batch['fundingTime'].iloc[-1]) + 1
            except Exception as e:
                print(f"Exception fetching funding batch: {e}")
                break
        
        if not all_funding:
            return pd.DataFrame()
            
        df = pd.concat(all_funding).drop_duplicates('fundingTime')
        df['fundingTime'] = pd.to_datetime(df['fundingTime'], unit='ms')
        df['fundingTime'] = df['fundingTime'].dt.round('h')
        df['fundingRate'] = df['fundingRate'].astype(float)
        df.set_index('fundingTime', inplace=True)
        return df[['fundingRate']]

    def apply_indicators(self, df):
        """
        Calculates log returns and mandatory technical indicators.
        """
        # Log Returns: r_t = ln(P_t / P_{t-1})
        df['Log_Returns'] = np.log(df['Close'] / df['Close'].shift(1))
        
        # Moving Averages
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        # RSI (Relative Strength Index)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))
        
        # MACD (Moving Average Convergence Divergence)
        ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_12 - ema_26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # ATR (Average True Range)
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['ATR_14'] = true_range.rolling(window=14).mean()
        
        return df

    def check_smt_divergence(self, df_main, df_sec):
        """
        Implements SMT Divergence logic:
        If BTC makes a LL and ETH makes a HL, or vice-versa.
        """
        # simplified lookback for SMT
        df_main['SMT_Divergence'] = 0
        
        for i in range(1, len(df_main)):
            # Bullish SMT: Main makes Lower Low, Sec makes Higher Low
            if (df_main['Low'].iloc[i] < df_main['Low'].iloc[i-1]) and \
               (df_sec['Low'].iloc[i] > df_sec['Low'].iloc[i-1]):
                df_main.iloc[i, df_main.columns.get_loc('SMT_Divergence')] = 1
                
            # Bearish SMT: Main makes Higher High, Sec makes Lower High
            elif (df_main['High'].iloc[i] > df_main['High'].iloc[i-1]) and \
                 (df_sec['High'].iloc[i] < df_sec['High'].iloc[i-1]):
                df_main.iloc[i, df_main.columns.get_loc('SMT_Divergence')] = -1
        
        return df_main

if __name__ == "__main__":
    engine = DataEngine()
    btc, eth = engine.fetch_data()
    btc = engine.apply_indicators(btc)
    btc = engine.check_smt_divergence(btc, eth)
    print(btc.tail())
