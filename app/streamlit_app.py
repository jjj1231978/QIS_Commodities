"""Streamlit entry point for the Systematic Commodity Futures dashboard.

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
    page_title="Systematic Commodity Futures",
    page_icon=":bar_chart:",
    layout="wide",
)

from app.lib.theme import apply_page_chrome  # noqa: E402

# Must precede st.navigation: anything the entry script emits after nav.run()
# is discarded, because the page script has already closed the main container.
apply_page_chrome()

PAGES_DIR = Path(__file__).resolve().parent / "pages"

# File numbering matches navigation order, and each url_path matches its label so a
# shared link names the page it opens. Data is the default page and takes "/".
pages = [
    st.Page(PAGES_DIR / "01_data.py", title="Data",
            icon=":material/table_view:", default=True),
    st.Page(PAGES_DIR / "02_strategy_lab.py", title="Strategy Lab",
            icon=":material/timeline:", url_path="strategy-lab"),
    st.Page(PAGES_DIR / "03_metrics.py", title="Performance Metrics",
            icon=":material/leaderboard:", url_path="metrics"),
    st.Page(PAGES_DIR / "04_correlations.py", title="Correlations",
            icon=":material/grid_on:", url_path="correlations"),
]

nav = st.navigation(pages)
nav.run()
