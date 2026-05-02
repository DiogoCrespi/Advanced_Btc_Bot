import asyncio
import os
import sys
import pandas as pd
from binance import AsyncClient
from datetime import datetime

# Garante a importação dos módulos locais quando executado da raiz do repositório
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.data_engine import DataEngine

async def fetch_historical_data(symbol: str, interval: str, start_str: str, end_str: str = None):
    print(f"[*] Iniciando coleta massiva de {symbol} ({interval}) de {start_str}...")
    client = await AsyncClient.create()
    
    klines = await client.get_historical_klines(
        symbol=symbol,
        interval=interval,
        start_str=start_str,
        end_str=end_str
    )
    await client.close_connection()

    # Estruturação e Limpeza Mínima
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])

    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'taker_buy_base_asset_volume']
    # BOLT OPTIMIZATION: Replacing apply(pd.to_numeric) with vectorized block astype(float) for faster data conversion
    df[numeric_cols] = df[numeric_cols].astype(float)
    df.set_index('open_time', inplace=True)
    
    # Calcular base CVD (Cumulative Volume Delta) similar ao data_engine nativo
    df['buy_vol'] = df['taker_buy_base_asset_volume']
    df['sell_vol'] = df['volume'] - df['buy_vol']
    df['delta'] = df['buy_vol'] - df['sell_vol']
    df['CVD'] = df['delta'].cumsum()

    df.drop(columns=['ignore', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_quote_asset_volume'], inplace=True)
    
    return df

async def main():
    # Parâmetros de Treinamento definidos pelo TRAINING.md
    symbol = "BTCUSDT"
    interval = AsyncClient.KLINE_INTERVAL_1HOUR 
    
    # 2 Anos garante ciclos suficientes para a Random Forest validar via Walk-Forward
    df = await fetch_historical_data(symbol, interval, "2 years ago UTC")
    
    # Aumentando os dados brutos com as Features atualizadas (agora inclui MACD e BB)
    engine = DataEngine()
    df = engine.apply_indicators(df)

    os.makedirs("data", exist_ok=True)
    file_path = f"data/{symbol}_{interval}_historical.parquet"
    
    # O Parquet com Snappy garante que os 2 anos ocupem pouco espaço e leiam rápido no treinamento
    df.to_parquet(file_path, compression='snappy')
    print(f"[+] Download e Engajamento concluídos. {len(df)} linhas de features salvas em: {file_path}")

if __name__ == "__main__":
    asyncio.run(main())
