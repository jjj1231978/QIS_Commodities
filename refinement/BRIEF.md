# Refinement brief: Sys Commodities Research Demo

**Space:** https://huggingface.co/spaces/JJ-JIN12345/qis-commodities
**Live:** https://jj-jin12345-qis-commodities.hf.space
**Reviewed:** 2026-09-20, against the deployed Space
**Goal:** the site should present the method as confidently as the README does.

This document is the *why*. `TASKS.md` is the *what*. Read this once, then work from
`TASKS.md`.

Every finding below was measured against the deployed Space or read from the Space's
own file tree. Where something came from an automated read of a source file rather
than direct observation, it is marked "verify".

---

## 1. What is already right

Two of these are things the other two Spaces got wrong, so they are worth naming
before the list of problems.

- **The correlation heatmap is built properly.** `cmin = -1`, `cmax = 1`, so the unit
  diagonal cannot saturate the scale and squash the off-diagonal values, and
  `texttemplate: "%{z:.2f}"` annotates every cell. This is the exact mistake the
  dl-research-demo heatmap makes. Do not let anyone "fix" this one.
- **Data is the first page in the navigation, deliberately**, and it is the source
  tables with CSV downloads and expanders deriving each column. Leading with the
  inputs rather than a headline number is an unusual and good choice for research.
- **The Performance Metrics page handles the missing reference honestly.** When the
  third-party comparison file is absent it says so in a caption and shows realised
  metrics only. Nothing breaks and nothing is faked.
- **"Why there are five strategies, not six."** The README section explaining that
  backwardation momentum was dropped, with the F12 coverage numbers and the explicit
  refusal to quietly redefine it as F0/F6, is the best thing on the site. It is the
  same class of writing as the baseline correction in ml-short-reversion.
- **"Backtested research, not a track record"** sits high in the README, where it
  belongs.
- **No metric value truncates** at any width checked.

## 2. The framing problem worth naming first

The portfolio Sharpe is 0.47. Three of the five sleeves are negative or flat: trend
0.08, congestion -0.30, basis momentum -0.41.

The README handles this well. It says carry and value carry the book, explains why
congestion's line is nearly flat by construction, and lists four honest limitations.
The app does not do any of that. A visitor who lands on the Strategy Lab page sees a
tangle of six lines, a 0.47, and three sleeves that lose money, with no framing at
all.

So the refinement is not about dressing up 0.47. The value here is the method: a
common term structure panel, five signals built on it, a documented cost model, a
vol-targeting overlay with the lookahead removed, and a sixth strategy dropped for a
stated reason. **The site should sell the process, because the process is the
result.** Several tasks below follow from that, T2.2 in particular.

---

## 3. Findings

### 3.1 The project has three names

| Where | Name |
|---|---|
| Space URL | `qis-commodities` |
| README H1, page title, sidebar H1 | Sys Commodities Research Demo |
| Space front matter `title` | Sys Commodities Research Demo |

A visitor arrives at a URL saying QIS and lands on a page saying Sys. Neither is a
phrase anyone will recognise, and "Sys" reads like a truncated variable name.

It runs deeper than the title. Nav labels and URL paths disagree:

| Nav label | URL path | File |
|---|---|---|
| Data | `/` | `app/pages/05_data.py` |
| Strategy Lab | `/performance` | `app/pages/01_performance.py` |
| Performance Metrics | `/stats` | `app/pages/02_stats.py` |
| Correlations | `/correlations` | `app/pages/03_correlations.py` |

Someone who shares a link to "Strategy Lab" sends a URL ending `/performance`. And
the file numbering runs `01_performance` through `05_data` while the navigation runs
Data first, so anyone opening `app/pages/` reads the order backwards.

`app/pages/04_overlay.py` ships to the Space and is not in the navigation at all. The
README says so plainly, which is honest, but a dead page in a published artifact is
still a dead page.

### 3.2 Internal identifiers are showing in the interface

Measured from the rendered figures:

- Legend entries on all three Strategy Lab charts: `carry`, `value`, `trend`,
  `congestion`, `basis_momentum`, `portfolio`. Lowercase, and `basis_momentum` is a
  snake_case Python identifier.
- Correlation heatmap axis labels: the same five raw keys.
- Sharpe bar chart x axis: the same six raw keys.
- Cumulative chart y-axis title: `cum ret`.
- Metric label: `Portfolio MaxDD`, alongside `Portfolio Vol` and `Portfolio Return`.

The README writes these correctly everywhere: Carry, Value, Trend, Congestion, Basis
momentum, Portfolio. The app is showing its dataframe columns.

This is one fix, not six: a single display-name mapping applied wherever a key
reaches the screen.

### 3.3 No theme at all

`.streamlit/config.toml` in full:

```toml
# Port must agree with the Dockerfile EXPOSE and the README front-matter
# app_port, or the HF Space renders a blank page.
[server]
port = 7860
address = "0.0.0.0"
headless = true

[browser]
gatherUsageStats = false
```

There is no `[theme]` block, not even `base`. Of the three Spaces this is the most
default. Every widget renders in Streamlit's `#FF4B4B`.

### 3.4 The chart palette actively hides the portfolio

This is the most consequential finding on the site.

Streamlit is injecting its own categorical palette into every Plotly figure, because
`st.plotly_chart` runs with its default `theme="streamlit"`. Measured trace colours on
the Strategy Lab cumulative chart:

| Series | Colour |
|---|---|
| carry | `#0068c9` blue |
| value | `#83c9ff` light blue |
| trend | `#ff2b2b` red |
| congestion | `#ffabab` light red |
| basis_momentum | `#29b09d` teal |
| **portfolio** | **`#7defa1` pale mint** |

Three problems follow from that sequence.

**The portfolio is the faintest line on the chart.** Combining five sleeves into one
vol-targeted book is the entire point of the page, and it is drawn in the palest
colour, last in the order, at the same stroke width as everything else.

**The palette is three near-identical pairs.** Blue against light blue, red against
light red, teal against light green. At a glance carry and value are one smear, and
so are trend and congestion.

**Red lands on trend by position, not by meaning.** Red reads as a warning. Trend has
a 0.08 Sharpe, so the impression is accidentally apt and entirely unearned, which is
worse than either a neutral colour or a deliberate one.

Fixing this is one registered template plus `theme=None`, because the page code does
not set colours itself.

### 3.5 Other chart problems

- **Legend is vertical at `x = 1.02`**, outside on the right, on all three Strategy
  Lab charts. On a 970px column that takes a bite out of the plot area for no gain.
- **The modebar carries 8 buttons** on every chart (download, zoom, pan, zoom in,
  zoom out, autoscale, reset axes, fullscreen).
- **Renderers are mixed.** Cumulative and rolling Sharpe render as `scattergl`,
  drawdown as `scatter`. Two renderers on one page means two hover behaviours and two
  antialiasing results.
- **The Sharpe bar chart uses one colour for everything.** Values run from -0.41 to
  1.15, the portfolio bar is not distinguished from the five sleeves, and there is no
  zero reference line. A chart whose whole subject is sign and magnitude encodes
  neither.

### 3.6 Line length, worse here than on either other Space

Measured on the Data page at a 1440px viewport, using range rectangles rather than
container widths:

| Element | Rendered |
|---|---|
| sidebar | 300px |
| main block container | 1130px at x=300, `max-width: none` |
| prose column | 970px |
| caption "The tables the rest of the dashboard is computed from..." | **138 characters on one line**, 825px |
| caption "Daily return per strategy, net of modelled..." | **131 characters on one line**, 757px |

Those are single unbroken lines of 131 and 138 characters. The readable range is 50
to 75. These captions are the ones telling a visitor what the tables are, so they are
the worst possible place for it.

### 3.7 Two H1s on every page

Every page renders `H1: Sys Commodities Research Demo` in the sidebar and a second H1
for the page itself. That is wrong semantically, and visually the sidebar title
competes with the page title for the same role.

### 3.8 The Correlations caption cites something the visitor cannot see

The caption reads: "The reference report (p. 27) shows that all strategies are weakly
or negatively correlated, except Congestion/Carry F0-F..."

That report is deliberately unpublished, correctly so. But the Performance Metrics
page handles the same absence gracefully ("Reference-report comparison figures are
third-party research and are not published with this repo, so this build shows
realised metrics only") while Correlations quotes a page number from it as though the
reader could check.

### 3.9 Smaller items

| Item | Where | Problem |
|---|---|---|
| No badges, no GitHub link | `README.md` | Nothing links the source. Same gap as ml-short-reversion. |
| Version floors, no ceilings | `requirements-space.txt` | `streamlit>=1.30`, `plotly>=5.18`, nothing capped. A rebuild can pull a breaking major. |
| `CLAUDE.md` ships to the Space | Space file tree | Agent instructions in the public runtime artifact. |
| No `tests/` in the Space tree | Space file tree | The README says tests are published and gives `pytest tests/`. Check the GitHub repo. |
| `Log scale (cumulative)` | sidebar control | Names the chart it affects in the label rather than in help text. |

---

## 4. The visual system

Same palette as the `dl-research-demo` and `ml-short-reversion` packages. Three public
Spaces from the same author in the same field should read as one body of work.

### 4.1 Palette

| Token | Hex | Use |
|---|---|---|
| `INK` | `#1A1D24` | body text |
| `MUTED` | `#5B6472` | captions, axis labels, secondary values |
| `RULE` | `#E2E6EB` | gridlines, borders, dividers |
| `ACCENT` | `#1F4E79` | primary, and the portfolio line in every chart |

Strategy assignment, fixed so a sleeve is the same colour on every page:

| Series | Hex | Why |
|---|---|---|
| Portfolio | `#1F4E79` deep blue | the subject, drawn at 2.6px |
| Carry | `#C77B3C` amber | |
| Value | `#4C8C7A` teal | |
| Trend | `#8A6FA0` violet | |
| Congestion | `#6E7B8B` slate | a near-flat hairline by construction, so a quiet colour is honest |
| Basis momentum | `#9C4F4F` brick | serious without reading as an alarm |

No two are confusable, lightness varies as well as hue, and none of them is red.

### 4.2 Typography

- Cap prose at `74ch` and captions at `78ch`. Charts, tables and dataframes keep the
  full container width.
- Cap the container at `1180px` so the page has a shape on a wide monitor.
- Demote the sidebar project title from `h1` to a styled `div`, so each page has one
  H1.
- `font-variant-numeric: tabular-nums` on metrics and dataframes.

### 4.3 Charts

- One registered Plotly template (`qis`), set as the default.
- Horizontal gridlines only, dotted.
- No title inside the figure; the markdown heading above it is the title.
- Legend horizontal, above the plot, left-aligned, outside the plot area.
- Modebar off by default.
- `theme=None` on every `st.plotly_chart`, or Streamlit's palette wins.
- One renderer per page.
- Display names applied at the figure, not in the data, so the underlying frames keep
  their machine-readable keys and the CSV downloads are unchanged.

---

## 5. Constraints for whoever implements this

1. **Do not touch `src/`.** Nothing under `src/data/`, `src/signals/`,
   `src/backtest/` or `src/reporting/` changes. Everything here is `app/`,
   `.streamlit/`, `README.md` and `requirements-space.txt`.
2. **Do not change any number**, or any caption that states a result or a limitation.
3. **Do not change the CSV downloads.** The Data page's exports must keep their
   current column keys. Display names are applied to figures and to rendered tables,
   never to the frames that get downloaded.
4. **The correlation heatmap's `cmin`/`cmax` of -1/+1 stays.** It is correct.
5. **The Space installs `requirements-space.txt`, not `requirements.txt`.**
6. **Deployment is `./deploy_hf.sh`.**
7. **One task at a time**, each independently committable.
