import time
from datetime import datetime

class LogTester:
    def __init__(self):
        self.signals_file = "signals_log.txt"
        self.trades_file = "paper_trades_log.txt"
        
    def run_test(self):
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # 1. Simula Log de Sinal (IA)
        signal_msg = f"[{timestamp}] TESTE_SINAL: BTCBRL VENDA (70%)"
        with open(self.signals_file, "a") as f:
            f.write(signal_msg + "\n")
            f.flush()
        print(f"✅ Gravado em {self.signals_file}")
            
        # 2. Simula Log de Trade (Papel)
        trade_msg = f"[{timestamp}] TESTE_TRADE: ABERTO BTCBRL @ 350000.00"
        with open(self.trades_file, "a") as f:
            f.write(trade_msg + "\n")
            f.flush()
        print(f"✅ Gravado em {self.trades_file}")

if __name__ == "__main__":
    LogTester().run_test()
