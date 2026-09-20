"""app/lib/theme.py: one visual system for the viewer.

Wire it into app/streamlit_app.py BEFORE st.navigation(...):

    from app.lib.theme import apply_page_chrome
    apply_page_chrome()
    nav = st.navigation(pages)
    nav.run()

Anything the entry script emits after nav.run() is discarded, because the
page script has already owned and closed the main container by then.

Everything here is presentation. No signal, backtest or metric code.

The palette matches the dl-research-demo and ml-short-reversion packages on
purpose. Three public Spaces from the same author in the same field should
read as one body of work.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ----------------------------------------------------------------------
# Palette
# ----------------------------------------------------------------------
INK = "#1A1D24"          # body text
MUTED = "#5B6472"        # captions, axis labels, secondary values
RULE = "#E2E6EB"         # gridlines, borders, dividers
ACCENT = "#1F4E79"       # primary, and the portfolio line in every chart

NEGATIVE = "#9C4F4F"     # brick: serious without reading as an alarm

# Fixed colour per strategy, keyed on the dataframe column name, so a sleeve
# keeps its colour on every page and survives a change to the strategy
# filter. Streamlit currently assigns these by position from its own
# palette, which puts the portfolio in pale mint (#7defa1) as the faintest
# line on the chart, and produces three near-identical pairs.
#
# Congestion gets a quiet slate deliberately. It is out of the market
# outside business days 1 to 9 and carries 0.6% vol, so a hairline in a
# quiet colour is the honest rendering, not a bug to compensate for.
STRATEGY_COLOURS: Mapping[str, str] = {
    "portfolio": "#1F4E79",       # deep blue, the subject
    "carry": "#C77B3C",           # amber
    "value": "#4C8C7A",           # teal
    "trend": "#8A6FA0",           # violet
    "congestion": "#6E7B8B",      # slate
    "basis_momentum": "#9C4F4F",  # brick
}

# Fallback order for any series not named above.
CATEGORICAL: tuple[str, ...] = (
    "#1F4E79", "#C77B3C", "#4C8C7A", "#8A6FA0", "#9C4F4F", "#6E7B8B",
)

# Drawn heavier and on top.
LEAD_KEYS: frozenset[str] = frozenset({"portfolio"})

# Diverging scale. The correlation heatmap already fixes cmin/cmax at -1/+1
# and annotates its cells, which is correct: leave that figure's scale
# bounds alone and let it pick this ramp up from the template.
DIVERGING: tuple[tuple[float, str], ...] = (
    (0.00, "#2C5F8A"),
    (0.25, "#7FA8C4"),
    (0.50, "#F4F1EC"),
    (0.75, "#D79A6A"),
    (1.00, "#A65A34"),
)

SEQUENTIAL: tuple[tuple[float, str], ...] = (
    (0.00, "#F4F6F8"),
    (0.50, "#7FA8C4"),
    (1.00, "#1F4E79"),
)

FONT_STACK = (
    '"Source Sans 3", "Source Sans Pro", -apple-system, BlinkMacSystemFont, '
    '"Segoe UI", Helvetica, Arial, sans-serif'
)


# ----------------------------------------------------------------------
# Display names
# ----------------------------------------------------------------------
#
# One mapping from dataframe keys to the names a reader should see. The
# interface currently shows raw column keys: legend entries read
# "basis_momentum", the correlation axes carry the same five keys, and the
# Sharpe bar x axis carries all six. The README writes them properly.
#
# IMPORTANT: apply this at the figure and at rendered tables only. The Data
# page's CSV exports must keep their current column keys, or anyone's saved
# parsing of those downloads breaks.
#
DISPLAY_NAMES: Mapping[str, str] = {
    "portfolio": "Portfolio",
    "carry": "Carry",
    "value": "Value",
    "trend": "Trend",
    "congestion": "Congestion",
    "basis_momentum": "Basis momentum",
    # Metric and column keys
    "cum_ret": "Cumulative return",
    "max_dd": "Max drawdown",
    "maxdd": "Max drawdown",
    "sharpe": "Sharpe",
    "sortino": "Sortino",
    "calmar": "Calmar",
    "vol": "Volatility",
    "ret": "Return",
}


def label(key: str) -> str:
    """Human name for a dataframe key. Unknown keys get a sensible guess
    rather than passing a snake_case identifier through to the screen."""
    if key in DISPLAY_NAMES:
        return DISPLAY_NAMES[key]
    return str(key).replace("_", " ").strip().capitalize()


def relabel(fig: go.Figure) -> go.Figure:
    """Apply display names to trace names and to categorical axis ticks.

    Handles the legend on the three Strategy Lab charts, the Sharpe bar
    chart's x axis, and the correlation heatmap's x and y labels in one
    call. Leaves the underlying data untouched.
    """
    for trace in fig.data:
        name = getattr(trace, "name", None)
        if name:
            trace.name = label(name)
        # Categorical axes on bar charts and heatmaps
        for axis in ("x", "y"):
            vals = getattr(trace, axis, None)
            if vals is None:
                continue
            seq = list(vals)
            if seq and all(isinstance(v, str) for v in seq):
                setattr(trace, axis, [label(v) for v in seq])
    return fig


# ----------------------------------------------------------------------
# Plotly template
# ----------------------------------------------------------------------
def _build_template() -> go.layout.Template:
    axis = dict(
        showgrid=False,
        zeroline=False,
        linecolor=RULE,
        linewidth=1,
        ticks="outside",
        tickcolor=RULE,
        ticklen=4,
        tickfont=dict(size=12, color=MUTED),
        title=dict(font=dict(size=12, color=MUTED), standoff=10),
        automargin=True,
    )
    return go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT_STACK, size=13, color=INK),
            # Chart titles live in the markdown heading above the figure.
            title=dict(
                font=dict(size=14, color=INK),
                x=0,
                xanchor="left",
                y=0.97,
                pad=dict(b=10),
            ),
            colorway=list(CATEGORICAL),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=8, r=8, t=28, b=8),
            xaxis={**axis},
            # Horizontal gridlines only. The reader compares values, not dates.
            yaxis={**axis, "showgrid": True, "gridcolor": RULE, "griddash": "dot"},
            # Horizontal, above the axis, outside the plot area. The three
            # Strategy Lab charts currently pin a vertical legend at x=1.02,
            # which takes a bite out of a 970px plot for no gain.
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.0,
                xanchor="left",
                x=0,
                title_text="",
                font=dict(size=12, color=MUTED),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
            ),
            hoverlabel=dict(
                bgcolor="#FFFFFF",
                bordercolor=RULE,
                font=dict(family=FONT_STACK, size=12, color=INK),
            ),
            hovermode="x unified",
            colorscale=dict(
                diverging=list(DIVERGING),
                sequential=list(SEQUENTIAL),
                sequentialminus=list(SEQUENTIAL),
            ),
            coloraxis=dict(
                colorbar=dict(
                    outlinewidth=0,
                    ticks="outside",
                    ticklen=4,
                    tickfont=dict(size=11, color=MUTED),
                    thickness=10,
                    len=0.8,
                )
            ),
        )
    )


pio.templates["qis"] = _build_template()
pio.templates.default = "plotly_white+qis"


# A published exhibit is not a workbench. The eight-button modebar
# (download, zoom, pan, zoom in, zoom out, autoscale, reset axes,
# fullscreen) reads as leftover tooling.
PLOTLY_CONFIG: dict = {
    "displayModeBar": False,
    "displaylogo": False,
    "scrollZoom": False,
    "responsive": True,
}

PLOTLY_CONFIG_INTERACTIVE: dict = {
    "displaylogo": False,
    "scrollZoom": False,
    "responsive": True,
    "modeBarButtonsToRemove": [
        "select2d",
        "lasso2d",
        "autoScale2d",
        "toggleSpikelines",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
    ],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def plot(fig: go.Figure, *, interactive: bool = False, height: int | None = None) -> None:
    """Render a figure with the house config.

    theme=None is the important argument. Streamlit's default
    (theme="streamlit") injects its own categorical palette into every
    Plotly figure and overrides the template registered above. That is why
    the deployed charts currently come out #0068c9 / #83c9ff / #ff2b2b /
    #ffabab / #29b09d / #7defa1 even though the page code sets no colours.
    """
    if height is not None:
        fig.update_layout(height=height)
    st.plotly_chart(
        fig,
        width="stretch",  # this project runs Streamlit 1.63; use_container_width
                          # is past its removal date and warns on every call
        config=PLOTLY_CONFIG_INTERACTIVE if interactive else PLOTLY_CONFIG,
        theme=None,
    )


def style_strategies(fig: go.Figure, *, relabel_traces: bool = True) -> go.Figure:
    """Fixed colour per sleeve, portfolio heavier and drawn on top.

    Call before relabel() if you call both, or leave relabel_traces=True and
    this does it for you. Matching is on the raw key, so call this while the
    trace names are still dataframe columns.
    """
    lead: list = []
    rest: list = []
    for trace in fig.data:
        key = str(getattr(trace, "name", "") or "")
        colour = STRATEGY_COLOURS.get(key)
        is_lead = key in LEAD_KEYS
        if colour:
            if getattr(trace, "line", None) is not None:
                trace.line.color = colour
                trace.line.width = 2.6 if is_lead else 1.5
            if getattr(trace, "marker", None) is not None:
                trace.marker.color = colour
        (lead if is_lead else rest).append(trace)

    # Portfolio last in the data list means portfolio on top.
    fig.data = tuple(rest + lead)
    return relabel(fig) if relabel_traces else fig


def sharpe_bar(values: Mapping[str, float], *, portfolio_key: str = "portfolio") -> go.Figure:
    """Signed bars, a zero reference line, and the portfolio set apart.

    The current chart paints every bar one blue for values running -0.41 to
    1.15, does not distinguish the portfolio from the five sleeves, and
    draws no zero line. Sign and magnitude are the chart's only subject.

    Sleeves sort descending by Sharpe; the portfolio is pinned last so the
    reader sees the ranking, then the combination.
    """
    items = {str(k): float(v) for k, v in values.items()}
    port = items.pop(portfolio_key, None)
    ordered = sorted(items.items(), key=lambda kv: kv[1], reverse=True)
    if port is not None:
        ordered.append((portfolio_key, port))

    names = [label(k) for k, _ in ordered]
    vals = [v for _, v in ordered]
    colours = [
        ACCENT if k == portfolio_key else (ACCENT if v >= 0 else NEGATIVE)
        for k, v in ordered
    ]
    widths = [1.6 if k == portfolio_key else 0 for k, _ in ordered]

    fig = go.Figure(
        go.Bar(
            x=names,
            y=vals,
            marker=dict(
                color=colours,
                line=dict(color=INK, width=widths),
            ),
            texttemplate="%{y:.2f}",
            textposition="outside",
            textfont=dict(size=11, color=MUTED),
            hovertemplate="%{x}<br>Sharpe %{y:.3f}<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_hline(y=0, line_width=1, line_color=MUTED)
    fig.update_layout(
        height=380,
        margin=dict(l=8, r=8, t=24, b=8),
        xaxis=dict(title_text="", showgrid=False),
        yaxis=dict(title_text="Sharpe"),
        hovermode="closest",
        bargap=0.35,
    )
    return fig


def mask_upper_triangle(fig: go.Figure) -> go.Figure:
    """Optional: drop the duplicated upper triangle of a correlation matrix.

    The heatmap is already correctly built (cmin/cmax fixed at -1/+1, cells
    annotated), so this is a refinement, not a repair. Leave the scale bounds
    alone.
    """
    import math

    for trace in fig.data:
        z = getattr(trace, "z", None)
        if z is None:
            continue
        rows = [list(r) for r in z]
        n = len(rows)
        for i in range(n):
            for j in range(n):
                if j >= i:
                    rows[i][j] = math.nan
        trace.z = rows
    return fig


# ----------------------------------------------------------------------
# Page chrome
# ----------------------------------------------------------------------
_CSS = """
<style>
/* 1. Measure. layout="wide" with no cap lets a caption run 138 characters
      on a single line at 1440px, and unbounded on a 27-inch display. Cap
      the prose; charts, tables and dataframes keep the full width. */
[data-testid="stMainBlockContainer"] {
    max-width: 1180px;
    padding-top: 3rem;
    padding-bottom: 6rem;
}
[data-testid="stMainBlockContainer"] p,
[data-testid="stMainBlockContainer"] li,
[data-testid="stMainBlockContainer"] blockquote {
    max-width: 74ch;
}
[data-testid="stMainBlockContainer"] [data-testid="stCaptionContainer"],
[data-testid="stMainBlockContainer"] [data-testid="stCaptionContainer"] p {
    max-width: 78ch;
    line-height: 1.55;
}

/* 2. Headings. Tighter tracking and leading than the Streamlit default,
      which is tuned for dashboards rather than for reading. */
[data-testid="stMainBlockContainer"] h1 {
    font-size: 2.1rem;
    line-height: 1.18;
    letter-spacing: -0.018em;
    margin-bottom: 0.15rem;
}
[data-testid="stMainBlockContainer"] h2 {
    font-size: 1.35rem;
    letter-spacing: -0.012em;
    margin-top: 2.75rem;
    padding-top: 1.25rem;
    border-top: 1px solid #E2E6EB;
}
[data-testid="stMainBlockContainer"] h3 {
    font-size: 1.05rem;
    letter-spacing: -0.006em;
    margin-top: 1.75rem;
}

/* 3. Sidebar: project title, nav, then filters. The title is currently an
      h1, which gives every page two h1s. T1.7 demotes it to a div with
      this class, which keeps the look and fixes the semantics. */
[data-testid="stSidebar"] { border-right: 1px solid #E2E6EB; }
.qis-sidebar-title {
    font-size: 1.02rem;
    font-weight: 650;
    line-height: 1.25;
    letter-spacing: -0.01em;
    color: #1A1D24;
    margin: 0.25rem 0 1.25rem;
}
[data-testid="stSidebarNav"] a { font-size: 0.86rem; }
[data-testid="stSidebarNav"] a[aria-current="page"] {
    font-weight: 650;
    color: #1A1D24;
}
[data-testid="stSidebar"] h2 {
    font-size: 0.7rem;
    font-weight: 650;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5B6472;
    border: none;
    margin-top: 1.6rem;
    margin-bottom: 0.4rem;
    padding-top: 0;
}
[data-testid="stSidebar"] label { font-size: 0.82rem; }

/* 4. Numbers. The subject here is a table of Sharpes, so figures align. */
[data-testid="stMetricValue"],
[data-testid="stDataFrame"],
[data-testid="stTable"] { font-variant-numeric: tabular-nums; }
[data-testid="stMetricLabel"] {
    font-size: 0.72rem;
    font-weight: 650;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #5B6472;
}

/* 5. Calm the running indicator. */
[data-testid="stStatusWidget"] { font-size: 0.75rem; }

/* 6. Reserve the scrollbar gutter, so a layout change that toggles the
      scrollbar does not also change the content width and rewrap text. */
section[data-testid="stMain"] { scrollbar-gutter: stable; }
</style>
"""


def apply_page_chrome() -> None:
    """Inject the shared CSS. Call from app/streamlit_app.py BEFORE
    st.navigation(...)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_title(text: str) -> None:
    """Render the project title in the sidebar without a second h1."""
    st.sidebar.markdown(
        f'<div class="qis-sidebar-title">{text}</div>', unsafe_allow_html=True
    )


def page_header(*, title: str, standfirst: str, meta: str | None = None) -> None:
    """H1, a standfirst, and an optional run-context line.

    The Data page currently opens on "Data" and two tables, so a visitor has
    no statement of what is being measured, over what period or universe, or
    that it is backtested. `meta` is where that goes.

    Take the wording from the README so the two cannot drift.
    """
    st.markdown(f"# {title}")
    st.markdown(
        f'<p style="max-width:70ch;font-size:1.05rem;line-height:1.55;color:{INK};'
        f'border-left:3px solid {ACCENT};padding-left:1rem;margin:1.1rem 0 1rem;">'
        f"{standfirst}</p>",
        unsafe_allow_html=True,
    )
    if meta:
        st.markdown(
            f'<p style="color:{MUTED};font-size:.82rem;margin:0 0 2rem;'
            f'font-variant-numeric:tabular-nums;">{meta}</p>',
            unsafe_allow_html=True,
        )


def stat_row(stats: Sequence[tuple[str, ...]]) -> None:
    """Label/value pairs that never truncate.

    The five Strategy Lab metric cards are not truncating, so keep st.metric
    there. Use this only where a value is too wide for a card, such as the
    sample date range.

    Each item is (label, value) or (label, value, hint).
    """
    cols = st.columns(len(stats), gap="large")
    for col, item in zip(cols, stats):
        name, value = item[0], item[1]
        hint = item[2] if len(item) > 2 else ""
        with col:
            st.markdown(
                f'<div style="font-size:.7rem;font-weight:650;letter-spacing:.07em;'
                f'text-transform:uppercase;color:{MUTED};margin-bottom:.25rem;">'
                f"{name}</div>"
                f'<div style="font-size:1.45rem;font-weight:600;line-height:1.15;'
                f'color:{INK};font-variant-numeric:tabular-nums;white-space:nowrap;">'
                f"{value}</div>"
                + (
                    f'<div style="font-size:.75rem;color:{MUTED};margin-top:.2rem;">'
                    f"{hint}</div>"
                    if hint
                    else ""
                ),
                unsafe_allow_html=True,
            )
