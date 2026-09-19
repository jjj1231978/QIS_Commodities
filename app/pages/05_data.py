"""Data page: raw return tables with CSV download."""

import pandas as pd
import streamlit as st

from src.config import load_config

from app.lib import data_loader as dl

st.title("Data")
st.caption(
    "The tables the rest of the dashboard is computed from, shown raw and "
    "downloadable. Every figure elsewhere traces back to these two frames."
)

strategy_returns = dl.load_strategy_returns()
overlay = dl.load_overlay()

if not strategy_returns and overlay is None:
    dl.render_no_data_warning()
    st.stop()

strategy_returns, overlay, _, _, _ = dl.render_sidebar(strategy_returns, overlay)

if strategy_returns:
    st.subheader("Strategy returns")
    st.caption(
        "Daily return per strategy, net of modelled transaction costs. One column "
        "per strategy, one row per trading day. Last 50 rows shown."
    )
    df = pd.DataFrame(strategy_returns)
    st.dataframe(df.tail(50), width="stretch")

    with st.expander("How a strategy return is computed"):
        st.markdown(
            """
Each value is one strategy's net return for one day, produced by
`src/backtest/engine.py` in four steps.

**1 — Weights.** The strategy emits a dates × commodities matrix, dollar-neutral at
gross 1.0 (longs sum to +0.5, shorts to −0.5).

**2 — Lag.** `weights.shift(1)`. A position set on yesterday's close earns today's
return, so no trade is filled at a price that set it.

**3 — Per-commodity return.** Two cases, chosen by whether the strategy trades the
curve or the outright:

- *spread trades* (carry, congestion) — the daily change in
  `(F_deferred − F_front) / F_front`
- *directional trades* (value, trend, basis momentum) — `F0.pct_change()`

**4 — Net of costs.**

```
gross_return = Σ (lagged_weight × commodity_return)
cost         = Σ |Δweight| × spread_bps / 10,000
net_return   = gross_return − cost
```

`spread_bps` is 2 by default, with per-commodity overrides where liquidity is
thinner (natural gas 3, aluminium and zinc 4, nickel 5). Time-spread trades get a
50% discount, since a calendar spread costs less to execute than two outright legs.
The first day of any series is charged nothing.
"""
        )
    st.download_button(
        "Download all strategy returns (CSV)",
        df.to_csv().encode(),
        file_name="strategy_returns.csv",
        mime="text/csv",
    )

if overlay is not None:
    st.subheader("Portfolio series")
    st.caption(
        "The vol-targeting calculation laid out step by step — one row per trading "
        "day. `scaled_return` is the reported portfolio return; the other columns "
        "are the intermediates, shown so the targeting is auditable."
    )
    st.dataframe(overlay.tail(50), width="stretch")
    st.download_button(
        "Download portfolio series (CSV)",
        overlay.to_csv().encode(),
        file_name="portfolio_series.csv",
        mime="text/csv",
    )

    try:
        _c = load_config()["overlay"]
        _target, _lb, _scheme = _c["vol_target"], _c["vol_lookback_days"], _c["weighting"]
    except Exception:
        _target, _lb, _scheme = 0.05, 63, "equal"

    with st.expander("How each column is computed"):
        _n = len(strategy_returns) or 5
        st.markdown(
            f"""
Produced by `src/backtest/portfolio.py`. Each column is one step of the chain, in
order — every row below is computed from the one above it.

| Column | Formula | Meaning |
|---|---|---|
| `raw_return` | `Σ (strategy_return × 1/{_n})` | the **{_scheme}**-weighted blend of the {_n} strategies, before any leverage |
| `rolling_vol` | `raw_return.rolling({_lb}).std() × √252` | annualised volatility estimate over the trailing {_lb} days |
| `scale_factor` | `{_target:.0%} / rolling_vol`, capped at 3× | the leverage multiple the target implies |
| `scaled_return` | `raw_return × scale_factor.shift(1)` | **the reported portfolio return** |
| `cumulative_return` | `(1 + scaled_return).cumprod()` | the equity curve, starting at 1.0 |

**Why `.shift(1)` on the scale factor.** Today's position size uses only volatility
estimated through yesterday. Without the lag the book would be sized using the very
day's return it is about to earn — a lookahead that flatters results.

**Why the 3× cap.** In very calm stretches `{_target:.0%} / rolling_vol` asks for
leverage that no one would actually run. The cap binds instead, and the portfolio
deliberately sits below target on those days.

**A worked row.** Reading the last row of the table above: the blend returns
`raw_return`; the vol estimate `rolling_vol` is compared to the {_target:.0%} target
to give `scale_factor`; multiply `raw_return` by *yesterday's* `scale_factor` and you
get `scaled_return`. A scale factor below 1.0 means realised vol is running above
target and the book is being **cut**, not levered.

**What is not in this frame.** Strategies flagged `in_overlay: false` in the config
never enter `raw_return` — that is how the extra carry variants are kept from
counting one bet several times. And the builder aligns strategies with a row-wise
`dropna()`, so this frame starts only once *every* constituent has data.
"""
        )
