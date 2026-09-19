"""Backtest engine — converts signal weights to daily PnL."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.backtest.costs import CostModel
from src.signals.base import SignalResult

log = logging.getLogger(__name__)


def run_strategy_backtest(
    signal_result: SignalResult,
    term_structures: dict[str, pd.DataFrame],
    cost_model: CostModel,
    start_date: str | None = None,
    end_date: str | None = None,
    is_spread_trade: bool = False,
) -> pd.DataFrame:
    """Convert signal weights to daily excess returns.

    For carry/spread strategies, the return is from holding the spread
    (long deferred, short front). For directional strategies (trend, value),
    the return comes from F0 price changes.

    Args:
        signal_result: Output from a signal module.
        term_structures: Per-commodity term structure panels.
        cost_model: Transaction cost model.
        start_date: Backtest start (inclusive). If None, uses first available.
        end_date: Backtest end (inclusive). If None, uses last available.
        is_spread_trade: Whether this strategy trades time spreads.

    Returns:
        DataFrame with columns: gross_return, cost, net_return, turnover.
        Index is DatetimeIndex.
    """
    weights = signal_result.weights
    if weights.empty:
        return pd.DataFrame()

    # Trim to backtest window
    if start_date:
        weights = weights[weights.index >= start_date]
    if end_date:
        weights = weights[weights.index <= end_date]

    # Compute daily returns for each commodity. If the signal supplied its
    # own (e.g. carry beta-hedged or optimised variants), use those directly.
    if signal_result.daily_returns is not None:
        commodity_returns = signal_result.daily_returns.reindex(
            columns=weights.columns
        ).fillna(0.0)
    else:
        commodity_returns = _compute_commodity_returns(
            term_structures, weights.columns, signal_result.metadata, is_spread_trade
        )

    # Align dates
    common_dates = weights.index.intersection(commodity_returns.index)
    weights = weights.loc[common_dates]
    commodity_returns = commodity_returns.loc[common_dates]

    # Daily portfolio return = sum of (weight * commodity return)
    # Weights are from previous day (we enter at yesterday's close, earn today's return)
    lagged_weights = weights.shift(1).fillna(0.0)
    daily_returns = (lagged_weights * commodity_returns).sum(axis=1)

    # Transaction costs
    costs = cost_model.compute_turnover_cost(weights, is_spread_trade)
    costs = costs.loc[common_dates]

    # Turnover
    turnover = weights.diff().abs().sum(axis=1)

    result = pd.DataFrame(
        {
            "gross_return": daily_returns,
            "cost": costs,
            "net_return": daily_returns - costs,
            "turnover": turnover,
        },
        index=common_dates,
    )

    return result


def _compute_commodity_returns(
    term_structures: dict[str, pd.DataFrame],
    roots: pd.Index,
    metadata: dict,
    is_spread_trade: bool,
) -> pd.DataFrame:
    """Compute daily returns for each commodity.

    For spread trades (carry): return from the spread position.
    For directional trades: F0 daily return.
    """
    returns = {}

    for root in roots:
        if root not in term_structures:
            continue
        ts = term_structures[root]

        if is_spread_trade and "front_contract" in metadata:
            # Spread return: long deferred, short front
            front_col = f"F{metadata['front_contract']}"
            deferred_col = f"F{metadata['deferred_contract']}"

            if front_col in ts.columns and deferred_col in ts.columns:
                # Spread value = deferred - front
                spread = ts[deferred_col] - ts[front_col]
                # Normalize by front price for percentage return
                spread_pct = spread / ts[front_col]
                # Daily return = change in spread / front price
                ret = spread_pct.diff()
                returns[root] = ret
        else:
            # Directional: F0 daily percentage return
            if "F0" in ts.columns:
                returns[root] = ts["F0"].pct_change()

    if not returns:
        return pd.DataFrame()

    result = pd.DataFrame(returns)
    return result.fillna(0.0)
