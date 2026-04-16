import unittest
import os
import sys

# Adicionar o caminho raiz do projeto
sys.path.append(os.getcwd())

from logic.risk_manager import RiskManager

class TestRiskMath(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager()
        # Mocking values for tests
        self.rm.stop_loss = 0.01
        self.rm.take_profit = 0.03

    def test_kelly_zero_edge(self):
        """Teste se Kelly retorna 0 quando nao ha vantagem estatistica (acuracia <= 50% com RR 1:1)"""
        # Se RR é 1:3 (0.01 loss vs 0.03 gain), o break-even é 25%. 
        # Com 20% de acurácia, Kelly deve ser 0.
        fraction = self.rm.calculate_kelly_fraction(accuracy=0.20)
        self.assertEqual(fraction, 0.0)

    def test_kelly_strong_edge(self):
        """Teste se Kelly sugere alocacao positiva com forte vantagem"""
        # p=0.7, b=3 (TP=0.03, SL=0.01)
        # Formula: (0.7 * (3+1) - 1) / 3 = (2.8 - 1) / 3 = 1.8 / 3 = 0.6
        # Com Kelly Fracionario (0.5x) e Ego (1.0x) = 0.3
        # Mas temos a trava max_kelly_cap = 0.10
        fraction = self.rm.calculate_kelly_fraction(accuracy=0.7)
        self.assertEqual(fraction, 0.10) # Deve bater na trava de 10%

    def test_bunker_allocation(self):
        """Teste se a alocacao Bunker responde corretamente ao risco macro"""
        # Risk 0.8 (Extreme) -> 90% Hedge
        hedge = self.rm.calculate_bunker_allocation(0.8)
        self.assertEqual(hedge, 0.90)
        
        # Risk 0.2 (Low) -> Desalocacao gradual (0% no longo prazo)
        # Note: A desalocação gradual subtrai 0.2 do target atual
        self.rm.target_hedge_pct = 0.6
        hedge = self.rm.calculate_bunker_allocation(0.2)
        self.assertAlmostEqual(hedge, 0.4)

    def test_ego_calibration(self):
        """Teste se o ego_multiplier reduz quando o bot esta super-confiante e errando"""
        self.rm.ego_multiplier = 1.0
        # Bot acha que acerta 80%, mas acerta 50% (Gap = 0.30)
        self.rm.calibrate_ego_buffer(realized_acc=0.5, expected_acc=0.8)
        self.assertLess(self.rm.ego_multiplier, 1.0)

if __name__ == "__main__":
    unittest.main()
