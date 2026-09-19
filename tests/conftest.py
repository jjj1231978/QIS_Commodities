"""Shared test fixtures — synthetic term structure data."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_term_structure():
    """Generate a synthetic term structure for one commodity.

    Simulates a market in mild contango (F0 < F1 < ... < F12)
    with some noise and a trend.
    """
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-01", "2023-12-31")
    n_days = len(dates)
    n_contracts = 13

    # Base price with a slow upward trend + noise
    base = 50 + np.cumsum(np.random.randn(n_days) * 0.3)

    # Term structure: mild contango (0.2% per contract month)
    data = {}
    for i in range(n_contracts):
        contango_factor = 1 + 0.002 * i
        noise = np.random.randn(n_days) * 0.1
        data[f"F{i}"] = base * contango_factor + noise

    df = pd.DataFrame(data, index=dates)
    df[df < 1] = 1  # no negative prices
    return df


@pytest.fixture
def synthetic_term_structures(synthetic_term_structure):
    """Dict of term structures for multiple commodities."""
    np.random.seed(123)
    structures = {"CL": synthetic_term_structure}

    # Add a few more with different characteristics
    for root, seed, trend, contango in [
        ("GC", 1, 0.1, 0.001),  # gold: slow trend, mild contango
        ("NG", 2, 0.5, 0.005),  # natgas: volatile, steep contango
        ("ZC", 3, 0.2, -0.001),  # corn: backwardation
        ("HG", 4, 0.3, 0.002),  # copper: contango
    ]:
        np.random.seed(seed)
        dates = synthetic_term_structure.index
        n_days = len(dates)
        base = 100 + np.cumsum(np.random.randn(n_days) * trend)

        data = {}
        for i in range(13):
            factor = 1 + contango * i
            noise = np.random.randn(n_days) * 0.05
            data[f"F{i}"] = base * factor + noise

        df = pd.DataFrame(data, index=dates)
        df[df < 1] = 1
        structures[root] = df

    return structures


@pytest.fixture
def sample_config():
    """Minimal config for testing."""
    return {
        "universe": {
            "commodities": {
                "energy": [
                    {"name": "WTI", "root": "CL", "exchange": "GLBX.MDP3",
                     "bcom_weight": 0.08, "months": "FGHJKMNQUVXZ", "seasonal": False},
                    {"name": "NatGas", "root": "NG", "exchange": "GLBX.MDP3",
                     "bcom_weight": 0.08, "months": "FGHJKMNQUVXZ", "seasonal": True},
                ],
                "grains": [
                    {"name": "Corn", "root": "ZC", "exchange": "GLBX.MDP3",
                     "bcom_weight": 0.06, "months": "HKNUZ", "seasonal": True},
                ],
                "base_metals": [
                    {"name": "Copper", "root": "HG", "exchange": "GLBX.MDP3",
                     "bcom_weight": 0.07, "months": "HKNUZ", "seasonal": False},
                ],
                "precious_metals": [
                    {"name": "Gold", "root": "GC", "exchange": "GLBX.MDP3",
                     "bcom_weight": 0.07, "months": "GJMQVZ", "seasonal": False},
                ],
            }
        },
        "data": {
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
            "max_contracts": 13,
            "roll_offset_days": -5,
        },
        "strategies": {
            "carry": {
                "enabled": True,
                "front_contract": 0,
                "deferred_contract": 3,
                "rebalance_freq": "monthly",
                "dollar_neutral": True,
            },
            "value": {
                "enabled": True,
                "ma_windows_years": [1, 2, 3],
                "n_long": 2,
                "n_short": 2,
                "rebalance_freq": "monthly",
            },
            "trend": {
                "enabled": True,
                "lookback_days": [21, 63, 126, 252],
                "sector_equal_weight": True,
                "rebalance_freq": "daily",
            },
            "congestion": {
                "enabled": True,
                "pre_roll_end_day": 4,
                "roll_start_day": 5,
                "roll_end_day": 9,
                "index": "BCOM",
            },
            "basis_momentum": {
                "enabled": True,
                "poly_order": 2,
                "slope_lookback_days": 63,
                "n_long": 2,
                "n_short": 2,
                "rebalance_freq": "monthly",
            },
        },
        "overlay": {
            "weighting": "equal",
            "vol_target": 0.05,
            "vol_lookback_days": 63,
        },
        "costs": {
            "default_spread_bps": 2.0,
            "spread_overrides": {"NG": 3.0},
            "time_spread_discount": 0.5,
            "commission_per_contract": 2.50,
        },
        "backtest": {
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
        },
    }
