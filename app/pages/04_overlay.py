"""Overlay page: vol-targeted multi-strategy overlay diagnostics."""

import plotly.express as px
import streamlit as st

from src.config import load_config

from app.lib import data_loader as dl
from app.lib.plots import cumulative

st.title("Overlay detail")
st.caption(
    "The overlay is the combined book — every strategy run together as one portfolio, "
    "then levered or de-levered to hold a constant volatility target."
)

strategy_returns = dl.load_strategy_returns()
overlay = dl.load_overlay()

if not strategy_returns and overlay is None:
    dl.render_no_data_warning()
    st.stop()

strategy_returns, overlay, _, _, _ = dl.render_sidebar(strategy_returns, overlay)

if overlay is None:
    st.info("No overlay file found. Run the pipeline with ≥2 strategies enabled.")
    st.stop()

# --- How it is built: config-driven so the note cannot drift from the run ---
try:
    _ocfg = load_config()["overlay"]
    _target = _ocfg["vol_target"]
    _lookback = _ocfg["vol_lookback_days"]
    _scheme = _ocfg["weighting"]
except Exception:  # config unreadable — fall back to the frame alone
    _target, _lookback, _scheme = None, None, None

_scaled = overlay["scaled_return"].dropna()
_raw = overlay["raw_return"].dropna()
_sf = overlay["scale_factor"].dropna()
_ann = 252 ** 0.5

m = st.columns(5)
m[0].metric("Raw blended vol", f"{_raw.std() * _ann:.2%}", help="Equal-weighted blend before any leverage is applied.")
m[1].metric("Vol target", f"{_target:.2%}" if _target else "—", help="Configured in overlay.vol_target.")
m[2].metric("Realised vol", f"{_scaled.std() * _ann:.2%}", help="Achieved volatility of the scaled overlay.")
m[3].metric("Mean leverage", f"{_sf.mean():.2f}x", help="Average scale factor applied.")
m[4].metric("Days at cap", f"{(_sf >= 2.999).mean():.1%}", help="Share of days pinned at the 3x leverage cap, running below target.")

with st.expander("How the overlay is built"):
    st.markdown(
        f"""
Built in `src/backtest/portfolio.py` in three steps.

**1 — Blend.** The enabled strategies are combined with **{_scheme or "equal"}** weighting.
Strategies flagged `in_overlay: false` in the config are left out — that is how the extra carry
variants are kept from quadruple-counting a single bet.

**2 — Measure risk.** A rolling **{_lookback or 63}-day** standard deviation of the blended return,
annualised by √252. This is the *pre-scale* vol plotted on the right below.

**3 — Scale to target.** `scale_factor = {f"{_target:.1%}" if _target else "target"} / rolling_vol`,
capped at **3x**. The factor is shifted one day before it is applied, so today's position uses only
volatility estimated through yesterday — there is no lookahead.

The reported overlay return is `scaled_return`, i.e. the blended return times the lagged scale factor.

---

**Two things to keep in mind when reading these charts.**

The builder aligns strategies with a row-wise `dropna()`, so the overlay only spans dates where
*every* constituent has data. The slowest strategy to warm up sets the start date for the whole
portfolio.

Vol targeting is **Sharpe-neutral** — it moves return and volatility together. It changes the size of
the book, never the quality of the signals underneath it.
"""
    )

st.subheader("Vol-targeted overlay")
cols = st.columns(2)
with cols[0]:
    fig = px.line(
        cumulative(overlay["scaled_return"].dropna()),
        title="Cumulative return (vol-targeted)",
    )
    fig.update_layout(height=320, showlegend=False, margin=dict(l=10, r=10, t=40, b=10),
                      yaxis_title="cum ret", xaxis_title="Date")
    st.plotly_chart(fig, width="stretch")
with cols[1]:
    fig = px.line(
        overlay[["rolling_vol"]].dropna(),
        title="Rolling realised vol (pre-scale)",
    )
    fig.update_layout(height=320, showlegend=False, margin=dict(l=10, r=10, t=40, b=10),
                      yaxis_title="Annualised vol", xaxis_title="Date")
    fig.update_yaxes(tickformat=".1%")
    st.plotly_chart(fig, width="stretch")

st.subheader("Vol-target scale factor")
fig = px.line(
    overlay[["scale_factor"]].dropna(),
)
fig.update_layout(height=260, showlegend=False, margin=dict(l=10, r=10, t=10, b=10),
                  yaxis_title="Leverage", xaxis_title="Date")
fig.add_hline(y=1.0, line_dash="dot", line_color="grey")
st.plotly_chart(fig, width="stretch")
