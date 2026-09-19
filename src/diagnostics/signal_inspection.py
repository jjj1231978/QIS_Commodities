"""Diagnostics helpers for inspecting `SignalResult` and backtest outputs.

User Story 4 of the spec — let a user filter by (date, root) and answer:
"On 2022-04-15, what was the carry signal for CL, what weight did it
get, and which contracts were traded?"
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import PROCESSED_DIR
from src.signals.base import SignalResult


def inspect_signal(
    result: SignalResult,
    date: str | pd.Timestamp,
    root: str | None = None,
) -> pd.DataFrame:
    """Return signal value and weight for a given date, optionally one root.

    Args:
        result: A `SignalResult` from any signal.
        date: Trading day to inspect (string or Timestamp).
        root: Optional commodity root to filter to.

    Returns:
        DataFrame with columns [signal, weight] and one row per root.
        If `root` is supplied, the frame is narrowed to that root.
    """
    ts = pd.Timestamp(date)
    sig_row = result.signal_values.loc[result.signal_values.index.asof(ts)]
    w_row = result.weights.loc[result.weights.index.asof(ts)]
    df = pd.DataFrame({"signal": sig_row, "weight": w_row})
    df.index.name = "root"
    if root is not None:
        df = df.loc[[root]] if root in df.index else df.iloc[0:0]
    return df


def load_backtest(
    strategy: str,
    processed_dir: Path | None = None,
) -> pd.DataFrame:
    """Load a strategy's backtest parquet (gross/net return + turnover)."""
    d = processed_dir if processed_dir is not None else PROCESSED_DIR
    return pd.read_parquet(d / f"{strategy}_backtest.parquet")


def load_weights(
    strategy: str,
    processed_dir: Path | None = None,
) -> pd.DataFrame:
    """Load a strategy's daily weights parquet."""
    d = processed_dir if processed_dir is not None else PROCESSED_DIR
    return pd.read_parquet(d / f"{strategy}_weights.parquet")


def load_stats(processed_dir: Path | None = None) -> pd.DataFrame:
    """Load the consolidated `stats.csv` produced by the pipeline."""
    d = processed_dir if processed_dir is not None else PROCESSED_DIR
    return pd.read_csv(d / "stats.csv", index_col="strategy")


def positions_on(
    strategy: str,
    date: str | pd.Timestamp,
    processed_dir: Path | None = None,
) -> pd.Series:
    """Return non-zero positions for a strategy on a given date."""
    weights = load_weights(strategy, processed_dir)
    ts = pd.Timestamp(date)
    row = weights.loc[weights.index.asof(ts)]
    return row[row != 0].sort_values()
