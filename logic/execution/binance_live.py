import os
import sys
from typing import Any, Dict, Optional
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from .base import BaseExchange

class BinanceLive(BaseExchange):
    def __init__(self) -> None:
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.client = None

        if not self.api_key or not self.api_secret:
            if os.getenv("SHADOW_MODE", "True").lower() == "true":
                print("[WARN] Chaves Binance ausentes, mas operando em SHADOW_MODE. Usando credenciais dummy.")
                self.api_key = "dummy"
                self.api_secret = "dummy"
            else:
                print("[ERRO FATAL] Chaves BINANCE_API_KEY e BINANCE_API_SECRET ausentes no .env!")
                sys.exit(1)

    async def initialize(self, max_retries: int = 5):
        """Initialize the AsyncClient with retries for network issues."""
        last_err = None
        for attempt in range(max_retries):
            try:
                if self.client:
                    try: await self.client.close_connection()
                    except: pass
                
                self.client = await AsyncClient.create(self.api_key, self.api_secret)
                
                if self.api_key == "dummy":
                    print("👻 [SHADOW] Operando sem chaves reais. Funcionalidades restritas (Apenas Market Data publico).")
                    return

                account_info = await self.client.get_account()
                if not account_info.get('canTrade'):
                    print("[ERRO FATAL] As chaves API nao tem permissao de Trading habilitada!")
                    sys.exit(1)
                print("✅ Conectado na Binance (LIVE)! Permissao de leitura/trading ativa.")
                return
            except BinanceAPIException as e:
                if e.status_code in [401, 403]:
                    print(f"[ERRO FATAL] Credenciais rejeitadas (API Key/Secret invalida): {e}")
                    sys.exit(1)
                last_err = e
            except Exception as e:
                last_err = e
            
            wait_time = 2 ** attempt
            print(f"[WARN] Falha ao inicializar Binance Live (tentativa {attempt+1}/{max_retries}): {last_err}. Retentando em {wait_time}s...")
            await asyncio.sleep(wait_time)
        
        print(f"[ERRO CRITICO] Nao foi possivel conectar a Binance apos {max_retries} tentativas. O bot seguira tentando em background.")


    async def get_balance(self, asset: str = 'BRL') -> float:
        try:
            asset_info = await self.client.get_asset_balance(asset=asset)
            return float(asset_info['free']) if asset_info else 0.0
        except Exception:
            return 0.0

    async def create_order(self, symbol: str, side: str, order_type: str, quantity: float, **kwargs: Any) -> Dict[str, Any]:
        return await self.client.create_order(
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            **kwargs
        )

    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        return await self.client.get_order(symbol=symbol, orderId=order_id)

    async def cancel_order(self, symbol: str, order_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.client.cancel_order(symbol=symbol, orderId=order_id, **kwargs)

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        return await self.client.get_symbol_ticker(symbol=symbol)

    async def get_orderbook_ticker(self, symbol: str) -> Dict[str, Any]:
        return await self.client.get_orderbook_ticker(symbol=symbol)

    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        return await self.client.get_symbol_info(symbol)

    async def start_user_data_stream(self) -> str:
        if self.api_key == "dummy":
            return ""
        try:
            # Para Futuros (Yield Basis), o metodo correto no AsyncClient do python-binance e futures_stream_get_listen_key
            return await self.client.futures_stream_get_listen_key()
        except Exception as e:
            print(f"[ERROR] Falha ao obter Listen Key: {e}")
            return ""

    async def keep_user_data_stream_alive(self, listen_key: str):
        try:
            await self.client.keep_alive_listen_key(listen_key)
        except Exception as e:
            print(f"[ERROR] Falha ao renovar Listen Key: {e}")
