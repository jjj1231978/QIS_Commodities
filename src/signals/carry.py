"""Carry strategy — monetise commodity term structure via convenience yield.

The reference paper presents four implementations of carry, summarised in its
Table 1 (page 8):

    Variant                       Sharpe (paper)
    F3-F0 (BCOM)                  1.75
    F6-F0 (BCOM)                  1.58
    F6-F0 (BCOM, beta hedged)     1.86
    Optimised contracts (BCOM)    1.96

All four short the front contract and go long a deferred contract,
weighted by BCOM. They differ in the choice of deferred contract and
how the directional exposure to the underlying is treated:

    fixed_pair   long F<deferred>, short F<front>, dollar-equal split.
    beta_hedged  same legs as fixed_pair, but the short leg is scaled by
                 a rolling beta so the spread is orthogonal to the front
                 contract's daily moves.
    optimised    per-commodity ex-ante search picks the best (front,
                 deferred) pair from candidates by realized Sharpe over a
                 lookback window, recomputed at each rebalance.

Configure via `strategies.carry.variant` in the YAML config.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.signals.base import BaseSignal, SignalResult

log = logging.getLogger(__name__)


class CarrySignal(BaseSignal):
    """Commodity carry: long deferred, short front, dollar-neutral."""

    @property
    def name(self) -> str:
        cfg = self.config["strategies"]["carry"]
        # Allow callers to instantiate the same class against a non-default
        # config section by passing config["strategies"]["carry_f6"] etc.
        # The display name comes from cfg["name"] when set.
        return cfg.get("name", "carry")

    def compute(self, term_structures: dict[str, pd.DataFrame]) -> SignalResult:
        cfg = self._cfg()
        variant = cfg.get("variant", "fixed_pair")

        if variant == "fixed_pair":
            return self._compute_fixed_pair(term_structures, cfg)
        if variant == "beta_hedged":
            return self._compute_beta_hedged(term_structures, cfg)
        if variant == "optimised":
            return self._compute_optimised(term_structures, cfg)
        raise ValueError(f"Unknown carry variant: {variant!r}")

    def _cfg(self) -> dict:
        # Sub-classes (CarryF6, CarryBetaHedged, CarryOptimised) read from a
        # different config key. The base reads strategies.carry.
        return self.config["strategies"][self._cfg_key()]

    def _cfg_key(self) -> str:
        return "carry"

    # ------------------------------------------------------------------
    # Variant: fixed pair (F3-F0 or F6-F0)
    # ------------------------------------------------------------------
    def _compute_fixed_pair(
        self, term_structures: dict[str, pd.DataFrame], cfg: dict
    ) -> SignalResult:
        front = cfg["front_contract"]
        deferred = cfg["deferred_contract"]

        carry_signals, _, _ = _per_commodity_carry(
            term_structures, self.universe.roots, front, deferred
        )
        if not carry_signals:
            return SignalResult(weights=pd.DataFrame(), signal_values=pd.DataFrame())

        signal_df = pd.DataFrame(carry_signals).sort_index()
        rebal_dates = _rebalance_dates(signal_df, cfg["rebalance_freq"])
        weights = _dollar_neutral_weights(signal_df, rebal_dates, self.universe.weights())
        weights_daily = weights.reindex(signal_df.index, method="ffill").fillna(0.0)

        return SignalResult(
            weights=weights_daily,
            signal_values=signal_df,
            metadata={
                "variant": "fixed_pair",
                "front_contract": front,
                "deferred_contract": deferred,
            },
        )

    # ------------------------------------------------------------------
    # Variant: beta-hedged (default F6-F0)
    # ------------------------------------------------------------------
    def _compute_beta_hedged(
        self, term_structures: dict[str, pd.DataFrame], cfg: dict
    ) -> SignalResult:
        front = cfg["front_contract"]
        deferred = cfg["deferred_contract"]
        beta_lookback = cfg.get("beta_lookback_days", 252)

        carry_signals, daily_returns, _ = _per_commodity_carry(
            term_structures,
            self.universe.roots,
            front,
            deferred,
            beta_lookback=beta_lookback,
        )
        if not carry_signals:
            return SignalResult(weights=pd.DataFrame(), signal_values=pd.DataFrame())

        signal_df = pd.DataFrame(carry_signals).sort_index()
        rebal_dates = _rebalance_dates(signal_df, cfg["rebalance_freq"])
        weights = _dollar_neutral_weights(signal_df, rebal_dates, self.universe.weights())
        weights_daily = weights.reindex(signal_df.index, method="ffill").fillna(0.0)
        returns_df = pd.DataFrame(daily_returns).reindex(signal_df.index)

        return SignalResult(
            weights=weights_daily,
            signal_values=signal_df,
            metadata={
                "variant": "beta_hedged",
                "front_contract": front,
                "deferred_contract": deferred,
                "beta_lookback_days": beta_lookback,
            },
            daily_returns=returns_df,
        )

    # ------------------------------------------------------------------
    # Variant: optimised contracts
    # ------------------------------------------------------------------
    def _compute_optimised(
        self, term_structures: dict[str, pd.DataFrame], cfg: dict
    ) -> SignalResult:
        candidates: list[tuple[int, int]] = [tuple(p) for p in cfg["candidate_pairs"]]
        warmup_days = cfg.get("optimisation_warmup_days", 504)

        # 1. Pick the best (front, deferred) per commodity using only the
        #    pre-warmup window. This is in-sample to that window but
        #    out-of-sample for the live backtest period.
        best_pairs: dict[str, tuple[int, int]] = {}
        for root in self.universe.roots:
            if root not in term_structures:
                continue
            ts = term_structures[root]
            if len(ts) < warmup_days + 60:
                continue
            warmup_ts = ts.iloc[:warmup_days]

            best_sr = -np.inf
            best_pair: tuple[int, int] | None = None
            for front, deferred in candidates:
                front_col, deferred_col = f"F{front}", f"F{deferred}"
                if front_col not in ts.columns or deferred_col not in ts.columns:
                    continue
                spread = (warmup_ts[deferred_col] - warmup_ts[front_col]) / warmup_ts[front_col]
                ret = spread.diff().dropna()
                # Rough SR of being long the spread when carry is positive
                # (i.e., backwardation pays out). Use sign of (deferred-front)
                # to direction-trade; reward if directional return is positive.
                sgn = -np.sign((warmup_ts[deferred_col] - warmup_ts[front_col]).reindex(ret.index))
                directional = (sgn * ret).dropna()
                if len(directional) < 60 or directional.std() == 0:
                    continue
                sr = directional.mean() / directional.std() * np.sqrt(252)
                if sr > best_sr:
                    best_sr, best_pair = sr, (front, deferred)
            if best_pair is not None:
                best_pairs[root] = best_pair

        if not best_pairs:
            return SignalResult(weights=pd.DataFrame(), signal_values=pd.DataFrame())

        # 2. Compute carry signals + daily returns using each commodity's
        #    chosen pair. Pairs vary by commodity, so we compute manually.
        carry_signals: dict[str, pd.Series] = {}
        daily_returns: dict[str, pd.Series] = {}
        for root, (front, deferred) in best_pairs.items():
            ts = term_structures[root]
            front_col, deferred_col = f"F{front}", f"F{deferred}"
            if front_col not in ts.columns or deferred_col not in ts.columns:
                continue
            carry_signals[root] = (ts[deferred_col] - ts[front_col]) / ts[front_col]
            spread = (ts[deferred_col] - ts[front_col]) / ts[front_col]
            daily_returns[root] = spread.diff()

        signal_df = pd.DataFrame(carry_signals).sort_index()
        rebal_dates = _rebalance_dates(signal_df, cfg["rebalance_freq"])
        weights = _dollar_neutral_weights(signal_df, rebal_dates, self.universe.weights())
        weights_daily = weights.reindex(signal_df.index, method="ffill").fillna(0.0)
        returns_df = pd.DataFrame(daily_returns).reindex(signal_df.index)

        return SignalResult(
            weights=weights_daily,
            signal_values=signal_df,
            metadata={
                "variant": "optimised",
                "per_commodity_pairs": best_pairs,
                "warmup_days": warmup_days,
            },
            daily_returns=returns_df,
        )


# ----------------------------------------------------------------------
# Helpers shared by all four variants
# ----------------------------------------------------------------------
def _per_commodity_carry(
    term_structures: dict[str, pd.DataFrame],
    roots,
    front: int,
    deferred: int,
    beta_lookback: int | None = None,
) -> tuple[dict[str, pd.Series], dict[str, pd.Series], dict[str, pd.Series]]:
    """Compute carry signal and (optionally) beta-hedged daily returns.

    Returns:
        carry_signals: per-commodity (F_deferred - F_front) / F_front Series.
        daily_returns: per-commodity beta-hedged daily return Series, or
            empty dict if `beta_lookback` is None.
        betas: rolling beta Series per commodity (diagnostic).
    """
    front_col, deferred_col = f"F{front}", f"F{deferred}"
    carry_signals: dict[str, pd.Series] = {}
    daily_returns: dict[str, pd.Series] = {}
    betas: dict[str, pd.Series] = {}

    for root in roots:
        if root not in term_structures:
            continue
        ts = term_structures[root]
        if front_col not in ts.columns or deferred_col not in ts.columns:
            continue

        front_px = ts[front_col]
        deferred_px = ts[deferred_col]
        carry_signals[root] = (deferred_px - front_px) / front_px

        if beta_lookback is None:
            continue

        r_front = front_px.pct_change()
        r_deferred = deferred_px.pct_change()
        cov = r_deferred.rolling(beta_lookback).cov(r_front)
        var = r_front.rolling(beta_lookback).var()
        beta = (cov / var).replace([np.inf, -np.inf], np.nan)
        betas[root] = beta
        # Beta-hedged spread return: long deferred, short beta * front
        daily_returns[root] = r_deferred - beta * r_front

    return carry_signals, daily_returns, betas


def _rebalance_dates(signal_df: pd.DataFrame, freq: str) -> pd.DatetimeIndex:
    if freq == "monthly":
        return signal_df.resample("BME").last().index
    if freq == "weekly":
        return signal_df.resample("W-FRI").last().index
    return signal_df.index


def _dollar_neutral_weights(
    signal_df: pd.DataFrame,
    rebal_dates: pd.DatetimeIndex,
    bcom_weights: pd.Series,
) -> pd.DataFrame:
    """Sign-of-carry × BCOM weight, normalised to long sum = +0.5 / short = -0.5."""
    weights = pd.DataFrame(index=rebal_dates, columns=signal_df.columns, dtype=float)

    for date in rebal_dates:
        if date not in signal_df.index:
            continue

        signals = signal_df.loc[date].dropna()
        if signals.empty:
            continue

        available_roots = signals.index.intersection(bcom_weights.index)
        if available_roots.empty:
            continue

        sig = signals[available_roots]
        w = bcom_weights[available_roots]

        # Carry < 0 (backwardation) → long deferred, short front → +sign weight.
        raw = -sig.apply(np.sign) * w

        long_sum = raw[raw > 0].sum()
        short_sum = abs(raw[raw < 0].sum())

        if long_sum > 0 and short_sum > 0:
            raw[raw > 0] *= 0.5 / long_sum
            raw[raw < 0] *= 0.5 / short_sum

        weights.loc[date, available_roots] = raw

    return weights.fillna(0.0)


# ----------------------------------------------------------------------
# Class-per-variant wrappers so each can be registered separately in main
# ----------------------------------------------------------------------
class CarryF6(CarrySignal):
    @property
    def name(self) -> str:
        return "carry_f6"

    def _cfg_key(self) -> str:
        return "carry_f6"


class CarryBetaHedged(CarrySignal):
    @property
    def name(self) -> str:
        return "carry_beta_hedged"

    def _cfg_key(self) -> str:
        return "carry_beta_hedged"


class CarryOptimised(CarrySignal):
    @property
    def name(self) -> str:
        return "carry_optimised"

    def _cfg_key(self) -> str:
        return "carry_optimised"
