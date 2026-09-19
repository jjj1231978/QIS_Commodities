"""Tests for performance metrics."""

import numpy as np
import pandas as pd
import pytest

from src.backtest.metrics import compute_diversification_ratio, compute_metrics


class TestComputeMetrics:
    def test_positive_returns(self):
        """Constant positive returns should give high SR, zero drawdown."""
        returns = pd.Series([0.001] * 252)  # 0.1% daily for a year
        m = compute_metrics(returns)

        assert m["annualized_return"] == pytest.approx(0.252, rel=0.01)
        assert m["sharpe_ratio"] > 10  # very high (no vol)
        assert m["max_drawdown"] == 0.0

    def test_zero_returns(self):
        """Zero returns should give zero everything."""
        returns = pd.Series([0.0] * 100)
        m = compute_metrics(returns)

        assert m["annualized_return"] == 0.0
        assert m["sharpe_ratio"] == 0.0

    def test_known_sharpe(self):
        """Test with known mean/vol to verify SR calculation."""
        np.random.seed(42)
        # Target: ~10% annual return, ~15% annual vol → SR ~0.67
        daily_mean = 0.10 / 252
        daily_vol = 0.15 / np.sqrt(252)
        returns = pd.Series(np.random.normal(daily_mean, daily_vol, 2520))

        m = compute_metrics(returns)
        assert 0.3 < m["sharpe_ratio"] < 1.5
        assert 0.05 < m["annualized_return"] < 0.20
        assert 0.10 < m["annualized_vol"] < 0.20

    def test_drawdown(self):
        """Large negative return should show up in max drawdown."""
        returns = pd.Series([0.01] * 50 + [-0.10] + [0.01] * 50)
        m = compute_metrics(returns)
        assert m["max_drawdown"] < -0.05

    def test_sortino_higher_than_sharpe_for_skewed(self):
        """Positively skewed returns should have Sortino > Sharpe."""
        np.random.seed(1)
        # Positive skew: mostly small gains, rare large gains
        returns = pd.Series(np.abs(np.random.randn(500)) * 0.01)
        m = compute_metrics(returns)
        # With all positive returns, downside vol is near zero → sortino very high
        assert m["sortino_ratio"] >= m["sharpe_ratio"]


class TestDiversificationRatio:
    def test_identical_returns(self):
        """Perfectly correlated strategies have DR = 1."""
        returns = pd.Series(np.random.randn(100) * 0.01)
        strategy_returns = {"A": returns, "B": returns}
        dr = compute_diversification_ratio(strategy_returns)
        assert dr == pytest.approx(1.0, abs=0.05)

    def test_uncorrelated_returns(self):
        """Uncorrelated strategies should have DR > 1."""
        np.random.seed(42)
        strategy_returns = {
            "A": pd.Series(np.random.randn(1000) * 0.01),
            "B": pd.Series(np.random.randn(1000) * 0.01),
            "C": pd.Series(np.random.randn(1000) * 0.01),
        }
        dr = compute_diversification_ratio(strategy_returns)
        assert dr > 1.3  # should be around sqrt(3) ≈ 1.73 for 3 uncorrelated

    def test_single_strategy(self):
        """Single strategy should have DR = 1."""
        returns = pd.Series(np.random.randn(100) * 0.01)
        dr = compute_diversification_ratio({"A": returns})
        assert dr == 1.0
