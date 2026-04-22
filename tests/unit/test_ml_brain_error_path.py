import sys
import unittest
import os
from unittest.mock import MagicMock, patch

# Definimos os mocks que serao usados
mock_joblib = MagicMock()
mock_pd = MagicMock()
mock_np = MagicMock()
mock_sklearn = MagicMock()

class TestMLBrainErrorPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Usamos patch.dict para isolar as mudancas no sys.modules apenas para esta classe
        cls.module_patcher = patch.dict(sys.modules, {
            'joblib': mock_joblib,
            'pandas': mock_pd,
            'numpy': mock_np,
            'sklearn': mock_sklearn,
            'sklearn.ensemble': MagicMock(),
            'sklearn.metrics': MagicMock()
        })
        cls.module_patcher.start()
        
        # Import MLBrain after mocks are set up
        from logic.ml_brain import MLBrain
        cls.MLBrain = MLBrain

    @classmethod
    def tearDownClass(cls):
        cls.module_patcher.stop()

    def setUp(self):
        self.brain = self.MLBrain()

    @patch('logic.ml_brain.os.path.exists')
    def test_load_model_file_not_found(self, mock_exists):
        """Test load_model returns False if the file does not exist."""
        mock_exists.return_value = False
        result = self.brain.load_model("non_existent_model.pkl")
        self.assertFalse(result)
        mock_exists.assert_called_once_with("non_existent_model.pkl")

    @patch('logic.ml_brain.os.path.exists')
    @patch('logic.ml_brain.joblib.load')
    def test_load_model_corrupted_file(self, mock_joblib_load, mock_exists):
        """Test load_model returns False if joblib.load raises an exception."""
        mock_exists.return_value = True
        mock_joblib_load.side_effect = Exception("Pickle load error")

        result = self.brain.load_model("corrupted_model.pkl")
        self.assertFalse(result)
        mock_joblib_load.assert_called_once_with("corrupted_model.pkl")

    @patch('logic.ml_brain.os.path.exists')
    @patch('logic.ml_brain.joblib.load')
    def test_load_model_success(self, mock_joblib_load, mock_exists):
        """Happy Path: Test load_model returns True and sets attributes on success."""
        mock_exists.return_value = True
        mock_joblib_load.return_value = {
            'model': 'mock_model',
            'feature_cols': ['feat_1'],
            'is_trained': True,
            'reliability_score': 0.8,
            'atr_threshold': 0.5
        }

        result = self.brain.load_model("valid_model.pkl")
        self.assertTrue(result)
        self.assertEqual(self.brain.model, 'mock_model')
        self.assertEqual(self.brain.feature_cols, ['feat_1'])
        self.assertTrue(self.brain.is_trained)
        self.assertEqual(self.brain.reliability_score, 0.8)
        self.assertEqual(self.brain.atr_threshold, 0.5)

if __name__ == '__main__':
    unittest.main()
