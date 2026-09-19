"""Correlations page: cross-strategy return correlation matrix."""

import pandas as pd
import streamlit as st

from app.lib import data_loader as dl
from app.lib.plots import correlation_heatmap

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
st.plotly_chart(correlation_heatmap(df), width="stretch")
st.caption(
    "The reference report (p. 27) shows that all strategies are weakly or "
    "negatively correlated, except Congestion/Carry F0–F6 and "
    "Basis/Backwardation momentum which are mildly positive."
)
