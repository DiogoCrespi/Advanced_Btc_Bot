class RiskManager:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.hwm = initial_balance
        self.max_drawdown = 0

    def calculate_pair_position(self, btc_price, eth_price, risk_fraction=0.10):
        """
        Aloca uma fração do capital total para o trade de pares (50/50 entre ativos).
        Isto garante neutralidade ao mercado (Hedge).
        """
        trade_capital = self.balance * risk_fraction
        
        # 50% para cada perna
        btc_size = (trade_capital / 2) / btc_price
        eth_size = (trade_capital / 2) / eth_price
        
        return btc_size, eth_size

    def calculate_pnl_with_fees(self, entry_price, exit_price, qty, is_short=False):
        """
        Simulando a execução via Limit Orders (Maker Fee).
        Vamos assumir a taxa VIP 0/Promocional para Maker (0.05%)
        """
        fee_rate = 0.0005 # 0.05% por ordem executada no book
        entry_value = entry_price * qty
        exit_value = exit_price * qty
        
        fee = (entry_value * fee_rate) + (exit_value * fee_rate)
        
        if is_short:
            gross_pnl = entry_value - exit_value
        else:
            gross_pnl = exit_value - entry_value
            
        return gross_pnl - fee

    def calculate_drawdown(self, current_balance):
        if current_balance > self.hwm:
            self.hwm = current_balance
        
        drawdown = (self.hwm - current_balance) / self.hwm
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
