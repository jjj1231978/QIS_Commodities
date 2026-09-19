"""Congestion (pre-roll) strategy — front-run BCOM/GSCI index roll flows.

The reference paper (page 16-17) describes congestion as the difference between
two BCOM-weighted baskets:

    Long basket:  same composition as the benchmark, but rolled BEFORE BD 5
                  (we ramp evenly from BD 1 to `pre_roll_end_day`).
    Short basket: replicates the benchmark exactly, rolling BD 5-9 with
                  1/N of the position rolled per business day.

Outside the roll period the two baskets hold the same contracts and the
net position is zero. During pre-roll (BD 1..pre_roll_end_day), the long
basket is rolling while the short basket still holds the front contract,
so net = LONG (F1 - F0) per BCOM weight, scaled linearly. Once the long
basket is fully rolled (BD pre_roll_end_day .. roll_end_day), the short
basket is unwinding the position by buying F1 / selling F0, so net
linearly decays back to zero.

Why this earns money: BCOM's mechanical sell-F0/buy-F1 during BD 5-9
depresses F0 and lifts F1, widening (F1 - F0). Holding LONG the spread
through the roll captures that widening. The pre-roll positioning is
done at "fair" spread levels before the index pressure hits.

The spread is held with positive sign (long F1, short F0). Engine reads
front_contract=0, deferred_contract=1 from metadata to compute returns.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.signals.base import BaseSignal, SignalResult

log = logging.getLogger(__name__)


class CongestionSignal(BaseSignal):
    """Two-basket pre-roll strategy: LONG (F1-F0) spread during BD 1-9."""

    @property
    def name(self) -> str:
        return "congestion"

    def compute(self, term_structures: dict[str, pd.DataFrame]) -> SignalResult:
        cfg = self.config["strategies"]["congestion"]
        pre_roll_start = cfg.get("pre_roll_start_day", 1)
        pre_roll_end = cfg["pre_roll_end_day"]            # 4
        roll_start = cfg["roll_start_day"]                # 5
        roll_end = cfg["roll_end_day"]                    # 9

        # Collect every trading date across all commodities so the BD-of-month
        # index covers the union — individual commodities then just look up
        # their fraction at the dates they trade.
        all_dates = sorted({d for ts in term_structures.values() for d in ts.index})
        if not all_dates:
            return SignalResult(weights=pd.DataFrame(), signal_values=pd.DataFrame())
        dates_index = pd.DatetimeIndex(all_dates)
        bday_of_month = self._business_day_of_month(dates_index)

        spread_fraction = _spread_fraction(
            bday_of_month, pre_roll_start, pre_roll_end, roll_start, roll_end
        )

        bcom_weights = self.universe.weights()
        weights = pd.DataFrame(0.0, index=dates_index, columns=self.universe.roots)
        for root in self.universe.roots:
            if root not in term_structures or root not in bcom_weights.index:
                continue
            w = bcom_weights[root]
            valid_dates = dates_index.intersection(term_structures[root].index)
            weights.loc[valid_dates, root] = spread_fraction.loc[valid_dates] * w

        signal_df = pd.DataFrame(
            {"spread_fraction": spread_fraction, "bday": bday_of_month}
        )

        return SignalResult(
            weights=weights,
            signal_values=signal_df,
            metadata={
                "front_contract": 0,
                "deferred_contract": 1,
                "pre_roll_start": pre_roll_start,
                "pre_roll_end": pre_roll_end,
                "roll_start": roll_start,
                "roll_end": roll_end,
            },
        )

    @staticmethod
    def _business_day_of_month(dates: pd.DatetimeIndex) -> pd.Series:
        """1-indexed business-day-of-month for each date."""
        bday_num = pd.Series(0, index=dates, dtype=int)
        for (year, month), group in dates.to_series().groupby([dates.year, dates.month]):
            month_start = pd.Timestamp(year, month, 1)
            month_end = month_start + pd.offsets.MonthEnd(0)
            all_bdays = pd.bdate_range(month_start, month_end)
            for date in group:
                if date in all_bdays:
                    bday_num[date] = all_bdays.get_loc(date) + 1
        return bday_num


def _spread_fraction(
    bday: pd.Series,
    pre_roll_start: int,
    pre_roll_end: int,
    roll_start: int,
    roll_end: int,
) -> pd.Series:
    """Per-day net (long - short) basket spread fraction.

    Returns a Series of values in [0, 1] aligned to `bday.index`. Linearly
    ramps up from BD `pre_roll_start` to `pre_roll_end`, holds at 1.0 during
    BD `pre_roll_end` to `roll_start - 1` (long fully rolled, short still on
    front), then linearly decays to zero from BD `roll_start` to `roll_end`.
    """
    pre_roll_days = pre_roll_end - pre_roll_start + 1
    roll_days = roll_end - roll_start + 1

    out = pd.Series(0.0, index=bday.index)
    pre_mask = (bday >= pre_roll_start) & (bday <= pre_roll_end)
    out[pre_mask] = (bday[pre_mask] - pre_roll_start + 1) / pre_roll_days

    # Between pre_roll_end and roll_start (e.g. BD 4 only when roll_start=5),
    # both windows overlap at the boundary; the pre-roll mask already covers
    # BD pre_roll_end with fraction 1.0, so the gap (if any) stays 0 unless
    # explicitly held — paper's example has them adjacent (BD 4 -> BD 5).

    roll_mask = (bday >= roll_start) & (bday <= roll_end)
    # On BD roll_start: long basket = 1, short basket = 1/roll_days → net = 1 - 1/roll_days
    # On BD roll_end:   long basket = 1, short basket = 1                → net = 0
    out[roll_mask] = 1.0 - (bday[roll_mask] - roll_start + 1) / roll_days

    return out
