"""Streamlit entry point for the Sys Commodities Research Demo dashboard.

Run from the repo root:

    streamlit run app/streamlit_app.py

Multi-page navigation via st.navigation. Pages are defined in app/pages/.
The viewer is read-only — it loads parquets written by `python -m src.main`
into data/processed/. It never triggers data fetches or backtest runs.
"""

import sys
from pathlib import Path

# Allow `from src.*` and `from app.*` imports when running via streamlit
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(
    page_title="Sys Commodities Research Demo",
    page_icon=":bar_chart:",
    layout="wide",
)

PAGES_DIR = Path(__file__).resolve().parent / "pages"

# The reference figures are third-party and ship only in a local build, so the
# published Space has no reference to compare against. Name the tab for what it
# actually shows rather than promising a column that is not there.
from app.lib.data_loader import REFERENCE_AVAILABLE  # noqa: E402

STATS_TITLE = "Stats vs Reference" if REFERENCE_AVAILABLE else "Stats"

pages = [
    st.Page(PAGES_DIR / "05_data.py", title="Data", icon=":material/table_view:"),
    st.Page(PAGES_DIR / "01_performance.py", title="Performance", icon=":material/timeline:"),
    st.Page(PAGES_DIR / "02_stats.py", title=STATS_TITLE, icon=":material/leaderboard:"),
    st.Page(PAGES_DIR / "03_correlations.py", title="Correlations", icon=":material/grid_on:"),
]

nav = st.navigation(pages)
nav.run()
