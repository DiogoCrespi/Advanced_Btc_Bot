# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pandas as pd
import numpy as np

class MacroRadar:
    """
    Monitora o sentimento macro do mercado (Beta Filter):
    - Correlacao BTC/DXY (Inversa)
    - Correlacao BTC/S&P 500 (Direta/Risk-On)
    - Correlacao BTC/Ouro (Hedge/Safe Haven)
    """

    def __init__(self):
        self.risk_score = 0.5 
        self.dxy_weight = 0.35
        self.sp500_weight = 0.35
        self.gold_weight = 0.15
        self.news_weight = 0.15
        
        # Limites de Veto (Macro Safety Gate)
        self.dxy_veto_threshold = 0.005 # +0.5% em 24h
        self.sp500_veto_threshold = -0.01 # -1.0% em 24h

    def get_macro_score(self, dxy_change, sp500_change, gold_change, news_sentiment):
        """Calcula o Macro Risk Score (0.0 a 1.0)."""
        
        # 1. DXY (Inverse)
        dxy_score = 0.5 - (dxy_change * 10.0) # Mais sensivel ao rali do dolar
        dxy_score = max(0.0, min(1.0, dxy_score))

        # 2. S&P 500 (Positive)
        sp500_score = 0.5 + (sp500_change * 5.0)
        sp500_score = max(0.0, min(1.0, sp500_score))
        
        # 3. Gold (Hedge - Ponderacao menor, mas relevante em crise)
        gold_score = 0.5 + (gold_change * 5.0)
        gold_score = max(0.0, min(1.0, gold_score))
        
        # 4. News Sentiment
        news_score = (news_sentiment + 1) / 2.0
        
        final_score = (dxy_score * self.dxy_weight) + \
                      (sp500_score * self.sp500_weight) + \
                      (gold_score * self.gold_weight) + \
                      (news_score * self.news_weight)
                      
        self.risk_score = final_score
        return final_score

    def is_risk_off_extreme(self, dxy_change, sp500_change):
        """Detecta se o cenario global e hostil para ativos de risco."""
        if dxy_change >= self.dxy_veto_threshold:
            return True, f"DXY RIPPING: Dolar subindo {dxy_change:.2%}"
        if sp500_change <= self.sp500_veto_threshold:
            return True, f"SP500 DUMPING: Mercado de acoes caindo {sp500_change:.2%}"
        return False, None

    def get_recommended_position_mult(self):
        """Retorna mult de posicao baseado no score macro."""
        if self.risk_score < 0.35:
            return 0.4, "⚠ Macro Risk Off: Protecao de Capital"
        elif self.risk_score > 0.65:
            return 1.3, "🚀 Macro Risk On: Agressividade Moderada"
        else:
            return 1.0, "⚖ Macro Neutro: Mao Padrao"

if __name__ == "__main__":
    radar = MacroRadar()
    # Simulacao: DXY subiu 0.5%, S&P 500 subiu 1%, Noticias Neutras (0)
    score = radar.get_macro_score(0.005, 0.01, 0)
    mult, reason = radar.get_recommended_position_mult()
    print(f"Macro Score: {score:.2f} | Multiplicador: {mult} | Razao: {reason}")
