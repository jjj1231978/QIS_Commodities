"""Tests for the backwardation-momentum signal."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.universe import Universe
from src.signals.backwardation_momentum import BackwardationMomentumSignal


class TestBackwardationMomentumSignal:
    def test_basic_computation(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        signal = BackwardationMomentumSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        assert not result.weights.empty

    def test_long_short_balanced(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        signal = BackwardationMomentumSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        nonzero = result.weights[(result.weights != 0).any(axis=1)]
        if nonzero.empty:
            return
        for _, row in nonzero.iterrows():
            assert abs(row.sum()) < 1e-9

    def test_backwardated_gets_long_weight(self, sample_config):
        """Highest F0/F12 ratio (backwardation) → long."""
        dates = pd.bdate_range("2020-01-01", "2023-12-31")

        # CL: backwardation — F0 well above F12.
        cl = pd.DataFrame(
            {f"F{i}": 100.0 - i * 1.5 + 0.0001 * np.arange(len(dates)) for i in range(13)},
            index=dates,
        )
        # GC: contango — F0 below F12.
        gc = pd.DataFrame(
            {f"F{i}": 100.0 + i * 1.5 + 0.0001 * np.arange(len(dates)) for i in range(13)},
            index=dates,
        )
        flat_a = pd.DataFrame({f"F{i}": 80 + 0.001 * i for i in range(13)}, index=dates)
        flat_b = pd.DataFrame({f"F{i}": 60 + 0.001 * i for i in range(13)}, index=dates)
        ts = {"CL": cl, "GC": gc, "NG": flat_a, "ZC": flat_b}

        universe = Universe.from_config(sample_config)
        result = BackwardationMomentumSignal(sample_config, universe).compute(ts)

        late = result.weights.iloc[-1]
        assert late["CL"] > 0  # backwardated → long
        assert late["GC"] < 0  # contango → short


class TestSkippedRebalanceHoldsPosition:
    """A rebalance that cannot rank must hold the previous book, not flatten it.

    Regression: `_rank_to_weights` used to allocate `pd.DataFrame(0.0, ...)`, so a
    rebalance skipped by the `len(row) < n_long + n_short` guard left an explicit
    zero row. The caller's ffill then propagated that zero, wiping the position
    until the next successful rebalance. With a shallow-curve universe this held
    backwardation momentum flat on 97.6% of days.
    """

    def _signal(self, sample_config):
        universe = Universe.from_config(sample_config)
        return BackwardationMomentumSignal(sample_config, universe)

    def test_skipped_rebalance_rows_are_dropped_not_zeroed(self, sample_config):
        cfg = sample_config.copy()
        cfg["strategies"]["backwardation_momentum"]["n_long"] = 2
        cfg["strategies"]["backwardation_momentum"]["n_short"] = 2
        signal = self._signal(cfg)

        rebal = pd.to_datetime(["2022-01-31", "2022-02-28", "2022-03-31"])
        cols = ["CL", "NG", "ZC", "GC"]
        sig = pd.DataFrame(1.0, index=rebal, columns=cols)
        sig.loc[rebal[0]] = [1.05, 1.02, 0.98, 0.95]
        sig.loc[rebal[1]] = [np.nan] * 4          # too few names -> skipped
        sig.loc[rebal[2]] = [0.95, 0.98, 1.02, 1.05]

        w = signal._rank_to_weights(sig, rebal, n_long=2, n_short=2)

        assert rebal[1] not in w.index, "skipped rebalance must be dropped, not zeroed"
        assert rebal[0] in w.index and rebal[2] in w.index
        assert not w.isna().any().any(), "successful rows must be fully specified"

    def test_position_persists_across_a_skipped_rebalance(self, sample_config):
        cfg = sample_config.copy()
        signal = self._signal(cfg)

        rebal = pd.to_datetime(["2022-01-31", "2022-02-28"])
        cols = ["CL", "NG", "ZC", "GC"]
        sig = pd.DataFrame(index=rebal, columns=cols, dtype=float)
        sig.loc[rebal[0]] = [1.05, 1.02, 0.98, 0.95]
        sig.loc[rebal[1]] = [np.nan] * 4          # skipped

        w = signal._rank_to_weights(sig, rebal, n_long=2, n_short=2)
        daily = pd.bdate_range("2022-01-31", "2022-03-15")
        held = w.reindex(daily, method="ffill").fillna(0.0)

        gross = held.abs().sum(axis=1)
        assert (gross > 0).all(), "book must stay invested through a skipped rebalance"
        assert held.loc["2022-03-01"].equals(held.loc[rebal[0]]), "must hold the prior allocation"

    def test_weights_stay_dollar_neutral_after_the_fix(self, sample_config):
        signal = self._signal(sample_config)
        rebal = pd.to_datetime(["2022-01-31"])
        cols = ["CL", "NG", "ZC", "GC"]
        sig = pd.DataFrame([[1.05, 1.02, 0.98, 0.95]], index=rebal, columns=cols)

        w = signal._rank_to_weights(sig, rebal, n_long=2, n_short=2)
        assert abs(w.loc[rebal[0]].sum()) < 1e-12
        assert abs(w.loc[rebal[0]].abs().sum() - 1.0) < 1e-12
