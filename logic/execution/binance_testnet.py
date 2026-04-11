import os
import sys
from typing import Any, Dict, Optional
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from .base import BaseExchange

class BinanceTestnet(BaseExchange):
    def __init__(self) -> None:
        self.api_key = os.getenv("BINANCE_TESTNET_API_KEY", os.getenv("BINANCE_API_KEY"))
        self.api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", os.getenv("BINANCE_API_SECRET"))
        self.client = None

        if not self.api_key or not self.api_secret:
            print("[ERRO FATAL] Chaves de API ausentes para o Testnet!")
            sys.exit(1)

    async def initialize(self, max_retries: int = 5):
        """Initialize the AsyncClient for Testnet with retries."""
        last_err = None
        for attempt in range(max_retries):
            try:
                if self.client:
                    try: await self.client.close_connection()
                    except: pass
                    
                self.client = await AsyncClient.create(self.api_key, self.api_secret, testnet=True)
                account_info = await self.client.get_account()
                if not account_info.get('canTrade'):
                    print("[ERRO FATAL] As chaves API nao tem permissao de Trading habilitada no Testnet!")
                    sys.exit(1)
                print("✅ Conectado na Binance (TESTNET)! Permissao de leitura/trading ativa.")
                return
            except BinanceAPIException as e:
                if e.status_code in [401, 403]:
                    print(f"[ERRO FATAL] Credenciais rejeitadas (API Key/Secret invalida) no Testnet: {e}")
                    sys.exit(1)
                last_err = e
            except Exception as e:
                last_err = e
            
            wait_time = 2 ** attempt
            print(f"[WARN] Falha ao inicializar Binance Testnet (tentativa {attempt+1}/{max_retries}): {last_err}. Retentando em {wait_time}s...")
            await asyncio.sleep(wait_time)

        print(f"[ERRO CRITICO] Nao foi possivel conectar ao Testnet apos {max_retries} tentativas. O bot seguira tentando em background.")


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

    async def cancel_order(self, symbol: str, order_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.client.cancel_order(symbol=symbol, orderId=order_id, **kwargs)

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        return await self.client.get_symbol_ticker(symbol=symbol)

    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        return await self.client.get_symbol_info(symbol)
