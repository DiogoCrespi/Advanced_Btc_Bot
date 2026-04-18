import pytest
import os
import sqlite3
import pandas as pd
import numpy as np
from logic.database.ledger import Ledger
from logic.risk_manager import RiskManager
from data.data_engine import DataEngine

def test_ledger_initialization(tmp_path):
    db_file = tmp_path / "test_ledger.db"
    ledger = Ledger(db_path=str(db_file))
    
    assert os.path.exists(db_file)
    
    # Verify tables
    with sqlite3.connect(str(db_file)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        assert "balance_history" in tables
        assert "active_positions" in tables
        assert "trade_history" in tables

def test_ledger_balance_persistence(tmp_path):
    db_file = tmp_path / "test_ledger.db"
    ledger = Ledger(db_path=str(db_file))
    
    ledger.save_balance(1500.0, 1600.0, reason="DEPOSIT")
    last_balance = ledger.get_last_balance()
    
    assert last_balance == 1500.0

def test_data_engine_atr_calculation():
    engine = DataEngine()
    # Create mock OHLCV data
    data = {
        'high': [105, 110, 108, 115],
        'low':  [100, 102, 104, 106],
        'close': [102, 108, 106, 112]
    }
    df = pd.DataFrame(data)
    
    df = engine.apply_indicators(df)
    
    assert 'feat_atr' in df.columns
    # TR calculation check:
    # TR1: 105-100 = 5
    # TR2: max(110-102=8, abs(110-102)=8, abs(102-102)=0) = 8
    # TR3: max(108-104=4, abs(108-108)=0, abs(104-108)=4) = 4
    # TR4: max(115-106=9, abs(115-106)=9, abs(106-106)=0) = 9
    # Rolling mean (window 14) on only 4 rows will have mostly NaNs, but let's check with smaller window if we could.
    # Our implementation uses window=period (14).
    
def test_risk_manager_atr_stop():
    rm = RiskManager()
    rm.stop_loss = 0.05 # 5% fixed stop
    rm.atr_multiplier = 2.0
    
    # Situation: Price is 100, ATR is 5. 
    # ATR Stop = (5 * 2) / 100 = 10%.
    # Effective SL should be max(5%, 10%) = 10%.
    
    # Case 1: PnL is -6%. Should NOT trigger if ATR stop is 10%.
    action, reason = rm.check_exit_conditions(
        asset="BTCBRL",
        pos_id="1",
        current_price=94, # -6%
        entry_price=100,
        signal_direction=1,
        atr_value=5.0
    )
    assert action == "HOLD"
    
    # Case 2: PnL is -11%. Should trigger.
    action, reason = rm.check_exit_conditions(
        asset="BTCBRL",
        pos_id="1",
        current_price=89, # -11%
        entry_price=100,
        signal_direction=1,
        atr_value=5.0
    )
    assert action == "SELL"
    assert reason == "HARD_STOP_LOSS"

def test_risk_manager_ego_calibration():
    rm = RiskManager()
    rm.ego_multiplier = 1.0
    
    # Case 1: Bad performance (Accuracy 40% vs Expected 65%)
    rm.calibrate_ego_buffer(realized_acc=0.40, expected_acc=0.65)
    assert rm.ego_multiplier < 1.0
    
    # Case 2: Good performance (Accuracy 70% vs Expected 65%)
    current_ego = rm.ego_multiplier
    rm.calibrate_ego_buffer(realized_acc=0.70, expected_acc=0.65)
    assert rm.ego_multiplier >= current_ego

def test_ledger_performance(tmp_path):
    db_file = tmp_path / "test_ledger_perf.db"
    ledger = Ledger(db_path=str(db_file))
    
    # Insert 10 trades: 7 wins, 3 losses
    for i in range(7):
        ledger.record_completed_trade("BTC", "BUY", 100, 105, 1, 0.05, 5, "2026-01-01", "TP")
    for i in range(3):
        ledger.record_completed_trade("BTC", "BUY", 100, 95, 1, -0.05, -5, "2026-01-01", "SL")
        
    perf = ledger.get_recent_performance(limit=10)
    assert perf['accuracy'] == 0.7
    assert perf['count'] == 10
