import json
import os
from datetime import datetime

class MarketMemory:
    def __init__(self, memory_file="results/market_memory.json"):
        self.memory_file = memory_file
        self.episodes = self.load_memory()
        
    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    return json.load(f)
            except: pass
        return []
        
    def save_memory(self):
        with open(self.memory_file, "w") as f:
            json.dump(self.episodes, f, indent=4)
            
    def record_episode(self, regime, volatility, outcome=None):
        """Records a market episode for future recall."""
        episode = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "regime": regime,
            "volatility": volatility,
            "outcome": outcome # To be updated later after trade closes
        }
        self.episodes.append(episode)
        if len(self.episodes) > 100: self.episodes.pop(0)
        self.save_memory()
        
    def recall_similar_regime(self, current_regime):
        """Finds historical outcomes for a similar regime."""
        matches = [e for e in self.episodes if e['regime'] == current_regime]
        if not matches: return None
        
        # Calculate success rate if outcomes are present
        outcomes = [e['outcome'] for e in matches if e['outcome'] is not None]
        if not outcomes: return None
        
        success_rate = sum(outcomes) / len(outcomes)
        return {
            "regime": current_regime,
            "match_count": len(matches),
            "historical_success_rate": round(success_rate, 2)
        }

if __name__ == "__main__":
    mem = MarketMemory()
    mem.record_episode("Risk-On", "High", outcome=1)
    mem.record_episode("Risk-On", "Low", outcome=0)
    print(f"Recall: {mem.recall_similar_regime('Risk-On')}")
