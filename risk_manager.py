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

    def check_liquidation_risk(self, entry_price, current_price, leverage=1.0):
        """
        Monitora o risco de liquidação da perna Short.
        Com 1x alavancagem, o preço de liquidação é aprox o dobro do preço de entrada.
        """
        # Preço de liquidação aproximado para Short 1x com margem isolada:
        # P_liq = Entry * (1 + 1/Leverage)
        liquidation_price = entry_price * (1 + 1/leverage)
        distance = (liquidation_price - current_price) / current_price
        return distance, liquidation_price

    def rebalance_margin(self, spot_balance, futures_margin, threshold=0.10):
        """
        Transfere lucro do Spot para Futuros para afastar a liquidação.
        """
        if spot_balance > futures_margin * (1 + threshold):
            transfer = (spot_balance - futures_margin) / 2
            return transfer
        return 0
