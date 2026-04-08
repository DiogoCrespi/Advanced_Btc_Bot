import threading
import uuid
import pandas as pd
from typing import Any, Dict, Optional, List
from datetime import datetime
from .base import BaseExchange

class BacktestEngine(BaseExchange):
    def __init__(self, initial_balance: float = 1000.0, maker_fee: float = 0.001, taker_fee: float = 0.001, slippage: float = 0.0005) -> None:
        self.initial_balance = initial_balance
        self.balances: Dict[str, float] = {'BRL': initial_balance, 'USDT': 0.0}
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage = slippage

        self.data: Optional[pd.DataFrame] = None
        self.current_index: int = 0

        self.active_orders: Dict[str, Dict[str, Any]] = {}
        self.trade_history: List[Dict[str, Any]] = []

        self.lock = threading.Lock()
        print("🎮 Backtest Engine Initialized. Mode: SIMULATION")

    def load_data(self, df: pd.DataFrame) -> None:
        """
        Loads historical OHLCV data for backtesting.
        Data should have a DatetimeIndex and columns 'open', 'high', 'low', 'close', 'volume'.
        """
        with self.lock:
            self.data = df.copy()
            self.current_index = 0

    def set_current_index(self, index: int) -> None:
        """
        Advances the simulation to a specific index in the loaded data.
        """
        with self.lock:
            if self.data is not None and 0 <= index < len(self.data):
                self.current_index = index

    def step(self) -> bool:
        """
        Advances the simulation by one time step. Returns False if at the end of data.
        """
        with self.lock:
            if self.data is None or self.current_index >= len(self.data) - 1:
                return False
            self.current_index += 1

            # Simple order processing: evaluate limit orders against new high/low
            current_row = self.data.iloc[self.current_index]
            completed_orders = []

            for order_id, order in self.active_orders.items():
                if order['type'] == 'LIMIT':
                    price = order.get('price', 0.0)
                    if order['side'] == 'BUY' and current_row['low'] <= price:
                        self._execute_order(order, price, is_maker=True)
                        completed_orders.append(order_id)
                    elif order['side'] == 'SELL' and current_row['high'] >= price:
                        self._execute_order(order, price, is_maker=True)
                        completed_orders.append(order_id)

            for oid in completed_orders:
                del self.active_orders[oid]

            return True

    def _execute_order(self, order: Dict[str, Any], execute_price: float, is_maker: bool = False) -> None:
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        symbol = order['symbol']
        side = order['side']
        qty = order['quantity']

        # Determine base and quote assets
        # Assume format BASEQUOTE (e.g., BTCBRL -> base=BTC, quote=BRL)
        base_asset = symbol.replace('BRL', '').replace('USDT', '')
        if 'BRL' in symbol:
            quote_asset = 'BRL'
        elif 'USDT' in symbol:
            quote_asset = 'USDT'
        else:
            quote_asset = 'USD'

        if base_asset not in self.balances:
            self.balances[base_asset] = 0.0

        quote_amount = qty * execute_price
        fee_amount = quote_amount * fee_rate

        if side == 'BUY':
            if self.balances[quote_asset] >= quote_amount:
                self.balances[quote_asset] -= quote_amount
                # Basic slippage model: slightly reduce acquired qty
                actual_qty = qty * (1 - self.slippage) if not is_maker else qty
                self.balances[base_asset] += actual_qty
                # Deduct fee from base or quote depending on exchange rules, usually base for buy
                fee_in_base = actual_qty * fee_rate
                self.balances[base_asset] -= fee_in_base

                trade_record = {
                    'timestamp': self.data.index[self.current_index] if self.data is not None else datetime.now(),
                    'symbol': symbol,
                    'side': side,
                    'price': execute_price,
                    'quantity': actual_qty,
                    'fee': fee_in_base,
                    'fee_asset': base_asset,
                    'type': order['type']
                }
                self.trade_history.append(trade_record)
        elif side == 'SELL':
            if self.balances[base_asset] >= qty:
                self.balances[base_asset] -= qty
                actual_price = execute_price * (1 - self.slippage) if not is_maker else execute_price
                received_quote = qty * actual_price
                fee_in_quote = received_quote * fee_rate
                self.balances[quote_asset] += (received_quote - fee_in_quote)

                trade_record = {
                    'timestamp': self.data.index[self.current_index] if self.data is not None else datetime.now(),
                    'symbol': symbol,
                    'side': side,
                    'price': actual_price,
                    'quantity': qty,
                    'fee': fee_in_quote,
                    'fee_asset': quote_asset,
                    'type': order['type']
                }
                self.trade_history.append(trade_record)

    def get_balance(self, asset: str = 'BRL') -> float:
        with self.lock:
            return self.balances.get(asset, 0.0)

    def create_order(self, symbol: str, side: str, order_type: str, quantity: float, **kwargs: Any) -> Dict[str, Any]:
        with self.lock:
            order_id = str(uuid.uuid4())
            order = {
                'orderId': order_id,
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': quantity,
                'status': 'NEW',
                **kwargs
            }

            if order_type == 'MARKET':
                if self.data is not None and len(self.data) > 0:
                    current_price = float(self.data.iloc[self.current_index]['close'])
                else:
                    current_price = kwargs.get('simulated_price', 0.0) # Fallback for pure mocked execution

                if current_price > 0:
                    self._execute_order(order, current_price, is_maker=False)
                    order['status'] = 'FILLED'
                    order['price'] = current_price
            elif order_type == 'LIMIT':
                self.active_orders[order_id] = order

            return order

    def cancel_order(self, symbol: str, order_id: str, **kwargs: Any) -> Dict[str, Any]:
        with self.lock:
            if order_id in self.active_orders:
                del self.active_orders[order_id]
                return {'symbol': symbol, 'orderId': order_id, 'status': 'CANCELED'}
            return {'symbol': symbol, 'orderId': order_id, 'status': 'NOT_FOUND'}

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        with self.lock:
            if self.data is not None and len(self.data) > 0:
                price = float(self.data.iloc[self.current_index]['close'])
                return {'symbol': symbol, 'price': str(price)}
            return {'symbol': symbol, 'price': '0.0'}

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        # Mocking generic Binance symbol info
        return {
            'symbol': symbol,
            'filters': [
                {'filterType': 'LOT_SIZE', 'stepSize': '0.00001'},
                {'filterType': 'PRICE_FILTER', 'tickSize': '0.01'}
            ]
        }
