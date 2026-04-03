# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
from data_engine import DataEngine
from basis_logic import BasisLogic
import json
from datetime import datetime
import os
import time

class ScannerCofreHibrido:
    def __init__(self, asset_pair="BTCUSDT", threshold_annual_yield=0.08):
        # Handle cases like BTCUSDT or BTCBRL
        if "BRL" in asset_pair:
            self.asset = "BTC" 
            self.spot_symbol = "BTCBRL"
        else:
            self.asset = "BTC"
            self.spot_symbol = asset_pair
            
        self.threshold = threshold_annual_yield
        self.log_file = "scanner_history.log"
        
        # Reaproveitando os modulos core
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
        self.log_event(f"🚀 Iniciando Sniper de Basis Arbitrage (Modo Short-Term Priority)...")
        self.log_event(f"🎯 Ativo Base: {self.asset} | Spot: {self.spot_symbol} | Threshold: {self.threshold*100}% a.a.")
        
        while True:
            try:
                contracts = self.engine.fetch_delivery_contracts(asset=self.asset)
                if not contracts:
                    self.log_event(f"❌ Nenhum contrato encontrado para {self.asset}.")
                else:
                    results = []
                    for c in contracts:
                        symbol = c['symbol']
                        data = self.engine.fetch_basis_data(spot_symbol=self.spot_symbol, delivery_symbol=symbol)
                        if data:
                            expiry = self.logic.parse_expiry(symbol)
                            y = self.logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
                            results.append({**data, 'symbol': symbol, 'yield_apr': y, 'expiry_date': str(expiry)})
                    
                    # NOVA LOGICA: Priorizar o contrato mais PROXIMO que atenda o threshold
                    best = self.logic.get_earliest_profitable_contract(results, self.threshold)
                    
                    if best:
                        self.log_event(f"✅ Alvo Curto Encontrado: {best['symbol']} ({best['yield_apr']*100:.2f}% a.a.)")
                        self.gerar_ordem_de_servico(best)
                        break
                    else:
                        # Se nenhum bater o threshold, mostramos o melhor yield disponivel apenas para log
                        highest = self.logic.get_best_contract(results)
                        current_best_yield = (highest['yield_apr'] * 100) if highest else 0
                        self.log_event(f"📈 Monitorando... Alvo {self.threshold*100:.0f}% nao atingido. Melhor atual: {current_best_yield:.2f}% a.a.")

            except Exception as e:
                self.log_event(f"❌ Erro durante verificacao: {e}")
            
            time.sleep(60)

    def gerar_ordem_de_servico(self, contract):
        lucro_bruto_por_btc = contract['future'] - contract['spot']
        moeda_spot = "R$" if contract['currency'] == "BRL" else "US$"
        
        self.log_event(f"\n{'='*65}")
        self.log_event(f"🚀 OPORTUNIDADE DETECTADA ({contract['currency']})! 🚀")
        self.log_event(f"{'='*65}")
        self.log_event(f"📌 Contrato Alvo:    {contract['symbol']}")
        self.log_event(f"💰 Preco Spot:       {moeda_spot} {contract['spot_raw']:.2f}")
        if contract['currency'] == "BRL":
            self.log_event(f"💱 Taxa Conversao:   {contract['fx_rate']:.4f} USDT/BRL")
            self.log_event(f"💵 Spot Normalizado: US$ {contract['spot']:.2f}")
            
        self.log_event(f"🎯 Preco Futuro:     US$ {contract['future']:.2f}")
        self.log_event(f"📈 Yield Anualizado: {contract['yield_apr']*100:.2f}% a.a.")
        self.log_event(f"📅 Data Vencimento:  {contract['expiry_date']}")
        self.log_event(f"{'='*65}")
        
        instrucoes = {
            'timestamp_analise': datetime.now().isoformat(),
            'contrato_alvo': contract['symbol'],
            'yield_anualizado_travado': round(contract['yield_apr'] * 100, 2),
            'currency_spot': contract['currency'],
            'passo_a_passo_execucao': [
                "1. Abra o app/site da Binance.",
                f"2. Compre a quantidade desejada de {self.asset} usando {contract['currency']} (Par {self.asset}/{contract['currency']}).",
                f"3. Transfira esse {self.asset} da carteira 'Spot' para a carteira 'Futuros COIN-M'.",
                f"4. Siga para Futuros COIN-M e selecione o contrato {contract['symbol']}.",
                f"5. Abra uma ordem de VENDA (SHORT) usando 1x de alavancagem.",
                f"6. PRONTO! Seu lucro esta matematicamente travado em BTC.",
                f"7. No dia {contract['expiry_date']}, a Binance liquidara a posicao e voce tera recuperado seu capital + o premio da arbitragem."
            ]
        }
        
        nome_arquivo = 'MANDATO_DE_EXECUCAO.json'
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(instrucoes, f, indent=4, ensure_ascii=False)
            
        self.log_event(f"\n📋 Instrucoes de execucao tatica salvas no arquivo: {nome_arquivo}")

if __name__ == "__main__":
    # Para rodar BRL, basta passar BTCBRL
    import sys
    pair = "BTCBRL" if len(sys.argv) > 1 and "BRL" in sys.argv[1].upper() else "BTCUSDT"
    
    # Threshold default para 4% conforme pedido: "faixa dos 4%"
    yield_target = 0.04
    if len(sys.argv) > 2:
        try:
            yield_target = float(sys.argv[2])
        except:
            yield_target = 0.04

    scanner = ScannerCofreHibrido(asset_pair=pair, threshold_annual_yield=yield_target)
    scanner.escanear_continuamente()
