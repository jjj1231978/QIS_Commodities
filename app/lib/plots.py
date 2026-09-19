"""Shared Plotly chart helpers for Streamlit pages."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.backtest.metrics import compute_metrics

from app.lib.data_loader import REF_BENCHMARK


def cumulative(returns: pd.Series) -> pd.Series:
    return (1 + returns).cumprod()


def drawdown(returns: pd.Series) -> pd.Series:
    cum = cumulative(returns)
    return cum / cum.cummax() - 1.0


def rolling_sharpe(returns: pd.Series, window: int = 252) -> pd.Series:
    mu = returns.rolling(window).mean() * 252
    sd = returns.rolling(window).std() * np.sqrt(252)
    return (mu / sd).replace([np.inf, -np.inf], np.nan)


def correlation_heatmap(returns_df: pd.DataFrame) -> go.Figure:
    corr = returns_df.corr()
    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        aspect="auto",
    )
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10))
    return fig


def build_stats_table(
    strategy_returns: dict[str, pd.Series],
    overlay: pd.DataFrame | None,
) -> pd.DataFrame:
    rows = []
    for name, r in strategy_returns.items():
        m = compute_metrics(r)
        rows.append({"strategy": name, **m, "n_obs": len(r)})
    if overlay is not None and "scaled_return" in overlay.columns:
        m = compute_metrics(overlay["scaled_return"].dropna())
        rows.append({"strategy": "portfolio", **m, "n_obs": int(len(overlay))})
    df = pd.DataFrame(rows).set_index("strategy")
    return df.join(REF_BENCHMARK, how="left")
