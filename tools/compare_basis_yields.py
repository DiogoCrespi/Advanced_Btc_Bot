# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.data_engine import DataEngine
from logic.basis_logic import BasisLogic
from datetime import datetime
import pandas as pd

def run_comparison():
    engine = DataEngine()
    logic = BasisLogic()
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] INICIANDO COMPARACAO DE YIELD (USD vs BRL)")
    print("="*60)
    
    # 1. Fetch contracts
    contracts = engine.fetch_delivery_contracts(asset="BTC")
    if not contracts:
        print("X Nenhum contrato encontrado.")
        return

    # Usaremos o contrato mais proximo para comparacao
    target_symbol = contracts[0]['symbol']
    expiry = logic.parse_expiry(target_symbol)
    
    print(f"Contrato Analisado: {target_symbol}")
    print(f"Data Vencimento: {expiry}")
    print("-" * 60)
    
    # 2. Fetch USD Basis
    usd_data = engine.fetch_basis_data(spot_symbol="BTCUSDT", delivery_symbol=target_symbol)
    usd_yield = logic.calculate_annualized_yield(usd_data['spot'], usd_data['future'], expiry) if usd_data else 0
    
    # 3. Fetch BRL Basis
    brl_data = engine.fetch_basis_data(spot_symbol="BTCBRL", delivery_symbol=target_symbol)
    brl_yield = logic.calculate_annualized_yield(brl_data['spot'], brl_data['future'], expiry) if brl_data else 0
    
    # 4. Results
    results = [
        {
            "Mercado": "USD (USDT)",
            "Preco Spot": f"US$ {usd_data['spot_raw']:.2f}" if usd_data else "N/A",
            "Yield Anualizado": f"{usd_yield * 100:.2f}%"
        },
        {
            "Mercado": "BRL (Reais)",
            "Preco Spot": f"R$ {brl_data['spot_raw']:.2f}" if brl_data else "N/A",
            "Yield Anualizado": f"{brl_yield * 100:.2f}%"
        }
    ]
    
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    
    print("-" * 60)
    
    # [MODULO CAMBIAL]
    forex = engine.fetch_forex_spread()
    if forex['valido']:
        print(f"| FOREX | Dolar Comercial (PTAX): R$ {forex['dolar_comercial']:.4f}")
        print(f"| FOREX | Dolar Cripto (Binance): R$ {forex['dolar_cripto']:.4f}")
        print(f"| FOREX | Spread (Agio Cambial) : {forex['agio_cambial_pct']*100:+.2f}%")
        print("-" * 60)
        
        if forex['agio_cambial_pct'] > 0.01:
            print(f"ALERTA TATICO: Agio massivo detectado! O Dolar Cripto esta {forex['agio_cambial_pct']*100:.2f}% mais caro.")
            print("RECOMENDACAO: Travar a operacao no mercado Spot BRL para extrair o spread como alpha adicional.")
            print("-" * 60)
            
    if brl_yield > usd_yield:
        diff = (brl_yield - usd_yield) * 100
        print(f"VENCEDOR ESTRUTURAL: MERCADO BRL (Reais) (Yield Basis: +{diff:.2f}%)")
    elif usd_yield > brl_yield:
        diff = (usd_yield - brl_yield) * 100
        print(f"VENCEDOR ESTRUTURAL: MERCADO USD (USDT) (Yield Basis: +{diff:.2f}%)")
    else:
        print("EMPATE TECNICO: Os rendimentos Basis estao identicos.")
        
    print("="*60 + "\n")

if __name__ == "__main__":
    run_comparison()
