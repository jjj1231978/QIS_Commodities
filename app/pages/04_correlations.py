"""Correlations page: cross-strategy return correlation matrix."""

import pandas as pd
import streamlit as st

from app.lib import data_loader as dl
from app.lib.plots import correlation_heatmap
from app.lib.theme import label, plot

st.title("Correlations")

strategy_returns = dl.load_strategy_returns()
overlay = dl.load_overlay()

if not strategy_returns and overlay is None:
    dl.render_no_data_warning()
    st.stop()

strategy_returns, _, _, _, _ = dl.render_sidebar(strategy_returns, overlay)

if len(strategy_returns) < 2:
    st.info("Need at least two strategies for a correlation matrix.")
    st.stop()

df = pd.DataFrame(strategy_returns).dropna()
st.subheader("Strategy return correlations")
# Display names on the axes; the frame keeps its keys.
plot(correlation_heatmap(df.rename(columns=label)))
st.caption(
    "Pairwise correlation of daily net returns. The sleeves are largely "
    "uncorrelated with each other, which is what lets the equal-weighted "
    "blend run at a lower volatility than any single strategy before "
    "vol targeting re-levers it."
)
