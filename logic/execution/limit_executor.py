import asyncio
import logging
from typing import Any, Dict, Optional
from .base import BaseExchange

logger = logging.getLogger("LimitExecutor")

class LimitExecutor:
    """
    Handles robust execution of LIMIT orders, specifically focusing on 
    Maker-only execution (Post-Only) to minimize slippage and fees.
    """
    
    def __init__(self, exchange: BaseExchange):
        self.exchange = exchange

    async def execute_limit_order(self, symbol: str, side: str, quantity: float, max_retries: int = 5) -> Optional[Dict[str, Any]]:
        """
        Attempts to fill a limit order by following the best bid/ask.
        Uses LIMIT_MAKER to ensure we are providing liquidity.
        """
        for attempt in range(max_retries):
            try:
                # 1. Get best bid/ask
                book = await self.exchange.get_orderbook_ticker(symbol)
                if not book:
                    logger.warning(f"[LIMIT] Could not fetch book for {symbol}")
                    continue
                
                price = float(book['bidPrice']) if side == 'BUY' else float(book['askPrice'])
                
                # 2. Place LIMIT_MAKER order
                logger.info(f"[LIMIT] Attempt {attempt+1}: Placing {side} {quantity} {symbol} @ {price}")
                order = await self.exchange.create_order(
                    symbol=symbol,
                    side=side,
                    order_type='LIMIT_MAKER',
                    quantity=quantity,
                    price=str(price)
                )
                
                if order and order.get('status') == 'FILLED':
                    return order
                
                # 3. Monitor for a short period
                order_id = order.get('orderId')
                fill_timeout = 30 # seconds
                start_time = asyncio.get_event_loop().time()
                
                while asyncio.get_event_loop().time() - start_time < fill_timeout:
                    await asyncio.sleep(2)
                    status_res = await self.exchange.get_order_status(symbol, order_id)
                    
                    if status_res.get('status') == 'FILLED':
                        logger.info(f"[LIMIT] Order {order_id} filled successfully.")
                        return status_res
                    
                    if status_res.get('status') in ['CANCELED', 'EXPIRED', 'REJECTED']:
                        logger.warning(f"[LIMIT] Order {order_id} ended with status: {status_res.get('status')}")
                        break
                
                # 4. If not filled or ended poorly, cancel and retry
                logger.info(f"[LIMIT] Order {order_id} not filled quickly. Cancelling and retrying...")
                await self.exchange.cancel_order(symbol, order_id)
                
            except Exception as e:
                logger.error(f"[LIMIT] Error in execution attempt {attempt+1}: {e}")
                await asyncio.sleep(1)
                
        return None

    async def execute_smart_market(self, symbol: str, side: str, quantity: float) -> Optional[Dict[str, Any]]:
        """
        Fallback to market order if Limit fails, but with a safety check.
        """
        try:
            return await self.exchange.create_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=quantity
            )
        except Exception as e:
            logger.error(f"[MARKET] Failed fallback: {e}")
            return None
