"""Performance page: cumulative return, drawdown, rolling Sharpe."""

import pandas as pd
import plotly.express as px
import streamlit as st

from src.backtest.metrics import compute_diversification_ratio, compute_metrics
from src.backtest.portfolio import build_overlay_portfolio
from src.config import load_config

from app.lib import data_loader as dl
from app.lib.data_loader import REF_BENCHMARK
from app.lib.plots import cumulative, drawdown, rolling_sharpe

st.title("Performance")
st.caption(
    "Reproduction of systematic commodity strategies from the reference report."
)

strategy_returns = dl.load_strategy_returns()
overlay = dl.load_overlay()

if not strategy_returns and overlay is None:
    dl.render_no_data_warning()
    st.stop()

strategy_returns, overlay, selected, show_overlay, log_scale = dl.render_sidebar(
    strategy_returns, overlay
)
sel_returns = {k: v for k, v in strategy_returns.items() if k in selected}

# The stored portfolio is the pipeline's, built from every strategy. When the
# sidebar narrows the selection, rebuild the blend from what is actually
# selected so the portfolio line agrees with the lines around it — rebuilding
# from the stored per-strategy returns reproduces the pipeline's own output
# exactly, so this is faithful rather than an approximation.
_is_full_set = set(selected) == set(strategy_returns)
_whatif = bool(selected) and not _is_full_set
if _whatif:
    _o = load_config()["overlay"]
    rebuilt = build_overlay_portfolio(
        sel_returns, _o["weighting"], _o["vol_target"], _o["vol_lookback_days"]
    )
    overlay = rebuilt if not rebuilt.empty else overlay
_pf_label = f"Portfolio ({len(selected)} of {len(strategy_returns)})" if _whatif else "Portfolio"
_pf_series = "portfolio (selected)" if _whatif else "portfolio"

# Headline metrics
if show_overlay and overlay is not None and "scaled_return" in overlay.columns:
    m = compute_metrics(overlay["scaled_return"].dropna())
    if _whatif:
        st.warning(
            f"**What-if blend.** These figures rebuild the portfolio from the "
            f"{len(selected)} selected strategies, not the {len(strategy_returns)} the "
            f"pipeline ran. Picking a subset after seeing the results is not a portfolio "
            f"anyone could have held — select every strategy for the reported number.",
            icon=":material/science:",
        )
    c1, c2, c3, c4, c5 = st.columns(5)
    # Reference figures are third-party research kept out of this repo; when the
    # local file is absent the tiles simply carry no comparison delta.
    _has_ref = "portfolio" in REF_BENCHMARK.index and not _whatif

    def _ref(col: str, fmt: str) -> str | None:
        if not _has_ref:
            return None
        return f"Ref: {format(REF_BENCHMARK.loc['portfolio', col], fmt)}"

    c1.metric(f"{_pf_label} Sharpe", f"{m['sharpe_ratio']:.2f}", _ref("ref_sharpe", ".2f"))
    c2.metric(f"{_pf_label} Return", f"{m['annualized_return']:.1%}", _ref("ref_return", ".1%"))
    c3.metric(f"{_pf_label} Vol", f"{m['annualized_vol']:.1%}", _ref("ref_vol", ".1%"))
    c4.metric(f"{_pf_label} MaxDD", f"{m['max_drawdown']:.1%}", _ref("ref_max_dd", ".1%"))
    dr = compute_diversification_ratio(sel_returns or strategy_returns)
    c5.metric("Diversification ratio", f"{dr:.2f}", "Ref: ~2.0" if _has_ref else None)

    with st.expander("How the portfolio is constructed"):
        try:
            _c = load_config()["overlay"]
            _scheme, _target, _lb = _c["weighting"], _c["vol_target"], _c["vol_lookback_days"]
        except Exception:
            _scheme, _target, _lb = "equal", None, 63
        _raw, _sf = overlay["raw_return"].dropna(), overlay["scale_factor"].dropna()
        _ann = 252 ** 0.5
        st.markdown(
            f"""
The **portfolio** is every strategy run together as one book. It is not a seventh strategy — it is
the other six combined. Built in `src/backtest/portfolio.py`:

1. **Align.** Strategy returns are joined on a common calendar with a row-wise `dropna()`, so the
   portfolio spans only dates where *every* constituent has data. The slowest strategy to warm up
   sets the start date for the whole book.
2. **Blend.** Constituents are combined with **{_scheme}** weighting. Anything flagged
   `in_overlay: false` in the config is excluded — that is what stops the extra carry variants
   from counting the same bet four times.
3. **Measure risk.** A rolling **{_lb}-day** standard deviation of the blended return, annualised
   by √252.
4. **Scale to target.** `scale_factor = {f"{_target:.1%}" if _target else "target"} / rolling_vol`,
   capped at **3x**, then shifted one day before it is applied — so today's size uses only
   volatility known through yesterday. No lookahead.

Realised on this run: raw blended vol **{_raw.std() * _ann:.2%}**, scaled to
**{compute_metrics(overlay["scaled_return"].dropna())["annualized_vol"]:.2%}** at a mean leverage of
**{_sf.mean():.2f}x**, pinned at the 3x cap on **{(_sf >= 2.999).mean():.1%}** of days.

Blending six streams that disagree is what makes the book quieter than its parts — the source of the
diversification ratio above. Note that vol targeting is **Sharpe-neutral**: it resizes the book, it
does not improve the signals.
"""
        )

if not sel_returns:
    st.info("Select at least one strategy in the sidebar.")
    st.stop()

st.subheader("Cumulative return (net of costs)")
cum_df = pd.DataFrame({k: cumulative(v) for k, v in sel_returns.items()})
if show_overlay and overlay is not None and "scaled_return" in overlay.columns:
    cum_df[_pf_series] = cumulative(overlay["scaled_return"].dropna())
fig = px.line(cum_df, labels={"value": "Equity", "index": "Date", "variable": "Strategy"})
if log_scale:
    fig.update_yaxes(type="log")
fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("Drawdown")
dd_df = pd.DataFrame({k: drawdown(v) for k, v in sel_returns.items()})
if show_overlay and overlay is not None and "scaled_return" in overlay.columns:
    dd_df[_pf_series] = drawdown(overlay["scaled_return"].dropna())
fig_dd = px.area(dd_df, labels={"value": "Drawdown", "index": "Date", "variable": "Strategy"})
fig_dd.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
fig_dd.update_yaxes(tickformat=".0%")
st.plotly_chart(fig_dd, width="stretch")

st.subheader("Rolling Sharpe")
# This control drives only the chart below it, so it sits here rather than in the
# shared sidebar, where it looked global but affected nothing on the other pages.
rolling_window = st.select_slider(
    "Window",
    options=[63, 126, 252, 504],
    value=252,
    format_func=lambda d: f"{d}d  ({d // 21}m)",
    key="perf_rolling_window",
    help="Trailing window for the Sharpe calculation. Shorter is noisier and starts "
         "earlier; longer is smoother but discards more history at the start.",
)
rs_df = pd.DataFrame({k: rolling_sharpe(v, rolling_window) for k, v in sel_returns.items()})
if show_overlay and overlay is not None and "scaled_return" in overlay.columns:
    rs_df[_pf_series] = rolling_sharpe(overlay["scaled_return"].dropna(), rolling_window)
fig_rs = px.line(rs_df, labels={"value": "Sharpe", "index": "Date", "variable": "Strategy"})
fig_rs.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
fig_rs.add_hline(y=0, line_dash="dot", line_color="grey")
st.plotly_chart(fig_rs, width="stretch")
