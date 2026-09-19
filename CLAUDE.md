# QIS Commodities

Systematic commodity QIS strategies reproduced from a reference research report.

## Quick Start

```bash
# Set up environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set API key
export DATABENTO_API_KEY="your-key"

# Fetch data (requires API key)
python -m src.data

# Run full pipeline
python -m src.main

# Launch dashboard
streamlit run app/streamlit_app.py

# Run tests
pytest tests/
```

## Architecture

```
src/
├── config.py           — load_config(), path constants
├── data/
│   ├── fetch.py        — Databento futures data with parquet caching
│   ├── universe.py     — BCOM 24 constituents, Commodity dataclass, Universe
│   ├── contracts.py    — roll calendar, expiry logic, active contract mapping
│   └── term_structure.py — build F0..F12 panel per commodity
├── signals/
│   ├── base.py         — SignalResult dataclass, BaseSignal ABC
│   ├── carry.py        — term structure carry (F3-F0, dollar-neutral)
│   ├── value.py        — cross-sectional mean reversion from multi-year MA
│   ├── trend.py        — multi-lookback (1m/3m/6m/12m) momentum
│   ├── congestion.py   — pre-roll strategy around BCOM BD 5-9
│   └── basis_momentum.py — trend of curve slope
├── backtest/
│   ├── engine.py       — weights → daily PnL
│   ├── costs.py        — per-commodity spread + commission model
│   ├── portfolio.py    — multi-strategy overlay, vol targeting
│   └── metrics.py      — SR, maxDD, calmar, sortino, diversification ratio
├── diagnostics/        — signal inspection helpers (inspect_signal, load_*)
├── reporting/          — multi-agent research-note generation
└── main.py             — pipeline orchestrator

app/                    — Streamlit dashboard (multi-page via st.navigation)
├── streamlit_app.py    — entry point: `streamlit run app/streamlit_app.py`
├── lib/                — shared loaders + chart helpers
└── pages/              — nav order: 05_data, 01_performance, 02_stats, 03_correlations
                          (04_overlay is on disk but unlisted in st.navigation)

notebooks/              — exploratory scripts (figures saved to notebooks/figures/)
```

## Key Design Decisions

- **Signal interface**: Every strategy returns `SignalResult(weights, signal_values, metadata)`. Weights are dates × commodities, dollar-neutral (rows sum to ~0).
- **Term structure**: Unadjusted prices in F0..F12 panel. Carry uses raw spreads. Trend uses ratio-adjusted continuous series.
- **Databento**: Fetch with `{root}.FUT` to get all contract months. Cache per-commodity as parquet.
- **Cost model**: Per-commodity spread (2-5 bps). Time-spread trades (carry, congestion) get 50% discount.
- **Intraday trend**: Deferred (requires minute data, separate pipeline).

## Validation Benchmarks

Reference-report comparison figures are third-party research licensed for
personal use and are **not** in this repo. They live in `data/reference/benchmark.json`,
which is gitignored and absent from GitHub and the Space.

The code degrades when the file is missing: `app/lib/data_loader.load_reference_benchmark()`
returns an empty frame, `src/reporting/pack.load_paper_reference()` returns
`{"available": False}`, the Stats page shows realised metrics only, and
`tests/test_pack.py::test_pack_paper_reference_complete` skips.

Realised results from the current run are in README.md.

## Data

- Source: Databento (`GLBX.MDP3` for CME, `IFEU.IMPACT` for ICE Europe, `IFUS.IMPACT` for ICE US)
- Universe: 24 BCOM constituents (energy, grains, softs, livestock, base metals, precious metals)
- Term structure: F0 through F12 (13 contracts along the curve)
- Backtest period: 2003-2024

## Testing

```bash
pytest tests/ -v
pytest tests/test_carry.py -k "dollar_neutral"
```

Tests use synthetic term structures (see `tests/conftest.py`). No API calls required for tests.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
