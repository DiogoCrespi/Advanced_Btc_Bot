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

    def get_ce_entry(self, ob):
        """
        Gatilho Otimizado (CE Zone): 
        Entry at 50% (Mean Threshold) of the Order Block.
        """
        ce_price = (ob['top'] + ob['bottom']) / 2
        return ce_price

    def calculate_position_size(self, entry_price, stop_loss):
        """
        Calculates position size based on balance and risk amount.
        """
        risk_amount = self.balance * self.risk_per_trade
        loss_per_unit = abs(entry_price - stop_loss)
        if loss_per_unit == 0:
            return 0
        return risk_amount / loss_per_unit

if __name__ == "__main__":
    rm = RiskManager()
    ob = {'top': 50000, 'bottom': 48000}
    print(f"CE Entry: {rm.get_ce_entry(ob)}")
    print(f"Position Size: {rm.calculate_position_size(50000, 48000)}")
