"""Data page: raw return tables with CSV download."""

import pandas as pd
import streamlit as st

from app.lib import data_loader as dl

st.title("Data")

strategy_returns = dl.load_strategy_returns()
overlay = dl.load_overlay()

if not strategy_returns and overlay is None:
    dl.render_no_data_warning()
    st.stop()

strategy_returns, overlay, _, _, _, _ = dl.render_sidebar(strategy_returns, overlay)

if strategy_returns:
    st.subheader("Raw strategy returns")
    df = pd.DataFrame(strategy_returns)
    st.dataframe(df.tail(50), width="stretch")
    st.download_button(
        "Download all strategy returns (CSV)",
        df.to_csv().encode(),
        file_name="strategy_returns.csv",
        mime="text/csv",
    )

if overlay is not None:
    st.subheader("Overlay frame")
    st.dataframe(overlay.tail(50), width="stretch")
    st.download_button(
        "Download overlay (CSV)",
        overlay.to_csv().encode(),
        file_name="overlay.csv",
        mime="text/csv",
    )
