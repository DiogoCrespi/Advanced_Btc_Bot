# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import yfinance as yf
import queue
from logic.order_flow_logic import OrderFlowLogic
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

    def _make_request(self, subdomain, path, params=None, max_retries=3):
        """
        Helper para disparar chamadas HTTP resilientes para a Binance.
        Alterna entre enderecos principais e fallbacks (ex: api, api1, api2, api3).
        """
        # Define os enderecos base para cada subdominio
        base_urls = [f"https://{subdomain}.binance.com"]
        # Fallbacks conhecidos para api, fapi, dapi
        for i in range(1, 4):
            base_urls.append(f"https://{subdomain}{i}.binance.com")
            
        last_err = None
        for attempt in range(max_retries):
            for base_url in base_urls:
                url = f"{base_url}{path}"
                try:
                    # Timeout generico de 10s
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 429:
                        # Rate limit: espera mais tempo
                        wait = (attempt + 1) * 5
                        print(f"[WARN] Binance Rate Limit (429) em {url}. Esperando {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"[WARN] Binance API {url} retornou HTTP {response.status_code}")
                except Exception as e:
                    last_err = e
                    # Tenta o proximo fallback imediatamente se for erro de conexao
                    continue
            
            # Se terminou todos os fallbacks sem sucesso, espera e tenta novamente a proxima tentativa
            wait_time = 2 ** attempt
            print(f"[RETRY] Todos os fallbacks para {subdomain}{path} falharam. Tentativa {attempt+1}/{max_retries}. Esperando {wait_time}s... Erro: {last_err}")
            time.sleep(wait_time)
            
        return None

    def fetch_delivery_klines(self, symbol, interval="1h", limit=1000):
        """
        Busca klines historicos de um contrato de entrega.
        """
        print(f"Fetching Delivery klines for {symbol}...")
        data = self._make_request('dapi', "/dapi/v1/klines", params={"symbol": symbol, "interval": interval, "limit": limit})
        if not data: return pd.DataFrame()
        
        try:
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
            print(f"Exception processing delivery klines: {e}")
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
            # Temporarily disabled yfinance to prevent hangs on some remote environments
            # sp500_df = yf.Ticker("^GSPC").history(period=period, interval="1d")
            # dxy_df = yf.Ticker("DX-Y.NYB").history(period=period, interval="1d")
            # gold_df = yf.Ticker("GC=F").history(period=period, interval="1d")
            pass
        except Exception as e:
            print(f"[DATA] Aviso Macro Data: {e}")

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
        # print(f"Fetching data for {self.symbol} and {self.secondary_symbol}...")
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
            # print(f"Fetching funding batch for {symbol} (start: {current_start})...")
            params = {"symbol": symbol, "limit": 1000}
            if current_start:
                params["startTime"] = int(current_start)
                
            try:
                data = self._make_request('fapi', "/fapi/v1/fundingRate", params=params)
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
        data = self._make_request('dapi', "/dapi/v1/exchangeInfo")
        if not data: return []
        
        try:
            symbols = data.get('symbols', [])
            quarterly_contracts = [
                s for s in symbols 
                if s['baseAsset'] == asset and s['contractType'] in ['CURRENT_QUARTER', 'NEXT_QUARTER']
            ]
            print(f"[DEBUG] Saindo de fetch_delivery_contracts. Encontrados: {len(quarterly_contracts)}")
            return quarterly_contracts
        except Exception as e:
            print(f"Exception processing delivery contracts: {e}")
            return []

    def fetch_basis_data(self, spot_symbol="BTCUSDT", delivery_symbol="BTCUSD_250627"):
        """
        Calculates the differential (Basis) between Spot and Delivery Future.
        Supports BRL by converting spot to USD if necessary.
        """
        try:
            # 1. Spot Price
            spot_data = self._make_request('api', "/api/v3/ticker/price", params={"symbol": spot_symbol})
            if not spot_data or 'price' not in spot_data:
                print(f"Error fetching spot: {spot_data}")
                return None
            spot_price_raw = float(spot_data['price'])
            
            # 2. USDBRL Rate (if needed)
            usd_brl = 1.0
            if "BRL" in spot_symbol:
                fx_data = self._make_request('api', "/api/v3/ticker/price", params={"symbol": "USDTBRL"})
                if fx_data and 'price' in fx_data:
                    usd_brl = float(fx_data['price'])
            
            # Normalize spot price to USD
            spot_price_usd = spot_price_raw / usd_brl
            
            # 3. Delivery Price
            delivery_data = self._make_request('dapi', "/dapi/v1/ticker/bookTicker", params={"symbol": delivery_symbol})
            if not delivery_data: return None
            
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

    def fetch_binance_klines(self, symbol="BTCUSDT", interval="1h", limit=1000, startTime=None, endTime=None):
        """
        Fetches historical klines from Binance Spot API including Taker Volume.
        Supports pagination via startTime and endTime.
        """
        # Cache only for the default recent lookback to avoid memory bloat with historical data
        is_cacheable = startTime is None and endTime is None and limit <= 1000
        cache_key = f"{symbol}_{interval}_{limit}"
        
        if is_cacheable:
            now = time.time()
            if cache_key in self._klines_cache:
                cache_time, cached_df = self._klines_cache[cache_key]
                if now - cache_time < 15:
                    return cached_df.copy()

        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if startTime: params["startTime"] = int(startTime)
        if endTime: params["endTime"] = int(endTime)
        
        data = self._make_request('api', "/api/v3/klines", params=params)
        
        if data:
            try:
                df = pd.DataFrame(data, columns=[
                    'open_time', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'count', 
                    'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
                ])
                
                # Convert to numeric
                cols = ['open', 'high', 'low', 'close', 'volume', 'taker_buy_base_volume']
                # BOLT OPTIMIZATION: Replaced apply(pd.to_numeric) with vectorized astype(float) to eliminate Python-level loop overhead and speed up data ingestion
                df[cols] = df[cols].astype(float)
                
                df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
                df.set_index('open_time', inplace=True)
                
                # Calculate CVD (Cumulative Volume Delta)
                df['buy_vol'] = df['taker_buy_base_volume']
                df['sell_vol'] = df['volume'] - df['buy_vol']
                df['delta'] = df['buy_vol'] - df['sell_vol']
                
                if is_cacheable:
                    df['CVD'] = df['delta'].cumsum() # CVD needs full history to be meaningful
                    self._klines_cache[cache_key] = (time.time(), df)
                
                return df.copy()
            except Exception as e:
                print(f"Error processing Binance Klines for {symbol}: {e}")
        
        return pd.DataFrame()

    def fetch_historical_backfill(self, symbol="BTCUSDT", interval="1h", target_samples=10000):
        """
        Paginates backwards to fetch the requested number of samples.
        """
        print(f"[DATA] [BACKFILL] Iniciando backfill de {target_samples} amostras para {symbol}...")
        all_klines = []
        last_startTime = None
        
        # O teto maximo e 1000 por chamada. Paginamos ate atingir o alvo.
        batch_size = 1000
        needed_batches = (target_samples // batch_size) + 1
        
        for i in range(needed_batches):
            # Para paginar para tras, precisamos do endTime. 
            # Contudo, a API da Binance funciona melhor paginando para frente se soubermos o inicio,
            # ou podemos simplesmente ir buscando o "presente" e usar o tempo da primeira kline para a proxima busca retroativa.
            
            params = {"symbol": symbol, "interval": interval, "limit": batch_size}
            if last_startTime:
                # Vamos buscar o bloco ANTERIOR ao que ja temos
                # endTime e exclusivo.
                params["endTime"] = last_startTime - 1
            
            data = self._make_request('api', "/api/v3/klines", params=params)
            if not data or not isinstance(data, list):
                break
                
            df_batch = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'count', 
                'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
            ])
            
            all_klines.append(df_batch)
            last_startTime = int(df_batch['open_time'].values[0])
            
            collected = sum(len(b) for b in all_klines)
            print(f"   > Coletado: {collected}/{target_samples}...")
            
            if collected >= target_samples:
                break
                
            # Rate limit safety
            time.sleep(0.5)

        if not all_klines:
            return pd.DataFrame()
            
        df = pd.concat(all_klines).sort_values('open_time').drop_duplicates('open_time')
        
        # Convert to numeric
        cols = ['open', 'high', 'low', 'close', 'volume', 'taker_buy_base_volume']
        # BOLT OPTIMIZATION: Replaced apply(pd.to_numeric) with vectorized astype(float) to eliminate Python-level loop overhead and speed up data ingestion
        df[cols] = df[cols].astype(float)
        
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        
        # Recalcula CVD para o set completo
        df['buy_vol'] = df['taker_buy_base_volume']
        df['sell_vol'] = df['volume'] - df['buy_vol']
        df['delta'] = df['buy_vol'] - df['sell_vol']
        df['CVD'] = df['delta'].cumsum()
        
        print(f"[SUCCESS] [DATA] Backfill concluido: {len(df)} amostras.")
        return df


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
            # BOLT OPTIMIZATION: Avoid division by zero warnings and use np.where
            bb_range = u - lw
            dt[f'feat_bb_dist_pct{suf}'] = np.where(bb_range == 0, 0, (dt[cl] - lw) / bb_range)

        def add_rsi(dt, cl, l, suf):
            # BOLT OPTIMIZATION: Replaced pd.Series.where() with vectorized np.maximum
            delta = dt[cl].diff().values
            gain = pd.Series(np.maximum(delta, 0), index=dt.index).rolling(window=l).mean()
            loss = pd.Series(np.maximum(-delta, 0), index=dt.index).rolling(window=l).mean()
            # Prevent division by zero internally via replacing zero loss with NaN initially
            rs = gain / loss.replace(0, np.nan)
            dt[f'feat_rsi{suf}'] = 100 - (100 / (1 + rs))

        def add_atr(dt, h, l, c, period, suf):
            prev_c = dt[c].shift(1)
            tr = np.maximum(dt[h] - dt[l], 
                            np.maximum(np.abs(dt[h] - prev_c), 
                                       np.abs(dt[l] - prev_c)))
            atr = tr.rolling(window=period).mean()
            dt[f'feat_atr{suf}'] = atr
            dt[f'feat_atr_pct{suf}'] = (atr / dt[c]) * 100

        # 1H Base Features
        add_macd(df, close_col, 12, 26, 9, '')
        add_bb(df, close_col, 20, 2, '')
        add_rsi(df, close_col, 14, '')
        add_atr(df, high_col, low_col, close_col, 14, '')

        # 4H Emulated (Multiplicador x4)
        add_macd(df, close_col, 12*4, 26*4, 9*4, '_4h')
        add_bb(df, close_col, 20*4, 2, '_4h')
        add_rsi(df, close_col, 14*4, '_4h')

        # 1D Emulated (Multiplicador x24)
        add_macd(df, close_col, 12*24, 26*24, 9*24, '_1d')
        add_bb(df, close_col, 20*24, 2, '_1d')
        add_rsi(df, close_col, 14*24, '_1d')

        # Order Flow Features (PR #60 - Microestrutura)
        of_logic = OrderFlowLogic()
        if 'taker_buy_base_volume' in df.columns:
            df['taker_buy_volume'] = df['taker_buy_base_volume']
            df = of_logic.calculate_delta_features(df)
            # Compatibilidade com nomes antigos
            df['CVD'] = df['feat_cvd_8h']
            df['delta'] = df['feat_delta']

        # Mantendo retrocompatibilidade para partes do bot que exibem 'RSI_14' logado
        df['RSI_14'] = df['feat_rsi']
        
        try:
            from tools.features import apply_all_features
            df = apply_all_features(df, close_col=close_col)
        except ImportError as e:
            print(f"Warning: tools.features not found. {e}")
            pass

        return df

    def fetch_order_book_imbalance(self, symbol="BTCUSDT"):
        """Busca o snapshot do Order Book e calcula o Imbalance de Liquidez."""
        params = {"symbol": symbol, "limit": 50}
        data = self._make_request('api', "/api/v3/depth", params=params)
        if data:
            of_logic = OrderFlowLogic()
            return of_logic.calculate_order_book_imbalance(data.get('bids', []), data.get('asks', []))
        return 0.0

if __name__ == "__main__":
    engine = DataEngine()
    df = engine.fetch_binance_klines("BTCUSDT", interval="1h")
    df = engine.apply_indicators(df)
    print(df[['close', 'delta', 'CVD', 'RSI_14']].tail())
