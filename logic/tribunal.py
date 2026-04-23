class ConsensusTribunal:
    """
    Tribunal de Consenso: Agrega as decisoes do Modelo Live, Shadow e Ancestral.
    Implementa Voto Ponderado e Poder de Veto em regimes extremos.
    """
    def __init__(self, veto_threshold=0.015):
        # Threshold de volatilidade para ativar Veto Ancestral
        self.veto_threshold = veto_threshold

    def evaluate_signals(self, signals: dict, regime_metrics: dict, failure_risk: int = 0, macro_status: dict = None):
        """
        Avalia o conjunto de sinais e retorna a decisao final.
        
        Args:
            signals: { 'live': {sig, prob}, 'shadow': {sig, prob}, 'ancestral': {sig, prob} }
            regime_metrics: { 'vol': float, 'trend': float }
            failure_risk: Numero de falhas similares encontradas no Neo4j
            macro_status: { 'is_extreme': bool, 'reason': str }
            
        Returns:
            final_signal (int), confidence (float), reason (str)
        """
        # 1. VETO MACRO (Gatekeeper Global)
        if macro_status and macro_status.get('is_extreme'):
             live_info = signals.get('live') or {}
             live_sig = live_info.get('sig', 0)
             if live_sig == 1: # Bloqueia apenas compras (Risk-On) em cenario hostil
                 return 0, 0.1, f"VETO MACRO: {macro_status.get('reason', 'Não especificado')}"

        # 2. Veto por Analogia de Falha (Self-Correction)
        if failure_risk >= 2:
            return 0, 0.2, f"VETO DE PROBABILIDADE: Estado similar a {failure_risk} falhas passadas."

        live_info = signals.get('live') or {}
        shadow_info = signals.get('shadow') or {}
        ancestral_info = signals.get('ancestral') or {}
        
        live_sig = live_info.get('sig', 0)
        shadow_sig = shadow_info.get('sig', 0)
        ancestral_sig = ancestral_info.get('sig', 0)
        
        vol = regime_metrics.get('vol', 0.0)
        is_extreme_market = vol >= self.veto_threshold
        
        # 1. Poder de Veto Ancestral (Gatilho em Alta Volatilidade)
        if is_extreme_market:
            if ancestral_sig != live_sig and ancestral_sig != 0:
                # O Veterano (Ancestral) discorda do Live em momento critico
                return 0, 0.4, "VETO ANCESTRAL: Divergencia em Alta Volatilidade"
            elif ancestral_sig == 0 and live_sig != 0:
                # O Veterano prefere ficar de fora quando o Live quer entrar
                 return 0, 0.3, "VETO ANCESTRAL: Veterano recomenda cautela (Ficar de Fora)"

        # 2. Votacao Ponderada (Consenso Majoritario)
        all_sigs = [live_sig, shadow_sig, ancestral_sig]
        active_sigs = [s for s in all_sigs if s != 0]
        
        if not active_sigs:
            # Fallback for visibility: use live prob even if signal is 0
            live_info = signals.get('live') or {}
            live_prob = live_info.get('prob', 0.0)
            return 0, live_prob, "Consenso: Neutro"
            
        # Contagem de votos
        buy_votes = len([s for s in all_sigs if s == 1])
        sell_votes = len([s for s in all_sigs if s == -1])
        
        # Exige pelo menos 2 votos concordantes para um sinal forte
        if buy_votes >= 2:
            conf = 1.0 if buy_votes == 3 else 0.7
            return 1, conf, f"Consenso de Compra ({buy_votes}/3)"
        elif sell_votes >= 2:
            conf = 1.0 if sell_votes == 3 else 0.7
            return -1, conf, f"Consenso de Venda ({sell_votes}/3)"
            
        # Se houver conflito total (1, -1, 0), prevalece a seguranca
        if buy_votes == 1 and sell_votes == 1:
            return 0, 0.2, "CONFLITO: Modelos divergem completamente"
            
        # Se apenas 1 modelo votou (e os outros sao 0), sinal fraco
        if len(active_sigs) == 1:
            return active_sigs[0], 0.5, "Sinal Isolado (Sem Consenso)"
            
        return 0, 0.1, "Indecisao Colegiada"
