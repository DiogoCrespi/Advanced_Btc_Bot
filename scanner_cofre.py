from data_engine import DataEngine
from basis_logic import BasisLogic
import json
from datetime import datetime
import os
import time

class ScannerCofreHibrido:
    def __init__(self, asset="BTC", threshold_annual_yield=0.08):
        self.asset = asset
        self.threshold = threshold_annual_yield
        self.log_file = "scanner_history.log"
        
        # Reaproveitando os módulos core
        self.engine = DataEngine()
        self.logic = BasisLogic()

    def log_event(self, message):
        """Prints to console and appends to log file."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_msg = f"[{timestamp}] {message}"
        print(formatted_msg)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")

    def escanear_continuamente(self):
        self.log_event(f"🚀 Iniciando Sniper de Basis Arbitrage (Modo Loop)...")
        self.log_event(f"🎯 Ativo: {self.asset} | Threshold: {self.threshold*100}% a.a.")
        
        while True:
            try:
                contracts = self.engine.fetch_delivery_contracts(asset=self.asset)
                if not contracts:
                    self.log_event(f"❌ Nenhum contrato encontrado.")
                else:
                    results = []
                    for c in contracts:
                        symbol = c['symbol']
                        data = self.engine.fetch_basis_data(spot_symbol=f"{self.asset}USDT", delivery_symbol=symbol)
                        if data:
                            expiry = self.logic.parse_expiry(symbol)
                            y = self.logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
                            results.append({**data, 'symbol': symbol, 'yield_apr': y, 'expiry_date': str(expiry)})
                    
                    best = self.logic.get_best_contract(results)
                    
                    if best and best['yield_apr'] >= self.threshold:
                        self.gerar_ordem_de_servico(best)
                        # Após encontrar e gerar o mandato, interrompemos para ação humana
                        break
                    else:
                        current_best_yield = (best['yield_apr'] * 100) if best else 0
                        self.log_event(f"📈 Monitorando... Melhor Yield: {current_best_yield:.2f}% a.a. (Aguardando {self.threshold*100}%)")

            except Exception as e:
                self.log_event(f"❌ Erro durante verificação: {e}")
            
            time.sleep(60) # Checar a cada minuto

    def gerar_ordem_de_servico(self, contract):
        lucro_bruto_por_btc = contract['future'] - contract['spot']
        
        self.log_event(f"\n{'='*65}")
        self.log_event(f"🚀 OPORTUNIDADE DETECTADA! 🚀")
        self.log_event(f"{'='*65}")
        self.log_event(f"📌 Contrato Alvo:    {contract['symbol']}")
        self.log_event(f"💰 Preço Spot:       US$ {contract['spot']:.2f}")
        self.log_event(f"🎯 Preço Futuro:     US$ {contract['future']:.2f}")
        self.log_event(f"📈 Yield Anualizado: {contract['yield_apr']*100:.2f}% a.a.")
        self.log_event(f"💸 Prêmio por BTC:   US$ {lucro_bruto_por_btc:.2f}")
        self.log_event(f"📅 Data Vencimento:  {contract['expiry_date']}")
        self.log_event(f"{'='*65}")
        
        instrucoes = {
            'timestamp_analise': datetime.now().isoformat(),
            'contrato_alvo': contract['symbol'],
            'yield_anualizado_travado': round(contract['yield_apr'] * 100, 2),
            'data_vencimento': contract['expiry_date'],
            'detalhes_financeiros': {
                'spot_ref': contract['spot'],
                'future_ref': contract['future'],
                'premio_bruto_por_unidade': lucro_bruto_por_btc
            },
            'passo_a_passo_execucao': [
                "1. Abra o app/site da Binance.",
                f"2. Compre a quantidade desejada de {self.asset} no mercado SPOT (Par {self.asset}/USDT).",
                f"3. Transfira fisicamente esse {self.asset} da carteira 'Spot' para a carteira 'Futuros COIN-M'.",
                f"4. Vá na aba de Futuros COIN-M e selecione o contrato {contract['symbol']}.",
                f"5. Abra uma ordem de VENDA (SHORT) usando 1x de alavancagem.",
                f"6. PRONTO! Seu capital está com risco direcional zero. Risco de liquidação zero.",
                f"7. Coloque um alarme no seu celular para {contract['expiry_date']}. Neste dia, a Binance liquidará o contrato e o lucro acumulado estará na sua conta."
            ]
        }
        
        nome_arquivo = 'MANDATO_DE_EXECUCAO.json'
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(instrucoes, f, indent=4, ensure_ascii=False)
            
        self.log_event(f"\n📋 Instruções de execução tática salvas no arquivo: {nome_arquivo}")
        self.log_event(f"Siga os passos no JSON e trave o seu lucro manualmente com segurança.")

if __name__ == "__main__":
    # asset="BTC", yield_minimo=8%
    scanner = ScannerCofreHibrido(asset="BTC", threshold_annual_yield=0.08)
    scanner.escanear_continuamente()
