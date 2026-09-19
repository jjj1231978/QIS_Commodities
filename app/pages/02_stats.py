"""Performance Metrics page: full metric table per strategy, plus a Sharpe chart.

The reference comparison columns appear only when the local reference file is
present; the page title stays stable either way and the subheadings say which
view you are looking at.
"""

import plotly.express as px
import streamlit as st

from app.lib import data_loader as dl
from app.lib.plots import build_stats_table

st.title("Performance Metrics")

strategy_returns = dl.load_strategy_returns()
overlay = dl.load_overlay()

if not strategy_returns and overlay is None:
    dl.render_no_data_warning()
    st.stop()

strategy_returns, overlay, _, show_overlay, _ = dl.render_sidebar(strategy_returns, overlay)

stats = build_stats_table(strategy_returns, overlay if show_overlay else None)

_cols = [
    "annualized_return",
    "annualized_vol",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "calmar_ratio",
    "n_obs",
]
if dl.REFERENCE_AVAILABLE:
    st.subheader("Realised vs reference benchmark")
    _cols += dl.REF_COLUMNS
else:
    st.subheader("Realised performance")
    st.caption(
        "Reference-report comparison figures are third-party research and are not "
        "published with this repo, so this build shows realised metrics only."
    )
display = stats[[c for c in _cols if c in stats.columns]].copy()
st.dataframe(
    display.style.format(
        {
            "annualized_return": "{:.2%}",
            "annualized_vol": "{:.2%}",
            "sharpe_ratio": "{:.2f}",
            "sortino_ratio": "{:.2f}",
            "max_drawdown": "{:.2%}",
            "calmar_ratio": "{:.2f}",
            "ref_sharpe": "{:.2f}",
            "ref_return": "{:.2%}",
            "ref_vol": "{:.2%}",
            "ref_max_dd": "{:.2%}",
        }
    ),
    width="stretch",
)

if dl.REFERENCE_AVAILABLE:
    st.subheader("Sharpe ratio: realised vs reference")
    sr_compare = stats[["sharpe_ratio", "ref_sharpe"]].dropna()
    sr_compare = sr_compare.rename(columns={"sharpe_ratio": "Realised", "ref_sharpe": "Reference"})
else:
    st.subheader("Sharpe ratio by strategy")
    sr_compare = stats[["sharpe_ratio"]].dropna().rename(columns={"sharpe_ratio": "Realised"})
fig = px.bar(sr_compare, barmode="group", labels={"value": "Sharpe", "index": "Strategy"})
fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, width="stretch")
