# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pytest
import sys
import os
import time
from unittest.mock import patch, MagicMock

# Adiciona o diretorio 'logic' ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logic')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from logic.coingecko_client import CoinGeckoClient

def test_get_btc_dominance_success():
    client = CoinGeckoClient()

    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'market_cap_percentage': {
                    'btc': 52.5
                }
            }
        }
        mock_get.return_value = mock_response

        dominance = client.get_btc_dominance()

        assert dominance == 52.5
        assert client.last_dominance == 52.5
        assert client.last_fetch_time > 0
        mock_get.assert_called_once()

def test_get_btc_dominance_caching():
    client = CoinGeckoClient(cache_timeout=180)

    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'market_cap_percentage': {
                    'btc': 53.0
                }
            }
        }
        mock_get.return_value = mock_response

        # Primeira chamada, deve fazer o request
        dominance1 = client.get_btc_dominance()
        assert dominance1 == 53.0
        assert mock_get.call_count == 1

        # Segunda chamada, deve usar o cache
        dominance2 = client.get_btc_dominance()
        assert dominance2 == 53.0
        assert mock_get.call_count == 1

def test_get_btc_dominance_http_error():
    client = CoinGeckoClient()
    client.last_dominance = 51.0 # Setar fallback

    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 429 # Too many requests
        mock_get.return_value = mock_response

        dominance = client.get_btc_dominance()

        # Deve retornar o ultimo fallback e nao deve alterar o tempo de fetch
        assert dominance == 51.0
        assert client.last_fetch_time == 0

def test_get_btc_dominance_exception():
    client = CoinGeckoClient()
    client.last_dominance = 49.5

    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Connection error")

        dominance = client.get_btc_dominance()

        # Deve retornar o ultimo fallback e capturar a exception graciosamente
        assert dominance == 49.5
        assert client.last_fetch_time == 0
