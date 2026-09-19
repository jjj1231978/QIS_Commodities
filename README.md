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

Six systematic commodity-futures strategies — carry, value, trend, congestion,
basis momentum and backwardation momentum — built on a common F0–F12 term
structure panel and combined into one vol-targeted portfolio.

Backtest runs **2015-06-08 → 2026-05-04** (3,391 trading days) over 17 CME-listed
BCOM constituents, net of modelled transaction costs.

> **Backtested research, not a track record.** Every figure here is the output of
> the code in this repo on historical data. Nothing has been traded.

## What the pages show

| Page | Contents |
|---|---|
| **Data** | Raw per-strategy return series and the portfolio frame |
| **Performance** | Cumulative return, drawdown, rolling Sharpe, headline portfolio metrics, and how the portfolio is constructed |
| **Stats vs Reference** | Realised metrics per strategy, side by side where a reference is available |
| **Correlations** | Strategy return correlation matrix |

## Results

Net of costs, full sample:

| Strategy | Sharpe | Return | Vol | Max DD |
|---|---|---|---|---|
| Carry | 1.15 | 7.7% | 6.7% | −7.2% |
| Value | 0.76 | 7.7% | 10.1% | −21.8% |
| Trend | 0.08 | 0.5% | 6.4% | −22.8% |
| Congestion | −0.30 | −0.2% | 0.6% | −4.0% |
| Basis momentum | −0.40 | −4.0% | 10.0% | −51.9% |
| Backwardation momentum | −0.46 | −1.5% | 3.2% | −19.2% |
| **Portfolio** | **0.53** | **2.9%** | **5.4%** | **−15.1%** |

Carry and value carry the book.

> **The backwardation momentum figure above is not a result.** The committed
> artifacts predate a fix to `_rank_to_weights`: a rebalance that could not rank
> enough names wrote an explicit zero row, which then forward-filled and flattened
> the book until the next successful rebalance. Combined with the F12 requirement
> starving the cross-section, that held the strategy flat on 97.6% of days — its
> −0.46 Sharpe reflects roughly 80 days of trading over eleven years, not the
> strategy. Two changes address it: `_rank_to_weights` now holds the previous
> position instead of flattening, and `n_long`/`n_short` drop from 4 to 3 so the
> six-name floor can actually be met in a universe where only ~11 roots carry a
> deep enough curve. These numbers will change when the pipeline is next re-run.
> `value` and `basis_momentum` shared the code path and are affected to a lesser
> degree.

Congestion's near-flat line is expected rather than broken: it is deliberately out
of the market outside business days 1–9, so ~60% of days are genuinely zero, and
its 0.6% vol makes it a hairline next to the others.

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
series the viewer reads.

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
