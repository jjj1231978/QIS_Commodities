"""Tests for the multi-strategy overlay portfolio."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.portfolio import build_overlay_portfolio


class TestOverlay:
    def test_realised_vol_close_to_target(self):
        """With a long enough warmup, realised vol should be near the target."""
        rng = np.random.default_rng(0)
        idx = pd.bdate_range("2015-01-01", "2024-12-31")
        # Three strategies with ~10% ann vol and zero correlation
        strat = {
            name: pd.Series(rng.standard_normal(len(idx)) * (0.10 / np.sqrt(252)), index=idx)
            for name in ("a", "b", "c")
        }

        target = 0.05
        overlay = build_overlay_portfolio(
            strat, weighting="equal", vol_target=target, vol_lookback=63
        )
        scaled = overlay["scaled_return"].dropna()
        # Skip the warmup (first ~252 obs) before measuring.
        realised_vol = scaled.iloc[252:].std() * np.sqrt(252)
        assert 0.85 * target < realised_vol < 1.20 * target

    def test_diversification(self):
        """Uncorrelated → diversification: portfolio vol < weighted avg vol."""
        rng = np.random.default_rng(1)
        idx = pd.bdate_range("2018-01-01", "2024-12-31")
        strat = {
            name: pd.Series(rng.standard_normal(len(idx)) * (0.10 / np.sqrt(252)), index=idx)
            for name in ("a", "b", "c", "d")
        }
        overlay = build_overlay_portfolio(strat, vol_target=0.05, vol_lookback=63)
        # Pre-vol-targeting: portfolio of independent equal-weight is 1/sqrt(N) of input vol.
        raw_vol = overlay["raw_return"].std() * np.sqrt(252)
        avg_input_vol = np.mean([s.std() * np.sqrt(252) for s in strat.values()])
        assert raw_vol < 0.7 * avg_input_vol  # ~ 0.5 in expectation (1/√4)

    def test_empty_input(self):
        out = build_overlay_portfolio({})
        assert out.empty

    def test_alignment_drops_misaligned_dates(self):
        idx_a = pd.bdate_range("2020-01-01", "2020-06-30")
        idx_b = pd.bdate_range("2020-04-01", "2020-12-31")
        strat = {
            "a": pd.Series(np.zeros(len(idx_a)), index=idx_a),
            "b": pd.Series(np.zeros(len(idx_b)), index=idx_b),
        }
        out = build_overlay_portfolio(strat, vol_target=0.05, vol_lookback=63)
        # Result should only span the intersection.
        assert out.index.min() >= max(idx_a.min(), idx_b.min())
        assert out.index.max() <= min(idx_a.max(), idx_b.max())
