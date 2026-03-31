from logic.intelligence_manager import IntelligenceManager
from logic.mirofish_client import MiroFishClient
from datetime import datetime
import numpy as np

class StrategistAgent:
    def __init__(self):
        self.intel = IntelligenceManager()
        self.sentiment = MiroFishClient()
        self.reasoning_log = []
        
    def assess_trade(self, asset, ml_signal, ml_prob, ml_reason):
        """
        Calculates trade approval and modifiers (sizing, TP/SL).
        Returns: (decision, reasoning, modifiers)
        modifiers: { "size_mult": float, "tp_mult": float, "sl_mult": float }
        """
        if ml_signal == 0:
            return "REJECT", "ML signal is Neutral.", {"size_mult": 0, "tp_mult": 1, "sl_mult": 1}
            
        # 1. Fetch Context
        macro_summary = self.intel.get_summary()
        macro_risk    = macro_summary['risk_score']
        regime        = macro_summary['regime']
        news_score    = macro_summary.get('news_score', 0.0)
        
        # 2. Reasoning Loop
        logic_steps = []
        decision    = "APPROVE"
        
        # Base Modifiers
        size_mult = 1.0
        tp_mult   = 1.0
        sl_mult   = 1.0
        
        # A. ML Confidence & News Confluence
        logic_steps.append(f"ML Prob: {ml_prob:.1%}")
        if ml_prob > 0.85:
            size_mult += 0.3
            logic_steps.append("Ultra High ML confidence (+0.3 size)")
            
        # NEWS ALPHA INTEGRATION
        if (ml_signal == 1 and news_score > 0.4):
            size_mult += 0.5
            tp_mult   += 0.3
            logic_steps.append(f"📰 Turbo Buy Confluence: Strong Bullish News ({news_score:+.2f})")
        elif (ml_signal == -1 and news_score < -0.4):
            size_mult += 0.5
            tp_mult   += 0.3
            logic_steps.append(f"📰 Turbo Sell Confluence: Strong Bearish News ({news_score:+.2f})")
        
        # NEWS KILL SWITCH
        if (ml_signal == 1 and news_score < -0.6):
            decision = "REJECT"
            logic_steps.append(f"🛑 NEWS KILL SWITCH: ML wants Long but News is EXTREME BEARISH ({news_score:+.2f})")
        elif (ml_signal == -1 and news_score > 0.6):
            decision = "REJECT"
            logic_steps.append(f"🛑 NEWS KILL SWITCH: ML wants Short but News is EXTREME BULLISH ({news_score:+.2f})")

        # B. Macro Risk & Regime Adjustments
        if regime == "Risk-On / Weak Dollar":
            if ml_signal == 1:
                tp_mult += 0.3 # Extend TP in Risk-On
                logic_steps.append("Regime: Risk-On (Extending TP +0.3)")
            else:
                size_mult -= 0.2 # Be careful shorting in Risk-On
        elif regime == "Risk-Off / Strong Dollar":
            if ml_signal == 1:
                decision = "REJECT" if macro_risk > 0.75 else "WAIT"
                logic_steps.append(f"Risk-Off Pressure: {decision}")
            else:
                tp_mult += 0.2 # Shorts thrive here
                
        # C. Critical Aborts
        if ml_signal == 1 and macro_risk > 0.85:
            decision = "REJECT"
            logic_steps.append("ABORT: Extreme Macro Risk")
            
        # Clamp Multipliers
        size_mult = float(np.clip(size_mult, 0.2, 2.0))
        tp_mult   = float(np.clip(tp_mult, 0.5, 2.5))
        
        reasoning_str = " | ".join(logic_steps)
        modifiers = {
            "size_mult": size_mult,
            "tp_mult":   tp_mult,
            "sl_mult":   sl_mult
        }

        # Log for historical tracking
        log_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "asset": asset,
            "ml_signal": ml_signal,
            "decision": decision,
            "reasoning": reasoning_str,
            "modifiers": modifiers
        }
        self.reasoning_log.append(log_entry)
        if len(self.reasoning_log) > 100: self.reasoning_log.pop(0)
        
        return decision, reasoning_str, modifiers

    def get_latest_logs(self, limit=5):
        return self.reasoning_log[-limit:]

if __name__ == "__main__":
    agent = StrategistAgent()
    # Mocking a Buy signal from ML
    decision, reason = agent.assess_trade("BTCBRL", 1, 0.65, "Confluence (Compra)")
    print(f"--- STRATEGIST AGENT DECISION ---")
    print(f"Asset: BTCBRL")
    print(f"Decision: {decision}")
    print(f"Reasoning: {reason}")
