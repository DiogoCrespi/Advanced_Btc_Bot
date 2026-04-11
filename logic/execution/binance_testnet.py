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

    async def initialize(self):
        """Initialize the AsyncClient for Testnet."""
        try:
            # Note: The testnet parameter tells python-binance to use the testnet endpoints
            self.client = await AsyncClient.create(self.api_key, self.api_secret, testnet=True)
            account_info = await self.client.get_account()
            if not account_info.get('canTrade'):
                print("[ERRO FATAL] As chaves API nao tem permissao de Trading habilitada no Testnet!")
                sys.exit(1)
            print("✅ Conectado na Binance (TESTNET)! Permissao de leitura/trading ativa.")
        except BinanceAPIException as e:
            print(f"[ERRO FATAL] Credenciais rejeitadas pelo Testnet da Binance: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERRO FATAL] Falha de rede ao conectar com a Binance (Testnet): {e}")
            sys.exit(1)

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
