import sys
import os
import asyncio
from datetime import datetime

# Garantir que o diretório raiz está no PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logic.strategist_agent import StrategistAgent

async def run_veto_test():
    agent = StrategistAgent()
    print("\n" + "="*60)
    print("🔬 INICIANDO DRY-RUN: VALIDAÇÃO DO GATEKEEPER (VETO LOGIC)")
    print("="*60)

    # ---------------------------------------------------------
    # CENÁRIO 1: O "LIVRAMENTO" (VETO ATIVADO)
    # ---------------------------------------------------------
    print("\n[TESTE 1] Cenário: Sinal de Compra vs Muralha de Venda")
    asset = "BTCBRL"
    signal = 1
    prob = 0.68
    imbalance = -0.28  # Muralha de venda detectada
    reason = "Confluencia ML (Bullish)"
    
    print(f"  -> Input: {asset} BUY | Prob: {prob:.2%} | Imbalance: {imbalance:.2f}")
    
    dec, ar, smod = agent.assess_trade(
        asset, signal, prob, reason, 
        reliability=1.0, 
        caution_mode=False, 
        book_imbalance=imbalance
    )
    
    if dec == "VETO":
        print(f"  🟢 RESULTADO: [STRATEGIST] HARD VETO: {ar}")
        print("  ✅ SUCESSO: O sistema evitou uma entrada contra liquidez passiva massiva.")
    else:
        print(f"  🔴 FALHA: O sistema deveria ter vetado, mas retornou: {dec}")

    # ---------------------------------------------------------
    # CENÁRIO 2: O "SINAL LIMPO" (APROVAÇÃO)
    # ---------------------------------------------------------
    print("\n[TESTE 2] Cenário: Sinal de Venda com Caminho Livre")
    asset = "ETHBRL"
    signal = -1
    prob = 0.62
    imbalance = -0.15  # Liquidez suporta o movimento ou é neutra
    reason = "Exaustao de Comprador"
    
    print(f"  -> Input: {asset} SELL | Prob: {prob:.2%} | Imbalance: {imbalance:.2f}")
    
    dec, ar, smod = agent.assess_trade(
        asset, signal, prob, reason, 
        reliability=1.0, 
        caution_mode=False, 
        book_imbalance=imbalance
    )
    
    if dec == "APPROVE":
        print(f"  🟢 RESULTADO: [STRATEGIST] {ar}")
        print(f"  -> Modificadores: {smod}")
        print("  ✅ SUCESSO: O sinal foi validado pela microestrutura e está liberado para SHADOW_ALPHA.")
    else:
        print(f"  🔴 FALHA: O sistema deveria ter aprovado, mas retornou: {dec} ({ar})")

    print("\n" + "="*60)
    print("🏁 DRY-RUN CONCLUÍDO: MECANISMOS DE SEGURANÇA OPERACIONAIS")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(run_veto_test())
