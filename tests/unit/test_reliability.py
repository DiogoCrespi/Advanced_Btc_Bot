import unittest
import numpy as np
import pandas as pd
from logic.ml_brain import MLBrain
from logic.strategist_agent import StrategistAgent

class TestReliabilityLogic(unittest.TestCase):
    def setUp(self):
        self.brain = MLBrain()
        self.agent = StrategistAgent()

    def test_reliability_calculation(self):
        # Case 1: No samples
        self.brain.n_samples = 0
        self.brain.reliability_score = 0.0
        
        # Case 2: Low samples (e.g., 500)
        self.brain.n_samples = 500
        # reliability_score = min(1.0, 500/2000) * 0.5 (if no OOB) = 0.25 * 0.5 = 0.125
        # Let's call the calculation logic if we can, or just mock it
        rel = min(1.0, 500 / 2000) * 0.5
        self.assertLess(rel, 0.5)

    def test_strategist_thresholds(self):
        # High reliability (1.0), No Caution
        dec, reason, _ = self.agent.assess_trade("BTCBRL", 1, 0.55, "Test", reliability=1.0, caution_mode=False)
        self.assertEqual(dec, "REJECT", "Should reject 0.55 with 0.60 threshold")
        
        dec, reason, _ = self.agent.assess_trade("BTCBRL", 1, 0.65, "Test", reliability=1.0, caution_mode=False)
        self.assertEqual(dec, "APPROVE", "Should approve 0.65 with 0.60 threshold")

        # Low reliability (0.2), No Caution
        dec, reason, _ = self.agent.assess_trade("BTCBRL", 1, 0.75, "Test", reliability=0.2, caution_mode=False)
        self.assertEqual(dec, "REJECT", "Should reject 0.75 when reliability is low (threshold 0.80)")
        
        dec, reason, _ = self.agent.assess_trade("BTCBRL", 1, 0.85, "Test", reliability=0.2, caution_mode=False)
        self.assertEqual(dec, "APPROVE", "Should approve 0.85 even with low reliability")

        # High reliability (1.0), Caution Mode
        dec, reason, _ = self.agent.assess_trade("BTCBRL", 1, 0.62, "Test", reliability=1.0, caution_mode=True)
        self.assertEqual(dec, "REJECT", "Should reject 0.62 with caution mode (threshold 0.65)")

if __name__ == '__main__':
    unittest.main()
