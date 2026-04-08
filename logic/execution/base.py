from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseExchange(ABC):
    """
    Abstract Base Class for Exchange interactions.
    """

    @abstractmethod
    async def get_balance(self, asset: str = 'BRL') -> float:
        """
        Returns the free balance of the specified asset.
        """
        pass

    @abstractmethod
    async def create_order(self, symbol: str, side: str, order_type: str, quantity: float, **kwargs: Any) -> Dict[str, Any]:
        """
        Creates a new order.
        """
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Cancels an active order.
        """
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Gets the current ticker information for a symbol.
        """
        pass

    @abstractmethod
    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Gets the trading rules and filters for a symbol.
        """
        pass
