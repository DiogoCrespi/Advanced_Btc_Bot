# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import yfinance as yf
import time
import pandas as pd
import numpy as np
import requests
from logic.xaut_logic import XAUTAnalyzer

class DataEngine:
    def __init__(self, symbol="BTC-USD", secondary_symbol="ETH-USD", period="720d", interval="1h"):
        self.symbol = symbol
        self.secondary_symbol = secondary_symbol
        self.period = period
        self.interval = interval
        self.funding_url = "https://fapi.binance.com/fapi/v1/fundingRate"
        self.dapi_url = "https://dapi.binance.com/dapi/v1"
        self._klines_cache = {}

    def fetch_delivery_klines(self, symbol, interval="1h", limit=1000):
        """
        Busca klines historicos de um contrato de entrega.
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
        Fetches Macro indicators: S&P 500 (^GSPC), DXY (DX-Y.NYB) and Gold (GC=F).
        Returns a dictionary with the % change of each.
        """
        print("Fetching Macro Data (S&P 500 & DXY)...")
        sp500_change = 0.0
        dxy_change = 0.0
        gold_change = 0.0
        
        try:
            # Fetch with Ticker.history for better robustness in single symbol downloads
            sp500_df = yf.Ticker("^GSPC").history(period=period, interval="1d")
            dxy_df = yf.Ticker("DX-Y.NYB").history(period=period, interval="1d")
            gold_df = yf.Ticker("GC=F").history(period=period, interval="1d")
            
            # 1. Process S&P 500
            if sp500_df is not None and not sp500_df.empty and len(sp500_df) >= 2:
                # history() handles MultiIndex differently, usually single symbol is standard columns
                close_col = 'Close' if 'Close' in sp500_df.columns else None
                if close_col:
                    sp500_change = float((sp500_df[close_col].values[-1] / sp500_df[close_col].values[-2]) - 1)
            
            # 2. Process DXY
            if dxy_df is not None and not dxy_df.empty and len(dxy_df) >= 2:
                close_col = 'Close' if 'Close' in dxy_df.columns else None
                if close_col:
                    dxy_change = float((dxy_df[close_col].values[-1] / dxy_df[close_col].values[-2]) - 1)
            
            # 3. Process Gold (GC=F)
            if gold_df is not None and not gold_df.empty and len(gold_df) >= 2:
                close_col = 'Close' if 'Close' in gold_df.columns else None
                if close_col:
                    gold_change = float((gold_df[close_col].values[-1] / gold_df[close_col].values[-2]) - 1)

        except Exception as e:
            # Captura JSONDecodeError, Indexing errors, etc. sem travar o bot
            print(f"[DATA] Aviso Macro Data: Falha limitada no download (^GSPC/DXY/GC=F): {e}")

        return {
            "sp500_change": float(sp500_change),
            "dxy_change": float(dxy_change),
            "gold_change": float(gold_change)
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
        Busca o historico de Funding Rates da Binance Futures de forma paginada para obter mais dados.
        """
        all_funding = []
        current_start = startTime
        
        # Binance permite buscar blocos de 1000. Vamos tentar buscar ate 5 blocos (5000 records ~ 4.5 anos)
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
                
                # Para paginar: o proximo startTime e o tempo do ultimo record + 1ms
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
        cache_key = f"{symbol}_{interval}_{limit}"
        now = time.time()
        if cache_key in self._klines_cache:
            cache_time, cached_df = self._klines_cache[cache_key]
            if now - cache_time < 15:
                # print(f"Using cached Binance Klines for {symbol}...")
                return cached_df.copy()

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
            
            self._klines_cache[cache_key] = (time.time(), df)
            return df.copy()
        except Exception as e:
            print(f"Error fetching Binance Klines: {e}")
            return pd.DataFrame()

    def fetch_xaut_ratio(self, limit: int = 300) -> pd.DataFrame:
        """
        Busca o ratio XAUT/BTC (via par XAUTBTC na Binance Spot) e retorna
        um DataFrame com indicadores tecnicos calculados pelo XAUTAnalyzer.

        Parametros
        ----------
        limit : numero de velas horarias (default 300 = ~12,5 dias)

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

    def fetch_forex_spread(self):
        """
        Calcula o Agio/Desagio Cambial (Spread) cruzando o Dolar Comercial puro (AwesomeAPI)
        contra o spot dolar implicito na Binance (BTCBRL / BTCUSDT).
        """
        try:
            aw_resp = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL", timeout=5)
            dolar_comercial = float(aw_resp.json()['USDBRL']['bid'])
            
            spot_url = "https://api.binance.com/api/v3/ticker/price"
            btc_brl_resp = requests.get(spot_url, params={"symbol": "BTCBRL"}, timeout=5).json()
            btc_usdt_resp = requests.get(spot_url, params={"symbol": "BTCUSDT"}, timeout=5).json()
            
            btc_brl = float(btc_brl_resp['price'])
            btc_usdt = float(btc_usdt_resp['price'])
            dolar_cripto = btc_brl / btc_usdt
            
            spread_pct = (dolar_cripto / dolar_comercial) - 1.0
            
            return {
                "dolar_comercial": dolar_comercial,
                "dolar_cripto": dolar_cripto,
                "agio_cambial_pct": spread_pct,
                "valido": True
            }
        except Exception as e:
            print(f"Aviso Forex Spread: {e}")
            return {
                "dolar_comercial": 0.0,
                "dolar_cripto": 0.0,
                "agio_cambial_pct": 0.0,
                "valido": False
            }

    def fetch_usdt_brl_data(self, limit: int = 300) -> pd.DataFrame:
        """
        Busca dados de USDTBRL e aplica indicadores tecnicos.
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

        # Base Features (Log Returns)
        df['feat_returns'] = np.log(df[close_col] / df[close_col].shift(1))

        def add_macd(dt, cl, f, s, sig, suf):
            ema_f = dt[cl].ewm(span=f, adjust=False).mean()
            ema_s = dt[cl].ewm(span=s, adjust=False).mean()
            macd = ema_f - ema_s
            sv = macd.ewm(span=sig, adjust=False).mean()
            dt[f'feat_macd{suf}'] = macd
            dt[f'feat_macd_h{suf}'] = macd - sv
            dt[f'feat_macd_s{suf}'] = sv

        def add_bb(dt, cl, l, std_val, suf):
            sma = dt[cl].rolling(window=l).mean()
            dev = dt[cl].rolling(window=l).std()
            u = sma + (dev * std_val)
            lw = sma - (dev * std_val)
            dt[f'feat_bb_u{suf}'] = u
            dt[f'feat_bb_m{suf}'] = sma
            dt[f'feat_bb_l{suf}'] = lw
            dt[f'feat_bb_dist_pct{suf}'] = (dt[cl] - lw) / (u - lw)

        def add_rsi(dt, cl, l, suf):
            delta = dt[cl].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=l).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=l).mean()
            rs = gain / loss
            dt[f'feat_rsi{suf}'] = 100 - (100 / (1 + rs))

        # 1H Base Features
        add_macd(df, close_col, 12, 26, 9, '')
        add_bb(df, close_col, 20, 2, '')
        add_rsi(df, close_col, 14, '')

        # 4H Emulated (Multiplicador x4)
        add_macd(df, close_col, 12*4, 26*4, 9*4, '_4h')
        add_bb(df, close_col, 20*4, 2, '_4h')
        add_rsi(df, close_col, 14*4, '_4h')

        # 1D Emulated (Multiplicador x24)
        add_macd(df, close_col, 12*24, 26*24, 9*24, '_1d')
        add_bb(df, close_col, 20*24, 2, '_1d')
        add_rsi(df, close_col, 14*24, '_1d')

        # Mantendo retrocompatibilidade para partes do bot que exibem 'RSI_14' logado
        df['RSI_14'] = df['feat_rsi']
        
        try:
            from tools.features import apply_all_features
            df = apply_all_features(df, close_col=close_col)
        except ImportError as e:
            print(f"Warning: tools.features not found. {e}")
            pass

        return df

if __name__ == "__main__":
    engine = DataEngine()
    df = engine.fetch_binance_klines("BTCUSDT", interval="1h")
    df = engine.apply_indicators(df)
    print(df[['close', 'delta', 'CVD', 'RSI_14']].tail())
