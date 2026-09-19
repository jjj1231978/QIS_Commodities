"""Tests for the congestion (pre-roll) signal."""

from __future__ import annotations

import pandas as pd

from src.data.universe import Universe
from src.signals.congestion import CongestionSignal


class TestCongestionSignal:
    def test_basic_computation(self, synthetic_term_structures, sample_config):
        universe = Universe.from_config(sample_config)
        signal = CongestionSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        assert not result.weights.empty

    def test_zero_outside_roll_window(
        self, synthetic_term_structures, sample_config
    ):
        """Weights MUST be zero on business days outside BD 1..roll_end_day."""
        universe = Universe.from_config(sample_config)
        signal = CongestionSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        bday_of_month = result.signal_values["bday"]
        roll_end = sample_config["strategies"]["congestion"]["roll_end_day"]

        outside = bday_of_month[bday_of_month > roll_end].index
        outside = outside.intersection(result.weights.index)
        if not outside.empty:
            outside_weights = result.weights.loc[outside]
            assert (outside_weights == 0).all().all(), (
                "Congestion should be flat once BCOM has finished rolling"
            )

    def test_long_spread_during_roll_period(
        self, synthetic_term_structures, sample_config
    ):
        """BD 1..roll_end_day should hold a LONG (F1-F0) spread position.

        Two-basket pre-roll: long basket rolls before BD 5, short basket
        replicates BCOM's BD 5-9 roll. Net is long the front time spread,
        ramping from BD 1, peaking at BD pre_roll_end_day, then decaying
        to zero by BD roll_end_day.
        """
        universe = Universe.from_config(sample_config)
        signal = CongestionSignal(sample_config, universe)
        result = signal.compute(synthetic_term_structures)

        bday_of_month = result.signal_values["bday"]
        roll_end = sample_config["strategies"]["congestion"]["roll_end_day"]

        in_window = bday_of_month[
            (bday_of_month >= 1) & (bday_of_month <= roll_end)
        ].index
        in_window = in_window.intersection(result.weights.index)

        if not in_window.empty:
            window_weights = result.weights.loc[in_window]
            assert (window_weights >= 0).all().all()
            # And at least some entries are strictly positive.
            assert (window_weights > 0).any().any()
