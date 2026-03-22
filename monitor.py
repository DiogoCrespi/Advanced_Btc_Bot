import os
import time
import json
from datetime import datetime

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def format_pnl(pnl, is_percent=True):
    color = "\033[92m" if pnl >= 0 else "\033[91m"
    reset = "\033[0m"
    if is_percent:
        return f"{color}{pnl:+.2%}{reset}"
    else:
        return f"{color}R$ {pnl:+.2f}{reset}"

def monitor():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    status_file = os.path.join(base_dir, "results/bot_status.json")
    log_file = os.path.join(base_dir, "results/paper_trades_log.txt")
    initial_balance = 1000.0

    while True:
        clear_screen()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Load Bot Status
        current_balance = initial_balance
        trade_amount = 100.0
        active_positions = {}
        if os.path.exists(status_file):
            try:
                with open(status_file, "r") as f:
                    data = json.load(f)
                    current_balance = data.get("balance", initial_balance)
                    trade_amount = data.get("trade_amount", 100.0)
                    active_positions = data.get("positions", {})
            except: pass
        
        # Calculate Floating PnL
        floating_pnl_brl = 0.0
        for asset, pos in active_positions.items():
            curr_price = pos.get('current_price', pos['entry'])
            price_ret = (curr_price / pos['entry']) - 1
            asset_pnl = price_ret * pos['signal'] * trade_amount
            floating_pnl_brl += asset_pnl
        
        total_equity = current_balance + floating_pnl_brl
        total_pnl_pct = (total_equity / initial_balance) - 1
        
        print(f"+{'-'*65}+")
        print(f"| >> BTC BOT MONITOR | {timestamp} |")
        print(f"+{'-'*65}+")
        print(f"| SALDO REALIZADO:  R$ {current_balance:8.2f}                                |")
        print(f"| PnL FLUTUANTE:    {format_pnl(floating_pnl_brl, False):18}                              |")
        print(f"| PATRIMONIO TOTAL: R$ {total_equity:8.2f}                                |")
        print(f"| PnL TOTAL (Eq):   {format_pnl(total_pnl_pct):18}                              |")
        print(f"+{'-'*65}+")
        
        # Section: MiroFish Sentiment
        sentiment_data = data.get("sentiment", {"sentiment": "Neutral", "confidence": 0.5, "updated": "N/A"})
        sent_str = sentiment_data.get("sentiment", "Neutral")
        color = "\033[92m" if sent_str == "Bullish" else "\033[91m" if sent_str == "Bearish" else "\033[93m"
        reset = "\033[0m"
        conf = sentiment_data.get("confidence", 0.0)
        upd = sentiment_data.get("updated", "N/A")
        print(f"| SENTIMENTO (MiroFish): {color}{sent_str:8}{reset} | Conf: {conf:.2f} | Upd: {upd:8} |")
        print(f"+{'-'*65}+")
        
        # Section: Quantities
        qty_btc = active_positions.get("BTCBRL", {}).get("qty", 0.0)
        qty_eth = active_positions.get("ETHBRL", {}).get("qty", 0.0)
        qty_sol = active_positions.get("SOLBRL", {}).get("qty", 0.0)
        print(f"| HOLDINGS:     BTC:{qty_btc:.5f} | ETH:{qty_eth:.4f} | SOL:{qty_sol:.2f}     |")
        print(f"+{'-'*65}+")
        
        # Section: Active Positions
        print(f"| POSICOES ATIVAS:                                              |")
        if active_positions:
            for asset, pos in active_positions.items():
                side = "LONG" if pos['signal'] == 1 else "SHORT"
                curr_price = pos.get('current_price', pos['entry'])
                pnl = ((curr_price / pos['entry']) - 1) * pos['signal']
                print(f"| > {asset:9}: {side:5} @ {pos['entry']:10.2f} -> {format_pnl(pnl):14} |")
        else:
            print(f"|   (Nenhuma posicao aberta no momento)                         |")
            
        print(f"+{'-'*65}+")
        
        # Section: Recent Events
        print(f"| ULTIMOS EVENTOS (Log):                                        |")
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    last_events = lines[-8:] if len(lines) > 8 else lines
                    if not last_events:
                        print("|   (Nenhum evento registrado ainda)                            |")
                    for line in reversed(last_events):
                        clean_line = line.strip().encode('ascii', 'ignore').decode('ascii')[:60]
                        print(f"| > {clean_line:60} |")
            except:
                print("|   (Erro ao ler log de trades)                                 |")
        else:
            print("|   (Aguardando primeira operacao...)                           |")
            
        print(f"+{'-'*65}+")
        print("\n[Pressione Ctrl+C para sair]")
        time.sleep(10)

if __name__ == "__main__":
    monitor()
