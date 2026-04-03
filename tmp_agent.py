# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import json
import os
from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, END
from logic.macro_radar import MacroRadar
from logic.market_memory import MarketMemory

class StrategistState(TypedDict):
    signals: Dict[str, float] # { 'tier1': 0.05, 'tier2': 1, 'tier3': -1 }
    macro_data: Dict[str, float] 
    risk_score: float
    historical_conviction: float
    decision: str
    allocation_mult: float
    reasoning: List[str]

class StrategistAgent:
    """
    Orquestrador Agentico (LangGraph) que decide a estrategia global do bot.
    Inspirado na arquitetura flexivel do @redamon.
    """

    def __init__(self):
        self.radar = MacroRadar()
        self.memory = MarketMemory() # Knowledge retrieval layer
        self.workflow = self._build_workflow()

    def _build_workflow(self):
        builder = StateGraph(StrategistState)
        
        # 1. Analyse Macro
        builder.add_node("analyze_macro", self._node_analyze_macro)
        # 2. Query Memory (Analogy)
        builder.add_node("query_memory", self._node_query_memory)
        # 3. Triage Signals
        builder.add_node("triage_signals", self._node_triage_signals)
        # 4. Final Decision
        builder.add_node("make_decision", self._node_make_decision)
        
        builder.set_entry_point("analyze_macro")
        builder.add_edge("analyze_macro", "query_memory")
        builder.add_edge("query_memory", "triage_signals")
        builder.add_edge("triage_signals", "make_decision")
        builder.add_edge("make_decision", END)
        
        return builder.compile()

    def _node_analyze_macro(self, state: StrategistState):
        md = state['macro_data']
        news_sent = md.get('news_sentiment', 0.0) 
        score = self.radar.get_macro_score(md.get('dxy_change', 0), md.get('sp500_change', 0), news_sent)
        state['risk_score'] = score
        state['reasoning'].append(f"Macro Risk Score: {score:.2f}")
        return state

    def _node_query_memory(self, state: StrategistState):
        md = state['macro_data']
        conv = self.memory.get_historical_conviction(md.get('news_sentiment', 0.0), state['risk_score'])
        state['historical_conviction'] = conv
        state['reasoning'].append(f"Historical Conviction (Neo4j): {conv:.2f}")
        return state

    def _node_triage_signals(self, state: StrategistState):
        # Se o risco for altissimo, ignorar sinais direcionais (Tier 2/3)
        if state['risk_score'] < 0.25:
            state['reasoning'].append("⚠ Risco Sistemico: Ignorando sinais de Alpha Direcional.")
            state['signals']['tier2'] = 0 # Neutro por seguranca
            state['signals']['tier3'] = 0 # Neutro por seguranca
        return state

    def _node_make_decision(self, state: StrategistState):
        mult, msg = self.radar.get_recommended_position_mult()
        state['allocation_mult'] = mult
        
        # Logica de decisao
        if state['signals'].get('tier2', 0) != 0:
            state['decision'] = "EXECUTE_ALPHA"
        elif state['signals'].get('tier1', 0) > 0.05:
            state['decision'] = "EXECUTE_BASIS"
        else:
            state['decision'] = "WAIT"
            
        # Gravar na Memoria de Mercado (Neo4j)
        md = state['macro_data']
        self.memory.record_context_and_decision(
            md.get('news_sentiment', 0.0), 
            state['risk_score'], 
            state['decision']
        )
            
        state['reasoning'].append(f"Decisao: {state['decision']} | Multiplicador: {mult} ({msg})")
        return state

    def assess_trade(self, asset: str, signal: int, probability: float, reason: str):
        """
        Avalia um trade especifico com base na probabilidade do ML e contexto macro.
        Retorna: (decision, reason, modifiers)
        """
        modifiers = {
            'size_mult': 1.0,
            'tp_mult': 1.0,
            'sl_mult': 1.0
        }
        
        # 1. Filtro de Probabilidade
        if probability < 0.60:
            return "REJECT", f"Probabilidade insuficiente ({probability:.2f})", modifiers
            
        # 2. Ajuste por Conviccao
        if probability > 0.80:
            modifiers['size_mult'] *= 1.2
            modifiers['tp_mult'] *= 1.5 # Alvos mais longos em alta conviccao
            
        # 3. Filtro Macro (acesso direto ao radar)
        if self.radar.risk_score < 0.3 and signal == 1:
            return "REJECT", "Macro Risk Off (No Longs)", modifiers
            
        return "APPROVE", f"Aprovado: {reason}", modifiers

    def run(self, signals: Dict[str, float], macro_data: Dict[str, float]):
        initial_state = {
            "signals": signals,
            "macro_data": macro_data,
            "risk_score": 0.5,
            "historical_conviction": 0.5,
            "decision": "WAIT",
            "allocation_mult": 1.0,
            "reasoning": []
        }
        return self.workflow.invoke(initial_state)

    @property
    def intel(self):
        """Compatibility layer for legacy calls to self.agent.intel"""
        return self

    def get_summary(self):
        """Returns the current macro risk summary from the radar"""
        mult, msg = self.radar.get_recommended_position_mult()
        return {
            "risk_score": self.radar.risk_score,
            "recommendation": msg,
            "multiplier": mult
        }

    def assess_usdt_opportunity(self, signal: int, confidence: float, reason: str):
        """
        Decision gate for USDT/BRL safe harbor strategy.
        """
        # Logic: If macro risk is high (Risk Off) and we have a bullish USDT signal, approve
        if signal == 1 and self.radar.risk_score < 0.40:
             return "APPROVE", f"Safe Harbor: {reason}"
        
        # If it's a mean reversion play (USDT oversold)
        if signal == 1 and confidence > 0.75:
            return "APPROVE", f"Mean Reversion: {reason}"

        # If it's a sell signal (Risk On returning)
        if signal == -1:
            return "APPROVE", f"Exiting Safe Harbor: {reason}"

        return "REJECT", "Context not optimal for USDT", {}

if __name__ == "__main__":
    agent = StrategistAgent()
    res = agent.run(
        signals={'tier1': 0.08, 'tier2': 1}, 
        macro_data={'dxy_change': 0.01, 'sp500_change': -0.015} # Risk Off!
    )
    print(json.dumps(res, indent=2))
