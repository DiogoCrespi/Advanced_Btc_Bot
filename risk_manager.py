import numpy as np

class RiskManager:
    def __init__(self, initial_balance=10000, risk_per_trade=0.02):
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.hwm = initial_balance
        self.max_drawdown = 0

    def calculate_drawdown(self, current_balance):
        """
        Calculates current drawdown and updates HWM / Max Drawdown.
        """
        if current_balance > self.hwm:
            self.hwm = current_balance
        
        current_dd = (self.hwm - current_balance) / self.hwm
        if current_dd > self.max_drawdown:
            self.max_drawdown = current_dd
            
        return current_dd

    def get_entry(self, ob, entry_type='50_ce'):
        """
        Calculates entry price based on OB and entry type.
        types: 'open', '25_ce', '50_ce'
        """
        if entry_type == 'open':
            return ob['top'] if ob['type'] == 'bearish' else ob['bottom']
        
        # CE = Mean Threshold (50%)
        ce_50 = (ob['top'] + ob['bottom']) / 2
        if entry_type == '50_ce':
            return ce_50
            
        # 25% CE (closer to the open)
        if entry_type == '25_ce':
            if ob['type'] == 'bullish':
                return ob['top'] - (ob['top'] - ob['bottom']) * 0.25
            else: # bearish
                return ob['bottom'] + (ob['top'] - ob['bottom']) * 0.25
                
        return ce_50

    def calculate_position_size(self, entry_price, stop_loss):
        """
        Calculates position size based on balance and risk amount.
        """
        risk_amount = self.balance * self.risk_per_trade
        loss_per_unit = abs(entry_price - stop_loss)
        if loss_per_unit == 0:
            return 0
        return risk_amount / loss_per_unit

    def calculate_pnl_with_fees(self, entry_price, exit_price, position_size, side='long', is_maker=False):
        """
        Calculates P&L taking into account Binance fees (Maker/Taker).
        Default to Taker (0.1%) for entry/exit to be realistic.
        """
        fee_rate = 0.0005 if is_maker else 0.0010 # 0.05% Maker, 0.1% Taker
        entry_value = entry_price * position_size
        exit_value = exit_price * position_size
        
        total_fees = (entry_value * fee_rate) + (exit_value * fee_rate)
        
        if side == 'long':
            gross_pnl = exit_value - entry_value
        else: # short
            gross_pnl = entry_value - exit_value
            
        return gross_pnl - total_fees

if __name__ == "__main__":
    rm = RiskManager()
    ob = {'top': 50000, 'bottom': 48000}
    print(f"CE Entry: {rm.get_ce_entry(ob)}")
    print(f"Position Size: {rm.calculate_position_size(50000, 48000)}")
