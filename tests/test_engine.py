"""Tests for the backtest engine and cost model."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.costs import CostModel
from src.backtest.engine import run_strategy_backtest
from src.signals.base import SignalResult


def _flat_term_structure(start: str, end: str, levels: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range(start, end)
    return pd.DataFrame({f"F{i}": v for i, v in enumerate(levels)}, index=dates)


class TestEngineNoLookahead:
    def test_first_day_zero_pnl(self, sample_config):
        """The very first day must have zero PnL — weights are not yet applied."""
        ts = {
            "CL": _flat_term_structure(
                "2020-01-01", "2020-03-01", [50, 50.1, 50.2, 50.3, 50.4]
            )
        }
        weights = pd.DataFrame(
            {"CL": [0.5] * len(ts["CL"])}, index=ts["CL"].index
        )
        sr = SignalResult(weights=weights, signal_values=weights, metadata={})

        cost_model = CostModel(sample_config)
        bt = run_strategy_backtest(sr, ts, cost_model, is_spread_trade=False)

        # First day's gross_return is built from a lagged (NaN→0) weight.
        assert bt["gross_return"].iloc[0] == 0


class TestCostModel:
    def test_default_spread(self, sample_config):
        cm = CostModel(sample_config)
        # CL not in overrides → default 2 bps
        assert cm.spread_cost_bps("CL", is_spread_trade=False) == 2.0
        # NG override → 3 bps
        assert cm.spread_cost_bps("NG", is_spread_trade=False) == 3.0

    def test_spread_discount_halves_cost(self, sample_config):
        cm = CostModel(sample_config)
        outright = cm.spread_cost_bps("CL", is_spread_trade=False)
        spread = cm.spread_cost_bps("CL", is_spread_trade=True)
        assert spread == outright * sample_config["costs"]["time_spread_discount"]

    def test_turnover_cost_zero_when_no_changes(self, sample_config):
        cm = CostModel(sample_config)
        idx = pd.bdate_range("2020-01-01", "2020-01-15")
        weights = pd.DataFrame({"CL": [0.5] * len(idx), "GC": [-0.5] * len(idx)}, index=idx)
        cost = cm.compute_turnover_cost(weights, is_spread_trade=False)
        # Static weights → no turnover cost on day 2 onwards (day 1 forced 0).
        assert (cost == 0).all()

    def test_turnover_cost_scales_with_change(self, sample_config):
        cm = CostModel(sample_config)
        idx = pd.bdate_range("2020-01-02", periods=8)
        weights = pd.DataFrame(
            {"CL": [0.0, 0.5, 0.5, 0.0, 0.0, 0.5, 0.5, 0.5]},
            index=idx,
        )
        cost = cm.compute_turnover_cost(weights, is_spread_trade=False)
        # Three transitions: 0→0.5 (day 1), 0.5→0 (day 3), 0→0.5 (day 5).
        # Each is a 0.5 weight change × 2 bps = 1e-4.
        nonzero = cost[cost > 0]
        assert len(nonzero) == 3
        assert np.isclose(nonzero.iloc[0], 0.5 * 2 / 10000)
