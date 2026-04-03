import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from logic.xaut_logic import XAUTAnalyzer

class DataEngine:
    def __init__(self, symbol="BTC-USD", secondary_symbol="ETH-USD", period="720d", interval="1h"):
        self.symbol = symbol
        self.secondary_symbol = secondary_symbol
        self.period = period
        self.interval = interval
        self.funding_url = "https://fapi.binance.com/fapi/v1/fundingRate"
        self.dapi_url = "https://dapi.binance.com/dapi/v1"

    def fetch_delivery_klines(self, symbol, interval="1h", limit=1000):
        """
        Busca klines históricos de um contrato de entrega.
        """
        print(f"Fetching Delivery klines for {symbol}...")
        try:
            url = f"{self.dapi_url}/klines"
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            df = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'base_volume', 'count', 'taker_buy_volume',
                'taker_buy_base_volume', 'ignore'
            ])
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['close'] = df['close'].astype(float)
            df.set_index('open_time', inplace=True)
            return df[['close']]
        except Exception as e:
            print(f"Exception fetching delivery klines: {e}")
            return pd.DataFrame()

    def fetch_macro_data(self, period="30d"):
        """
        Fetches Macro indicators: S&P 500 (^GSPC) and DXY (DX-Y.NYB).
        Returns a dictionary with the % change of each.
        """
        print("Fetching Macro Data (S&P 500 & DXY)...")
        sp500_change = 0.0
        dxy_change = 0.0
        
        try:
            # Download with short timeout and no progress bar
            sp500 = yf.download("^GSPC", period=period, interval="1d", progress=False, timeout=5)
            dxy = yf.download("DX-Y.NYB", period=period, interval="1d", progress=False, timeout=5)
            
            # 1. Process S&P 500
            if not sp500.empty and len(sp500) >= 2:
                if isinstance(sp500.columns, pd.MultiIndex): sp500.columns = sp500.columns.droplevel(1)
                sp500_change = float(sp500['Close'].values[-1] / sp500['Close'].values[-2]) - 1
            
            # 2. Process DXY
            if not dxy.empty and len(dxy) >= 2:
                if isinstance(dxy.columns, pd.MultiIndex): dxy.columns = dxy.columns.droplevel(1)
                dxy_change = float(dxy['Close'].values[-1] / dxy['Close'].values[-2]) - 1

        except Exception as e:
            # Captura JSONDecodeError, Indexing errors, etc. sem travar o bot
            print(f"[DATA] Aviso Macro Data: Falha limitada no download (^GSPC/DXY): {e}")

        return {
            "sp500_change": float(sp500_change),
            "dxy_change": float(dxy_change)
        }

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
                response = requests.get(self.funding_url, params=params, timeout=10)
                data = response.json()
                if not isinstance(data, list) or not data:
                    break
                    
                df_batch = pd.DataFrame(data)
                all_funding.append(df_batch)
                
                # Para paginar: o próximo startTime é o tempo do último record + 1ms
                current_start = int(df_batch['fundingTime'].values[-1]) + 1
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

    def fetch_delivery_contracts(self, asset="BTC"):
        """
        Retorna todos os contratos de entrega (Quarterly) ativos para um ativo.
        """
        print(f"[DEBUG] Entrando em fetch_delivery_contracts para {asset}...")
        try:
            url = f"{self.dapi_url}/exchangeInfo"
            print(f"[DEBUG] Fazendo requests.get para {url}...")
            response = requests.get(url, timeout=10)
            print(f"[DEBUG] Resposta recebida. Status: {response.status_code}")
            data = response.json()
            symbols = data.get('symbols', [])
            
            # Filtrar contratos CURRENT QUARTER ou NEXT QUARTER
            # Geralmente possuem formato BTCUSD_210625
            quarterly_contracts = [
                s for s in symbols 
                if s['baseAsset'] == asset and s['contractType'] in ['CURRENT_QUARTER', 'NEXT_QUARTER']
            ]
            print(f"[DEBUG] Saindo de fetch_delivery_contracts. Encontrados: {len(quarterly_contracts)}")
            return quarterly_contracts
        except Exception as e:
            print(f"Exception fetching delivery contracts: {e}")
            return []

    def fetch_basis_data(self, spot_symbol="BTCUSDT", delivery_symbol="BTCUSD_250627"):
        """
        Calculates the differential (Basis) between Spot and Delivery Future.
        Supports BRL by converting spot to USD if necessary.
        """
        try:
            # 1. Spot Price
            spot_url = "https://api.binance.com/api/v3/ticker/price"
            spot_resp = requests.get(spot_url, params={"symbol": spot_symbol}, timeout=10)
            spot_data = spot_resp.json()
            if 'price' not in spot_data:
                print(f"Error fetching spot: {spot_data}")
                return None
            spot_price_raw = float(spot_data['price'])
            
            # 2. USDBRL Rate (if needed)
            usd_brl = 1.0
            if "BRL" in spot_symbol:
                # Fetch USDTBRL as a proxy for USDBRL on Binance
                fx_resp = requests.get(spot_url, params={"symbol": "USDTBRL"}, timeout=10)
                fx_data = fx_resp.json()
                if 'price' in fx_data:
                    usd_brl = float(fx_data['price'])
            
            # Normalize spot price to USD
            spot_price_usd = spot_price_raw / usd_brl
            
            # 3. Delivery Price
            delivery_url = f"{self.dapi_url}/ticker/bookTicker"
            delivery_resp = requests.get(delivery_url, params={"symbol": delivery_symbol}, timeout=10)
            delivery_data = delivery_resp.json()
            
            if isinstance(delivery_data, list):
                delivery_data = delivery_data[0]
                
            if 'bidPrice' not in delivery_data:
                print(f"Error fetching delivery: {delivery_data}")
                return None
                
            delivery_price_usd = float(delivery_data['bidPrice'])
            
            basis_usd = delivery_price_usd - spot_price_usd
            premium_pct = (delivery_price_usd / spot_price_usd) - 1
            
            return {
                'spot': spot_price_usd,
                'spot_raw': spot_price_raw,
                'future': delivery_price_usd,
                'basis': basis_usd,
                'premium_pct': premium_pct,
                'fx_rate': usd_brl,
                'currency': 'BRL' if 'BRL' in spot_symbol else 'USD'
            }
        except Exception as e:
            print(f"Exception fetching basis data: {e}")
            return None

    def fetch_binance_klines(self, symbol="BTCUSDT", interval="1h", limit=1000):
        """
        Fetches historical klines from Binance Spot API including Taker Volume.
        """
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        print(f"Fetching Binance Klines for {symbol}...")
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            df = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'count', 
                'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
            ])
            
            # Convert to numeric
            cols = ['open', 'high', 'low', 'close', 'volume', 'taker_buy_base_volume']
            df[cols] = df[cols].apply(pd.to_numeric)
            
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('open_time', inplace=True)
            
            # Calculate CVD (Cumulative Volume Delta)
            df['buy_vol'] = df['taker_buy_base_volume']
            df['sell_vol'] = df['volume'] - df['buy_vol']
            df['delta'] = df['buy_vol'] - df['sell_vol']
            df['CVD'] = df['delta'].cumsum()
            
            return df
        except Exception as e:
            print(f"Error fetching Binance Klines: {e}")
            return pd.DataFrame()

    def fetch_xaut_ratio(self, limit: int = 300) -> pd.DataFrame:
        """
        Busca o ratio XAUT/BTC (via par XAUTBTC na Binance Spot) e retorna
        um DataFrame com indicadores técnicos calculados pelo XAUTAnalyzer.

        Parâmetros
        ----------
        limit : número de velas horárias (default 300 = ~12,5 dias)

        Retorna
        -------
        DataFrame com OHLCV + features do ratio (ratio_rsi, bb_pct, etc.)
        ou DataFrame vazio em caso de falha.
        """
        df_raw = self.fetch_binance_klines("XAUTBTC", interval="1h", limit=limit)
        if df_raw.empty:
            print("[XAUT] Falha ao buscar XAUTBTC klines — DataFrame vazio.")
            return pd.DataFrame()

        try:
            analyzer = XAUTAnalyzer()
            df_features = analyzer.compute_ratio_features(df_raw)
            if df_features.empty:
                print("[XAUT] compute_ratio_features retornou vazio (dados insuficientes).")
                return pd.DataFrame()
            return df_features
        except Exception as e:
            print(f"[XAUT] Erro ao calcular features do ratio: {e}")
            return pd.DataFrame()

    def fetch_usdt_brl_data(self, limit: int = 300) -> pd.DataFrame:
        """
        Busca dados de USDTBRL e aplica indicadores técnicos.
        """
        df_raw = self.fetch_binance_klines("USDTBRL", interval="1h", limit=limit)
        if df_raw.empty:
            return pd.DataFrame()
        
        try:
            from logic.usdt_brl_logic import UsdtBrlLogic
            logic = UsdtBrlLogic()
            return logic.compute_features(df_raw)
        except Exception as e:
            print(f"[USDTBRL] Erro fetch_usdt_brl_data: {e}")
            return pd.DataFrame()

    def apply_indicators(self, df):
        """
        Calculates log returns and mandatory technical indicators.
        """
        # Close column case sensitive check
        close_col = 'close' if 'close' in df.columns else 'Close'
        high_col = 'high' if 'high' in df.columns else 'High'
        low_col = 'low' if 'low' in df.columns else 'Low'

        # Log Returns
        df['Log_Returns'] = np.log(df[close_col] / df[close_col].shift(1))
        
        # Moving Averages
        df['SMA_50'] = df[close_col].rolling(window=50).mean()
        df['EMA_21'] = df[close_col].ewm(span=21, adjust=False).mean()
        
        # RSI
        delta = df[close_col].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))
        
        return df

if __name__ == "__main__":
    engine = DataEngine()
    df = engine.fetch_binance_klines("BTCUSDT", interval="1h")
    df = engine.apply_indicators(df)
    print(df[['close', 'delta', 'CVD', 'RSI_14']].tail())
