"""Cached parquet loaders + shared sidebar for Streamlit pages.

All loaders use `st.cache_data` so the dashboard stays snappy when navigating
between pages. Returns None when a file is absent so pages can render a
"not yet produced" message instead of crashing.
"""

from __future__ import annotations

import json

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import PROCESSED_DIR

STRATEGIES = [
    "carry",
    "value",
    "trend",
    "congestion",
    "basis_momentum",
    "backwardation_momentum",
]

# Reference-report figures are NOT in this repo — they are third-party research
# transcribed from a licensed report, kept in a gitignored local file. When the
# file is absent (GitHub, the Space, any fresh clone) the comparison columns are
# simply empty and the dashboard shows realised metrics only.
REF_COLUMNS = ["ref_sharpe", "ref_return", "ref_vol", "ref_max_dd"]
REFERENCE_FILE = PROCESSED_DIR.parent / "reference" / "benchmark.json"


def load_reference_benchmark() -> pd.DataFrame:
    """Benchmark comparison frame, empty when the local reference file is absent."""
    empty = pd.DataFrame(columns=REF_COLUMNS, index=pd.Index([], name="strategy"))
    if not REFERENCE_FILE.exists():
        return empty
    try:
        block = json.loads(REFERENCE_FILE.read_text())["dashboard_benchmark"]
    except (OSError, ValueError, KeyError):
        return empty
    return pd.DataFrame(
        block["data"],
        index=pd.Index(block["index"], name="strategy"),
        columns=block["columns"],
    )


REF_BENCHMARK = load_reference_benchmark()
REFERENCE_AVAILABLE = not REF_BENCHMARK.empty


@st.cache_data(show_spinner=False)
def load_strategy_returns(processed_dir: Path = PROCESSED_DIR) -> dict[str, pd.Series]:
    out = {}
    for s in STRATEGIES:
        p = processed_dir / f"{s}_backtest.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            if "net_return" in df.columns:
                out[s] = df["net_return"].dropna()
    return out


@st.cache_data(show_spinner=False)
def load_overlay(processed_dir: Path = PROCESSED_DIR) -> pd.DataFrame | None:
    p = processed_dir / "overlay_portfolio.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)


def render_no_data_warning() -> None:
    st.warning(
        f"No results found in `{PROCESSED_DIR}`. Run the pipeline first:\n\n"
        "```bash\npython -m src.main\n```"
    )


def render_sidebar(
    strategy_returns: dict[str, pd.Series],
    overlay: pd.DataFrame | None,
) -> tuple[dict[str, pd.Series], pd.DataFrame | None, list[str], bool, bool, int]:
    """Render shared sidebar filters and return the filtered data + selections.

    Widget keys are stable so values persist across pages.
    """
    st.sidebar.title("Sys Commodities Research Demo")
    st.sidebar.header("Filters")
    available = list(strategy_returns.keys())
    selected = st.sidebar.multiselect(
        "Strategies", available, default=available, key="filter_strategies"
    )
    show_overlay = st.sidebar.checkbox(
        "Show portfolio", value=overlay is not None, key="filter_show_overlay"
    )
    log_scale = st.sidebar.checkbox("Log scale (cumulative)", value=False, key="filter_log_scale")
    rolling_window = st.sidebar.slider(
        "Rolling window (days)", 63, 504, 252, 63, key="filter_rolling_window"
    )

    if strategy_returns:
        date_min = min(r.index.min() for r in strategy_returns.values())
        date_max = max(r.index.max() for r in strategy_returns.values())
        date_range = st.sidebar.date_input(
            "Date range",
            value=(date_min.date(), date_max.date()),
            min_value=date_min.date(),
            max_value=date_max.date(),
            key="filter_date_range",
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            d0, d1 = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
            strategy_returns = {k: v.loc[d0:d1] for k, v in strategy_returns.items()}
            if overlay is not None:
                overlay = overlay.loc[d0:d1]

    return strategy_returns, overlay, selected, show_overlay, log_scale, rolling_window
