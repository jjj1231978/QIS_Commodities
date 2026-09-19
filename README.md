---
title: Sys Commodities Research Demo
emoji: 🛢️
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Sys Commodities Research Demo

Five systematic commodity-futures strategies — carry, value, trend, congestion,
and basis momentum — built on a common F0–F12 term structure panel and combined
into one vol-targeted portfolio.

Backtest runs **2015-06-08 → 2026-05-04** (3,391 trading days) over 17 CME-listed
BCOM constituents, net of modelled transaction costs.

> **Backtested research, not a track record.** Every figure here is the output of
> the code in this repo on historical data. Nothing has been traded.

## What the pages show

Navigation order is Data first — the tables everything else is derived from.

| Page | Contents |
|---|---|
| **Data** | The two source tables, downloadable as CSV: per-strategy daily returns net of costs, and the portfolio series with every step of the vol-targeting calculation. Expanders derive each column from the code. |
| **Performance** | Cumulative return, drawdown and rolling Sharpe (window selectable: 63/126/252/504d), headline portfolio metrics, and an expander on how the portfolio is constructed |
| **Stats** | Realised metrics per strategy. The tab is named *Stats vs Reference* and gains comparison columns only where the local reference file is present; this published build ships without it |
| **Correlations** | Strategy return correlation matrix |

A fifth page, **Overlay detail**, exists in `app/pages/` but is not in the
navigation; its content was folded into Performance.

## Results

Net of costs, full sample:

| Strategy | Sharpe | Return | Vol | Max DD |
|---|---|---|---|---|
| Carry | 1.15 | 7.7% | 6.7% | -7.2% |
| Value | 0.64 | 6.7% | 10.6% | -23.1% |
| Trend | 0.08 | 0.5% | 6.4% | -22.8% |
| Congestion | -0.30 | -0.2% | 0.6% | -4.0% |
| Basis momentum | -0.41 | -4.2% | 10.3% | -53.3% |
| **Portfolio** | **0.47** | **2.5%** | **5.5%** | **-14.8%** |

Carry and value carry the book. Basis momentum and congestion detract over this
sample — see "Known limitations" before reading much into either.

Congestion's near-flat line is expected rather than broken: it is deliberately out
of the market outside business days 1–9, so ~60% of days are genuinely zero, and
its 0.6% vol makes it a hairline next to the others.

### Why there are five strategies, not six

A sixth, **backwardation momentum**, was removed. It ranks on `F0/F12`, choosing
contracts twelve months apart so seasonal effects cancel — but this universe does
not carry that curve. Only WTI and natural gas have an F12 populated on ≥80% of
days; silver's liquid curve is two contracts deep, gold's four. The median month
offered five rankable names against a six-name floor, so the strategy held a
position on 4.2% of days. A shallower pairing (F0/F6 gives twelve names) would
restore the cross-section but forfeit the seasonality neutrality that is the
signal's entire rationale, so the sleeve was dropped rather than quietly
redefined.

## How it is built

Every signal reads a per-commodity **term structure panel**: a dates × `F0…F12`
matrix of unadjusted settlement prices, rolled five business days before expiry.
Prices are unadjusted deliberately — carry-type signals need the true spread
between two real contracts. Trend is the exception and uses a ratio-adjusted
continuous series.

Each strategy returns a dates × commodities weight matrix, **dollar-neutral at
gross 1.0** (longs +0.5, shorts −0.5). The engine lags positions one day, then
computes either a spread return (carry, congestion) or an outright `F0` return.

The portfolio equal-weights the six streams, measures a 63-day rolling
volatility, and scales to a 5% annualised target capped at 3× leverage, with the
scale factor lagged one day so there is no lookahead.

```
src/
├── data/        term structure panel, roll calendar, universe
├── signals/     one module per strategy
├── backtest/    engine, cost model, portfolio, metrics
└── reporting/   research-pack assembly
app/             Streamlit viewer (multi-page)
```

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DATABENTO_API_KEY="your-key"
python -m src.data          # fetch (requires API key)
python -m src.main          # full pipeline

streamlit run app/streamlit_app.py
pytest tests/               # no API calls needed
```

The viewer is read-only: it loads the parquets under `data/processed/` and never
triggers a fetch or a backtest.

## What is and isn't published

Both the GitHub repo and the Space are **public**. The split is deliberate.

**Published** — everything needed to audit or reproduce the work: all source,
configs and tests, plus the per-strategy backtest outputs and the portfolio
series the viewer reads. The Data page exposes both as CSV downloads, and its
expanders document how every figure is derived.

**Not published:**

| Path | Why |
|---|---|
| `data/reference/` | Benchmark figures transcribed from a third-party research report licensed for personal use — not ours to redistribute |
| `Sys_Commodity.pdf` | That report. Never committed |
| `data/raw/` | Licensed Databento futures pulls |
| `data/processed/*_weights.parquet` | Position matrices; no page reads them |

The reference figures are loaded from a local file when present and are simply
absent otherwise — the Stats page then shows realised metrics only, and the
reporting pack records that no reference is available. Nothing breaks.

## Known limitations

- **Universe.** 17 CME-listed futures, not the full 24-constituent index. Softs
  (sugar, coffee, cocoa, cotton) are absent entirely. The three cross-sectional
  rankers pick 5 long / 5 short, so they hold 10 of 17 names — far less
  selective than the same rule on a broader universe.
- **Sample.** Just under eleven years from mid-2015. Several of these premia are
  documented as having decayed over precisely this period.
- **No per-strategy vol scaling.** Volatility targeting happens only at the
  portfolio level, so strategy vols range from 0.6% to 10.1%. Return magnitudes
  are not comparable across strategies; Sharpe comparisons still are.
- **Unvalidated free parameters.** The 63-day lookback in basis momentum is the
  clearest case — the highest-leverage choice in that strategy, with no sourced
  justification.

## Licence

MIT — see [LICENSE](LICENSE).
