# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pandas as pd
import numpy as np

class MacroRadar:
    """
    Inspirado no @worldmonitor, monitora o sentimento macro do mercado:
    - Correlacao BTC/DXY (Dolar Forte -> Crypto Fraco)
    - Correlacao BTC/S&P 500 (Risk-On / Risk-Off)
    - Sentimento de Noticias (CPI, Taxa de Juros)
    """

    def __init__(self):
        self.risk_score = 0.5 # Neutro inicial (0=Risk Off, 1=Risk On)
        self.dxy_weight = 0.3
        self.sp500_weight = 0.3
        self.news_weight = 0.4

    def get_macro_score(self, dxy_change, sp500_change, news_sentiment):
        """
        Calcula o Macro Risk Score (0.0 a 1.0).
        - dxy_change: Mudanca % do Dolar (Inverso ao Risco)
        - sp500_change: Mudanca % das Acoes (Positivo ao Risco)
        - news_sentiment: Score IA das noticias (-1 a 1)
        """
        
        # 1. DXY (Inverse: DXY up -> Risk Score Down)
        # Se Dolar sobe mais de 1%, o risco aumenta (score diminui)
        dxy_score = 0.5 - (dxy_change * 5.0)
        dxy_score = max(0.0, min(1.0, dxy_score))

        # 2. S&P 500 (Positive: SP500 up -> Risk Score Up)
        sp500_score = 0.5 + (sp500_change * 5.0)
        sp500_score = max(0.0, min(1.0, sp500_score))
        
        # 3. News Sentiment (-1 a 1 mapped to 0 a 1)
        news_score = (news_sentiment + 1) / 2.0
        
        final_score = (dxy_score * self.dxy_weight) + \
                      (sp500_score * self.sp500_weight) + \
                      (news_score * self.news_weight)
                      
        self.risk_score = final_score
        return final_score

    def get_recommended_position_mult(self):
        """
        Recomenda multiplicador de mao baseado no risco macro.
        - Risk < 0.3 (Escuro): Reduzir mao em 70% (Mao 0.3)
        - Risk 0.3 a 0.7: Mao Normal (Mao 1.0)
        - Risk > 0.7 (Rally): Mao Agressiva (Mao 1.2 a 1.5)
        """
        if self.risk_score < 0.3:
            return 0.3, "⚠ Macro Risk Off: Protecao de Capital"
        elif self.risk_score > 0.7:
            return 1.4, "🚀 Macro Risk On: Agressividade Alta"
        else:
            return 1.0, "⚖ Macro Neutro: Mao Padrao"

if __name__ == "__main__":
    radar = MacroRadar()
    # Simulacao: DXY subiu 0.5%, S&P 500 subiu 1%, Noticias Neutras (0)
    score = radar.get_macro_score(0.005, 0.01, 0)
    mult, reason = radar.get_recommended_position_mult()
    print(f"Macro Score: {score:.2f} | Multiplicador: {mult} | Razao: {reason}")
