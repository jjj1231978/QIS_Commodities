"""Performance metrics for strategy evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(returns: pd.Series, annualization: float = 252.0) -> dict:
    """Compute standard performance metrics from daily returns.

    Args:
        returns: Daily return series (not cumulative).
        annualization: Trading days per year.

    Returns:
        Dict with: annualized_return, annualized_vol, sharpe_ratio,
        max_drawdown, calmar_ratio, sortino_ratio.
    """
    if returns.empty or returns.std() == 0:
        return {
            "annualized_return": 0.0,
            "annualized_vol": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "calmar_ratio": 0.0,
            "sortino_ratio": 0.0,
        }

    ann_return = returns.mean() * annualization
    ann_vol = returns.std() * np.sqrt(annualization)
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0

    # Max drawdown
    cum_returns = (1 + returns).cumprod()
    running_max = cum_returns.cummax()
    drawdowns = cum_returns / running_max - 1
    max_dd = drawdowns.min()

    # Calmar ratio
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0.0

    # Sortino ratio (downside deviation)
    downside = returns[returns < 0]
    downside_vol = downside.std() * np.sqrt(annualization) if len(downside) > 0 else ann_vol
    sortino = ann_return / downside_vol if downside_vol > 0 else 0.0

    return {
        "annualized_return": ann_return,
        "annualized_vol": ann_vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "calmar_ratio": calmar,
        "sortino_ratio": sortino,
    }


def compute_diversification_ratio(
    strategy_returns: dict[str, pd.Series],
    weights: dict[str, float] | None = None,
) -> float:
    """Compute diversification ratio of a portfolio of strategies.

    DR = (weighted sum of individual vols) / (portfolio vol)
    DR > 1 means diversification is reducing total risk.

    Args:
        strategy_returns: Dict mapping strategy name to daily returns.
        weights: Portfolio weights per strategy. If None, equal-weight.

    Returns:
        Diversification ratio (typically ~2 for well-diversified portfolios).
    """
    returns_df = pd.DataFrame(strategy_returns).dropna()
    if returns_df.empty or returns_df.shape[1] < 2:
        return 1.0

    n = returns_df.shape[1]
    if weights is None:
        w = np.ones(n) / n
    else:
        w = np.array([weights.get(name, 1.0 / n) for name in returns_df.columns])
        w = w / w.sum()

    # Individual annualized vols
    individual_vols = returns_df.std() * np.sqrt(252)

    # Portfolio vol
    portfolio_returns = returns_df @ w
    portfolio_vol = portfolio_returns.std() * np.sqrt(252)

    # Weighted sum of individual vols
    weighted_vol_sum = (individual_vols * w).sum()

    if portfolio_vol == 0:
        return 1.0

    return weighted_vol_sum / portfolio_vol
