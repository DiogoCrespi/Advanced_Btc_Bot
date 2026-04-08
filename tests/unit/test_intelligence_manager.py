import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from logic.intelligence_manager import IntelligenceManager

@pytest.fixture
def intelligence_manager():
    return IntelligenceManager()

def test_fetch_macro_data_happy_path(intelligence_manager):
    """Test successful fetching and calculation of macro data."""
    # Create mock dataframe with 'Close' column
    mock_df = pd.DataFrame({'Close': [100.0, 105.0]})

    with patch('logic.intelligence_manager.yf.Ticker') as mock_ticker, \
         patch.object(intelligence_manager, 'fetch_news_sentiment') as mock_sentiment:

        # Configure the mock to return the dataframe when history() is called
        mock_ticker.return_value.history.return_value = mock_df

        # Configure mock sentiment
        mock_sentiment.return_value = {'signal': 'bullish', 'score': 0.8}

        result = intelligence_manager.fetch_macro_data()

        assert result is not None
        assert result['dxy_close'] == pytest.approx(105.0)
        assert result['dxy_change'] == pytest.approx(0.05) # (105/100) - 1
        assert result['gold_close'] == pytest.approx(105.0)
        assert result['gold_change'] == pytest.approx(0.05)
        assert result['sp500_close'] == pytest.approx(105.0)
        assert result['sp500_change'] == pytest.approx(0.05)
        assert result['news_sentiment'] == 0.8
        assert result['news_signal'] == 'bullish'
        assert 'timestamp' in result

        # Check cache was updated
        assert intelligence_manager.cache == result
        assert intelligence_manager.last_update is not None

def test_fetch_macro_data_empty_df(intelligence_manager):
    """Test handling of empty dataframe returned from yfinance."""
    mock_df_empty = pd.DataFrame()

    with patch('logic.intelligence_manager.yf.Ticker') as mock_ticker:
        mock_ticker.return_value.history.return_value = mock_df_empty

        result = intelligence_manager.fetch_macro_data()

        assert result is None
        assert intelligence_manager.cache == {}

def test_fetch_macro_data_exception(intelligence_manager):
    """Test handling of an exception raised during yfinance call."""
    with patch('logic.intelligence_manager.yf.Ticker') as mock_ticker:
        mock_ticker.side_effect = Exception("API error")

        result = intelligence_manager.fetch_macro_data()

        assert result is None
        assert intelligence_manager.cache == {}
