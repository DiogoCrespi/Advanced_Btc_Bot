import pandas as pd
import numpy as np

class FundingLogic:
    def __init__(self, risk_free_rate_annual=0.10):
        """
        risk_free_rate_annual: Taxa livre de risco anualizada (ex: 0.10 para 10%).
        """
        self.risk_free_rate_annual = risk_free_rate_annual

    def calculate_annualized_funding(self, funding_rate_8h):
        """
        Converte a taxa de funding de 8h para anualizada.
        Cálculo: (1 + rate)^ (3 * 365) - 1  (Considerando juros compostos)
        Ou simplificado: rate * 3 * 365
        """
        annualized = funding_rate_8h * 3 * 365
        return annualized

    def get_signal(self, current_funding_8h, historical_fundings):
        """
        Retorna sinal de entrada/saída baseado na taxa anualizada.
        historical_fundings: lista ou série das últimas taxas para detectar negatividade persistente.
        """
        annualized = self.calculate_annualized_funding(current_funding_8h)
        
        # Regra de Entrada: Funding anualizado > taxa livre de risco
        if annualized > self.risk_free_rate_annual:
            return 1 # ENTRAR (Long Spot / Short Future)
            
        # Regra de Saída: Funding negativo persistente (5 ciclos)
        if len(historical_fundings) >= 5:
            last_5 = historical_fundings[-5:]
            if all(f < 0 for f in last_5):
                return 0 # SAIR
                
        return None
