# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pandas as pd
from datetime import datetime, timedelta

def compare_scenarios():
    # Capital de referencia: 1 BTC
    capital_btc = 1.0
    
    # Preco Spot Medio (R$)
    spot_brl = 388000
    
    # Dados extraidos do mercado real vs cenario teorico de 8%
    scenarios = [
        {
            "Nome": "🎯 Curto Prazo (Real)",
            "Yield Anual (%)": 4.04,
            "Dias para Vencimento": 11,
            "Contrato": "BTCUSD_260327"
        },
        {
            "Nome": "🛡 Longo Prazo (Cofre 8%)",
            "Yield Anual (%)": 8.00,
            "Dias para Vencimento": 102, # Exemplo Junho
            "Contrato": "BTCUSD_260626"
        },
        {
            "Nome": "💎 Maxima Eficiencia",
            "Yield Anual (%)": 12.00,
            "Dias para Vencimento": 284, # Dezembro
            "Contrato": "BTCUSD_251226"
        }
    ]
    
    results = []
    for s in scenarios:
        # ROI Absoluto = Yield * (Dias / 365)
        roi_abs = (s['Yield Anual (%)'] / 100) * (s['Dias para Vencimento'] / 365)
        
        # Lucro Bruto em Reais (estimado)
        lucro_brl = spot_brl * roi_abs
        
        # Lucro por Dia (Eficiencia Diaria)
        lucro_diario = lucro_brl / s['Dias para Vencimento']
        
        results.append({
            "Estrategia": s['Nome'],
            "Yield a.a.": f"{s['Yield Anual (%)']}%",
            "Dias": s['Dias para Vencimento'],
            "Lucro/BTC (R$)": f"R$ {lucro_brl:.2f}",
            "Eficiencia Diaria": f"R$ {lucro_diario:.2f}/dia"
        })
        
    df = pd.DataFrame(results)
    
    print("\n" + "="*70)
    print("📈 COMPARATIVO DE LUCRO: 4% (Curto) vs 8% (Longo)")
    print("="*70)
    print(df.to_string(index=False))
    print("="*70)
    
    print("\n💡 ANALISE TATICA:")
    print("1. O cenario de 4% paga menos 'no bolso' agora (R$ 472), mas libera o capital em 11 dias.")
    print("2. O cenario de 8% trava o capital por 100+ dias para ganhar R$ 8.6k.")
    print("3. CUSTO DE OPORTUNIDADE: Se voce fizer 10 ciclos de 11 dias a 4% (110 dias),")
    print("   voce ganharia ~R$ 4,720, o que ainda e MENOS que um unico ciclo de 8% longo.")
    print("4. CONCLUSAO: O yield de 8% e matematicamente superior no 'fio do bigode' (lucro real),")
    print("   mas o de 4% e imbativel para quem quer liquidez rapida.")
    print("="*70 + "\n")

if __name__ == "__main__":
    compare_scenarios()
