"""Multi-strategy overlay portfolio with volatility targeting."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.backtest.metrics import compute_diversification_ratio, compute_metrics

log = logging.getLogger(__name__)


def build_overlay_portfolio(
    strategy_returns: dict[str, pd.Series],
    weighting: str = "equal",
    vol_target: float = 0.05,
    vol_lookback: int = 63,
) -> pd.DataFrame:
    """Combine strategy returns into a vol-targeted overlay portfolio.

    Args:
        strategy_returns: Dict mapping strategy name to daily net return series.
        weighting: "equal" or "risk_parity".
        vol_target: Annualized volatility target (default 5%).
        vol_lookback: Rolling window for vol estimation (business days).

    Returns:
        DataFrame with columns: raw_return, scaled_return, rolling_vol,
        scale_factor, cumulative_return.
    """
    # Align all strategies to common dates
    returns_df = pd.DataFrame(strategy_returns).dropna()
    if returns_df.empty:
        return pd.DataFrame()

    n_strategies = returns_df.shape[1]
    log.info(f"Building overlay: {n_strategies} strategies, {len(returns_df)} days")

    # Compute strategy weights
    if weighting == "equal":
        weights = np.ones(n_strategies) / n_strategies
    else:
        # Risk parity: weight inversely proportional to vol
        vols = returns_df.std()
        inv_vol = 1.0 / vols.replace(0, np.inf)
        weights = (inv_vol / inv_vol.sum()).values

    # Raw portfolio return (before vol scaling)
    raw_return = returns_df @ weights

    # Vol targeting: scale portfolio to achieve target vol
    rolling_vol = raw_return.rolling(vol_lookback, min_periods=20).std() * np.sqrt(252)
    scale_factor = vol_target / rolling_vol.replace(0, np.inf)
    scale_factor = scale_factor.clip(upper=3.0)  # cap leverage at 3x

    # Scaled return (apply vol target)
    scaled_return = raw_return * scale_factor.shift(1).fillna(1.0)

    # Cumulative
    cumulative = (1 + scaled_return).cumprod()

    result = pd.DataFrame(
        {
            "raw_return": raw_return,
            "scaled_return": scaled_return,
            "rolling_vol": rolling_vol,
            "scale_factor": scale_factor,
            "cumulative_return": cumulative,
        }
    )

    # Log summary
    metrics = compute_metrics(scaled_return)
    dr = compute_diversification_ratio(strategy_returns)
    log.info(
        f"Overlay: SR={metrics['sharpe_ratio']:.2f}, "
        f"Ret={metrics['annualized_return']:.1%}, "
        f"Vol={metrics['annualized_vol']:.1%}, "
        f"MaxDD={metrics['max_drawdown']:.1%}, "
        f"DR={dr:.2f}"
    )

    return result
