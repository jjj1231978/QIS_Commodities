"""
QIS Commodities — Signal Diagnostics
====================================
Run: python notebooks/01_signal_diagnostics.py
Or use in Jupyter/IPython for interactive exploration.

Loads cached term structures and runs each signal end-to-end so you can
inspect raw weights, realised vs reference benchmark, and per-commodity contributions.
"""

import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import pandas as pd

from src.config import PROCESSED_DIR, load_config
from src.diagnostics import load_backtest, load_stats

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------
plt.style.use("seaborn-v0_8-whitegrid")
cfg = load_config()
OUTPUT_DIR = Path(__file__).resolve().parent / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)

STRATEGIES = [
    "carry",
    "value",
    "trend",
    "congestion",
    "basis_momentum",
    "backwardation_momentum",
]

# --------------------------------------------------------------------------
# 1. Realised vs reference benchmark
# --------------------------------------------------------------------------
print("=" * 60)
print("1. STRATEGY STATS")
print("=" * 60)
try:
    stats = load_stats()
    print(stats)
except FileNotFoundError:
    print(f"No stats.csv yet — run `python -m src.main` first.")
    sys.exit(0)

# --------------------------------------------------------------------------
# 2. Cumulative equity curves
# --------------------------------------------------------------------------
print("\n" + "=" * 60)
print("2. EQUITY CURVES")
print("=" * 60)
returns = {}
for s in STRATEGIES:
    p = PROCESSED_DIR / f"{s}_backtest.parquet"
    if p.exists():
        returns[s] = load_backtest(s)["net_return"].dropna()

if returns:
    cum = pd.DataFrame({k: (1 + v).cumprod() for k, v in returns.items()})
    fig, ax = plt.subplots(figsize=(11, 5))
    cum.plot(ax=ax, lw=1.2)
    ax.set_title("Cumulative return (net of costs)")
    ax.set_ylabel("Equity")
    ax.legend(loc="upper left", ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "equity_curves.png", dpi=120)
    print(f"saved {OUTPUT_DIR / 'equity_curves.png'}")
