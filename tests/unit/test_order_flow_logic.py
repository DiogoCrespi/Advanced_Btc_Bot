import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from logic.order_flow_logic import OrderFlowLogic

@pytest.fixture
def order_flow_logic():
    return OrderFlowLogic()

@pytest.fixture
def sample_data():
    dates = pd.date_range(start='2024-01-01', periods=5, freq='h')
    df = pd.DataFrame({
        'open': [100, 102, 101, 105, 104],
        'high': [105, 104, 103, 108, 106],
        'low': [95, 100, 99, 102, 101],
        'close': [102, 101, 102, 106, 105],
        'volume': [10, 20, 15, 30, 25]
    }, index=dates)
    return df

def test_calculate_avwap_basic(order_flow_logic, sample_data):
    anchor_time = pd.Timestamp('2024-01-01 02:00:00')
    result = order_flow_logic.calculate_avwap(sample_data, anchor_time)

    # Assert return type and index match
    assert isinstance(result, pd.Series)
    assert result.index.equals(sample_data.index)

    # Before anchor should be NaN
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])

    # Manual calculation from anchor (index 2) onwards
    # Index 2: (High+Low+Close)/3 = (103+99+102)/3 = 304/3 = 101.333
    # PV = 101.333 * 15 = 1520
    # AVWAP = 1520 / 15 = 101.333...
    assert result.iloc[2] == pytest.approx(101.333333)

    # Index 3: (High+Low+Close)/3 = (108+102+106)/3 = 316/3 = 105.333
    # PV = 105.333 * 30 = 3160. Cum_PV = 1520 + 3160 = 4680
    # Cum_Vol = 15 + 30 = 45
    # AVWAP = 4680 / 45 = 104.0
    assert result.iloc[3] == pytest.approx(104.0)

def test_calculate_avwap_anchor_before_data(order_flow_logic, sample_data):
    anchor_time = pd.Timestamp('2023-12-31')
    result = order_flow_logic.calculate_avwap(sample_data, anchor_time)

    assert isinstance(result, pd.Series)
    assert result.index.equals(sample_data.index)
    assert not result.isna().any() # All rows should have a value

def test_calculate_avwap_anchor_after_data(order_flow_logic, sample_data):
    anchor_time = pd.Timestamp('2024-01-02')
    result = order_flow_logic.calculate_avwap(sample_data, anchor_time)

    assert isinstance(result, pd.Series)
    assert result.index.equals(sample_data.index)
    assert result.isna().all() # Empty dataframe means all NaNs returned

def test_calculate_avwap_empty_dataframe(order_flow_logic):
    # To fix TypeError: '>=' not supported between instances of 'numpy.ndarray' and 'Timestamp'
    # we need an index of datetime type for the empty dataframe
    df = pd.DataFrame(
        columns=['open', 'high', 'low', 'close', 'volume'],
        index=pd.DatetimeIndex([])
    )
    anchor_time = pd.Timestamp('2024-01-01')

    result = order_flow_logic.calculate_avwap(df, anchor_time)

    assert isinstance(result, pd.Series)
    assert result.empty
