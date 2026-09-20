# Refinement tasks

Three tiers. Each leaves the site shippable, so you can stop after any of them.

**Rules of engagement**

- One task, verify, commit, next. Do not batch.
- Presentation only. Nothing under `src/` changes.
- Never change a number, or a caption that states a result or a limitation.
- The Data page's CSV downloads keep their current column keys. Display names go on
  figures and rendered tables, never on the frames that get exported.
- The correlation heatmap's `cmin = -1`, `cmax = 1` and its `texttemplate` stay. They
  are correct, and they are the thing the other two Spaces got wrong.
- Anything the app imports must be in `requirements-space.txt`.
- Deploy with `./deploy_hf.sh`. Do not push to the `hf` remote directly.
- Before T0.1, run `git remote -v` and record the GitHub URL. The package does not
  know it.
- Commit format: `refine(T0.3): unify strategy display names`.

**Status legend:** `[ ]` not started, `[x]` done, `[-]` skipped (say why).

---

# Tier 0: naming, packaging, first impression

No visual changes. This tier is mostly about the project having one name.

## [ ] T0.1 Settle on one project name

**Files:** `README.md` front matter and H1, `app/streamlit_app.py`
(`st.set_page_config(page_title=...)`), `app/pages/*.py` sidebar title

The project currently has three names: the Space URL says `qis-commodities`, the page
title and README say "Sys Commodities Research Demo", and neither is a phrase a
reader will recognise. "Sys" reads as a truncated variable.

**Do:** pick one name and apply it in all four places. A descriptive one beats an
abbreviation: "Systematic Commodity Futures Strategies" or "Commodity Term Structure
Strategies" both say what it is.

The Space slug cannot be changed without a new Space URL, so either rename the Space
(and update every link you have shared) or accept the slug and make everything else
agree. Decide which, and say which in the commit message.

Do **not** rename the GitHub repo as part of this task. That breaks clones.

**Accept:** `grep -rn "Sys Commodities" README.md app/` returns nothing but the chosen
name. The browser tab, the sidebar and the README H1 all match.

---

## [ ] T0.2 Make URL paths match nav labels

**File:** `app/streamlit_app.py`

Nav labels and URLs disagree, so a shared link does not name the page it opens:

| Nav label | URL now | Should be |
|---|---|---|
| Strategy Lab | `/performance` | `/strategy-lab` |
| Performance Metrics | `/stats` | `/metrics` |
| Correlations | `/correlations` | fine |
| Data | `/` | fine, it is the default page |

**Do:** pass an explicit `url_path` to each `st.Page`.

Old links will break. That is acceptable for a demo Space that has not been widely
shared, but check whether you have sent `/performance` or `/stats` to anyone first.
If you have, mark this `[-]` and note why.

**Accept:** every nav label and its URL path describe the same thing. All four pages
load from a cold browser at their new paths.

---

## [ ] T0.3 Unify the strategy display names

**Files:** `app/lib/theme.py` (from T1.2, which ships `DISPLAY_NAMES`),
`app/pages/01_performance.py`, `app/pages/02_stats.py`,
`app/pages/03_correlations.py`, `app/lib/plots.py`

The interface is showing dataframe column keys. Measured on the deployed site:
legend entries read `carry`, `value`, `trend`, `congestion`, `basis_momentum`,
`portfolio`; the correlation heatmap's axes carry the same five; the Sharpe bar x
axis carries all six; the cumulative chart's y axis reads `cum ret`; and one metric
is labelled `Portfolio MaxDD` next to `Portfolio Vol` and `Portfolio Return`.

The README already writes all of these properly.

**Do:** apply `DISPLAY_NAMES` from `theme.py` wherever a key reaches the screen.
`relabel(fig)` handles trace names and categorical axis ticks in one call.

Fix the two stragglers by hand: the y axis `cum ret` becomes `Cumulative return`, and
`Portfolio MaxDD` becomes `Portfolio max drawdown`.

**This task depends on T1.2.** Either run T1.2 first, or do the metric label and axis
title now and come back for the figures.

**Critical:** the mapping is applied at the figure and at rendered tables only. The
Data page's CSV exports keep their current column keys, or you break anyone's saved
parsing.

**Accept:** no snake_case string appears anywhere in the rendered UI. Download both
CSVs and confirm the headers are byte-identical to before.

---

## [ ] T0.4 Resolve the unnavigable overlay page

**File:** `app/pages/04_overlay.py`

It ships to the Space and is not in the navigation. The README says its content was
folded into Performance.

**Do:** confirm nothing imports it:

```bash
grep -rn "04_overlay\|overlay_page\|from app.pages" app/ src/
```

If it is genuinely dead, delete it. If parts are still wanted, fold them in and then
delete it. Either way it should not ship.

Update the README paragraph that describes it, since that paragraph becomes wrong.

**Accept:** `app/pages/` contains only navigated pages. The README no longer mentions
a fifth page. Every page still renders.

---

## [ ] T0.5 Renumber the page files to match the navigation

**Files:** `app/pages/*.py`, `app/streamlit_app.py`

File numbering runs `01_performance` to `05_data` while the navigation runs Data
first. Anyone opening the directory reads the order backwards.

**Do:** `git mv` to match nav order:

```
05_data.py        -> 01_data.py
01_performance.py -> 02_strategy_lab.py
02_stats.py       -> 03_metrics.py
03_correlations.py-> 04_correlations.py
```

Update the four `PAGES_DIR / "..."` references in `app/streamlit_app.py`. Use
`git mv` so history follows.

Do this **after** T0.4, so you are not renumbering a file you are about to delete.

**Accept:** `ls app/pages/` reads in navigation order. All four pages load. `git log
--follow` still works on each.

---

## [ ] T0.6 Add badges and a GitHub link to the README

**File:** `README.md`

There are no badges and no link to the source, despite the README describing a
public GitHub repo as part of the split.

**Do:** insert after the opening paragraph, above the "Backtested research, not a
track record" blockquote, which stays where it is:

```markdown
[![Live demo](https://img.shields.io/badge/🤗%20Spaces-live%20viewer-yellow)](https://huggingface.co/spaces/JJ-JIN12345/qis-commodities)
[![GitHub](https://img.shields.io/badge/GitHub-source-blue)](https://github.com/OWNER/REPO)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)
```

**Accept:** all three badges return 200. The GitHub URL matches `git remote -v`.

---

## [ ] T0.7 Put ceilings on the runtime dependencies

**File:** `requirements-space.txt`

Every line is a floor. Nothing is capped, not even pandas.

**Do:** add upper bounds, keeping every existing comment:

```
pandas>=2.0,<3.0
numpy>=1.24,<3.0
pyarrow>=15.0,<22.0
streamlit>=1.30,<2.0
plotly>=5.18,<7.0
pyyaml>=6.0,<7.0
```

Check each ceiling against what the Space currently resolves to before committing.
`plotly<7.0` in particular: if the Space already runs Plotly 7, that line breaks the
build immediately. This is the one task here that can take the Space down.

**Accept:** a clean install succeeds and the app starts. Every comment survives.

---

## [ ] T0.8 Keep internal files out of the Space build

**File:** `deploy_hf.sh`

`CLAUDE.md` is in the Space's file tree.

**Do:** exclude it, and anything else that is build scaffolding rather than app or
research, from the orphan-branch build. Keep `src/`, `configs/`, `data/processed/`
and the README: the README's published/not-published table promises them.

**Accept:** after the next deploy the Space tree carries no agent or build tooling.
`src/`, `configs/` and `data/processed/` are unchanged.

---

# Tier 1: the visual system

## [ ] T1.1 Install the theme config

**File:** `.streamlit/config.toml`, source at `refinement/assets/streamlit-config.toml`

There is currently no `[theme]` block at all.

**Do:** replace the file with the asset. It keeps your `[server]` and `[browser]`
blocks verbatim, **including the port comment**, and adds `[client]` and `[theme]`.

Check the resolved Streamlit version after T0.7:

- `>= 1.44`: keep everything.
- `1.30` to `1.43`: delete the marked block and `[theme.sidebar]`.
- `< 1.42`: also change `showErrorDetails = "none"` to `showErrorDetails = false`.

**Accept:** the app starts with no config warnings. Widgets render deep blue, not red.
The port is still 7860.

---

## [ ] T1.2 Add the shared UI module

**File:** `app/lib/theme.py` (new), source at `refinement/assets/theme.py`

Goes in `app/lib/` beside `plots.py` and `data_loader.py`. Not in `src/`.

| Name | Purpose |
|---|---|
| `apply_page_chrome()` | shared CSS: measure cap, headings, nav, metrics, sidebar title |
| `page_header(title, standfirst, meta=None)` | H1 plus standfirst and a run-context line |
| `plot(fig, interactive=False, height=None)` | `st.plotly_chart` with `theme=None` and the house config |
| `style_strategies(fig)` | fixed colour per sleeve, portfolio heavier and on top |
| `DISPLAY_NAMES`, `label(key)`, `relabel(fig)` | one mapping from keys to human names |
| `sharpe_bar(series)` | signed bars, zero line, portfolio distinguished |
| `stat_row([...])` | label/value pairs that do not truncate |
| `INK`, `MUTED`, `RULE`, `ACCENT`, `STRATEGY_COLOURS` | palette tokens |

It registers a Plotly template named `qis` and sets `plotly_white+qis` as the default
at import time.

**Accept:** `PYTHONPATH=. python -c "from app.lib.theme import plot, relabel; print('ok')"`
prints `ok`.

---

## [ ] T1.3 Wire the chrome into the entry point

**File:** `app/streamlit_app.py`

There is no style hook yet. Add one, and put it **before** `st.navigation(...)`:
anything the entry script emits after `nav.run()` is discarded, because the page
script has already owned and closed the main container by then.

```python
from app.lib.theme import apply_page_chrome

apply_page_chrome()   # must precede st.navigation

nav = st.navigation(pages)
nav.run()
```

Leave `st.set_page_config(layout="wide")` alone. Do not set
`initial_sidebar_state="expanded"`; the default `"auto"` is already correct and
collapses on a phone.

**Accept:** at 1440px the Data page captions wrap at about 78 characters instead of
running 131 to 138 on one line. Measure with range rectangles in the inspector, not
by eye. At 390px there is no horizontal scroll.

---

## [ ] T1.4 Route every chart through `plot()`

**Files:** `app/pages/*.py`, `app/lib/plots.py`

**Do:**

1. `grep -rn "st.plotly_chart" app/` to find every call site.
2. Replace each with `plot(fig)`. Drop the redundant `use_container_width` and
   `config` arguments.
3. **`theme=None` is the point of this task.** Streamlit is currently injecting its
   own palette (`#0068c9`, `#83c9ff`, `#ff2b2b`, `#ffabab`, `#29b09d`, `#7defa1`)
   into every figure. Without `theme=None` the template you registered never applies.
4. Remove per-figure styling the template now owns: `paper_bgcolor`, `plot_bgcolor`,
   fonts, gridline colours, and the `legend` override that pins the legend vertically
   at `x=1.02`. Keep axis ranges, hovertemplates and the heatmap's `cmin`/`cmax`.
5. **Pick one renderer.** Cumulative and rolling Sharpe currently render as
   `scattergl`, drawdown as `scatter`. Use `scattergl` for all three if the series
   are long enough to need it, otherwise `scatter` for all three. Two renderers on
   one page means two hover behaviours.

**Accept:** `grep -rn "st.plotly_chart" app/` returns only the call inside
`theme.py`. No modebar except where you passed `interactive=True`. One renderer per
page. Every chart shares one font, one grid treatment, one palette.

---

## [ ] T1.5 Fix the strategy colour encoding

**Files:** `app/pages/01_performance.py` (or its renamed form), `app/lib/plots.py`

The most consequential visual problem on the site. Streamlit's palette puts the
portfolio in pale mint `#7defa1`, last in sequence and the faintest line on the
chart, while the combined book is the whole point of the page. The other five come
out as three near-identical pairs, and red lands on trend by position rather than
meaning.

**Do:** call `style_strategies(fig)` on all three Strategy Lab charts. It assigns a
fixed colour per sleeve, gives the portfolio the accent blue at 2.6px, and reorders
so the portfolio draws on top:

| Series | Colour |
|---|---|
| Portfolio | `#1F4E79` deep blue, 2.6px |
| Carry | `#C77B3C` amber |
| Value | `#4C8C7A` teal |
| Trend | `#8A6FA0` violet |
| Congestion | `#6E7B8B` slate |
| Basis momentum | `#9C4F4F` brick |

Congestion gets a quiet slate deliberately: the README explains it is out of the
market outside business days 1 to 9 and carries 0.6% vol, so a hairline in a quiet
colour is the honest rendering rather than a bug to compensate for.

The colours are fixed by key, so a sleeve keeps its colour when the user narrows the
strategy filter. Check that: deselect two strategies and confirm the rest do not
shift colour.

**Accept:** the portfolio is the most prominent line at a glance. No two sleeves are
confusable. Nothing is red. Colours survive a change to the strategy filter.

---

## [ ] T1.6 Rebuild the Sharpe bar chart

**Files:** `app/pages/02_stats.py` (or its renamed form)

Values run from -0.41 to 1.15. Every bar is the same blue, the portfolio is not
distinguished from the five sleeves, and there is no zero line. A chart whose only
subject is sign and magnitude encodes neither.

**Do:** replace the figure with `sharpe_bar(series)` from `theme.py`. It gives
negative bars a muted brick, positive bars the accent blue, the portfolio a heavier
outline, and draws a zero reference line.

Sort descending by Sharpe, with the portfolio pinned last and separated, so the
reader sees the sleeve ranking and then the combination rather than an arbitrary
order.

**Accept:** sign is visible without reading the axis. The portfolio bar is
distinguishable from the sleeves. A zero line is drawn.

---

## [ ] T1.7 Give each page a single H1

**Files:** `app/pages/*.py`, or wherever the sidebar title is rendered

Every page currently renders two H1s: the project title in the sidebar and the page
title in the main column.

**Do:** demote the sidebar title to a styled `div` or `st.sidebar.markdown` with an
explicit class. The CSS in T1.2 already styles `.qis-sidebar-title`, so use that
class and the title keeps its current look with correct semantics.

**Accept:** `document.querySelectorAll('h1').length` is 1 on every page. The sidebar
title looks unchanged.

---

# Tier 2: framing

## [ ] T2.1 Fix the Correlations caption

**File:** `app/pages/03_correlations.py` (or its renamed form)

The caption reads "The reference report (p. 27) shows that all strategies are weakly
or negatively correlated, except Congestion/Carry F0-F...". That report is
deliberately unpublished, so the caption cites a page number the visitor cannot open.

The Performance Metrics page handles the same absence well: "Reference-report
comparison figures are third-party research and are not published with this repo, so
this build shows realised metrics only."

**Do:** rewrite the Correlations caption to state what the realised matrix shows, and
note the reference comparison is unavailable in this build using the same wording as
the Metrics page. Keep the substance of the claim if it is true of the realised data;
drop the page citation.

Do not delete the observation. Move it from "the report says" to "these returns show".

**Accept:** no caption cites a page of an unpublished document. The two pages describe
the missing reference in the same words.

---

## [ ] T2.2 Frame the result on the landing page

**File:** `app/pages/05_data.py` (or `01_data.py` after T0.5)

The portfolio Sharpe is 0.47 and three of five sleeves are negative or flat. The
README handles this well: carry and value carry the book, congestion is flat by
construction, and four limitations are listed. The app says none of it.

A visitor currently lands on "Data", two tables, and no statement of what this is.

**Do:** add a `page_header()` to the Data page with a standfirst and a meta line:

```python
page_header(
    title="Systematic commodity futures strategies",
    standfirst="Five signals built on a common F0 to F12 term structure panel: "
               "carry, value, trend, congestion and basis momentum, combined into "
               "one vol-targeted portfolio. Backtested research, not a track record.",
    meta="2015-06-08 to 2026-05-04  ·  3,391 trading days  ·  17 CME-listed BCOM "
         "constituents  ·  net of modelled transaction costs",
)
```

Then add one short paragraph, taken from the README, saying what the result is and is
not: carry and value carry the book, three sleeves detract over this sample, and the
limitations are documented. Link to the README section rather than restating all four.

Take the wording from the README so the two cannot drift. Introduce no number that is
not already there.

**Do not dress up the 0.47.** The value of this site is the method, and a visitor who
sees the honest framing first reads the rest as rigour rather than as a weak result.

**Accept:** a visitor who reads only the first screen can say what is being measured,
over what period and universe, that it is backtested, and which sleeves drive it.

---

## [ ] T2.3 Move chart-scoping out of control labels

**File:** wherever the sidebar filters are built

`Log scale (cumulative)` names the chart it affects inside its own label.

**Do:** shorten to `Log scale` and move the scope into `help=`. Check the other three
controls (`Strategies`, `Show portfolio`, `Date range`) for the same pattern.

**Accept:** no control label names a chart. Every control has help text where the
scope is not obvious.

---

# Verification

## [ ] V1 Tests

The Space file tree has no `tests/`, but the README says tests are published and
gives `pytest tests/`. Check the GitHub repo. If a suite exists, run it and confirm
it passes. If not, say so and check each page by hand instead.

## [ ] V2 Every page, three widths

All four pages at 390px, 1280px and 1920px:

- no horizontal scroll at any width
- caption measure near 78 characters at 1920px, not 138
- no clipped metric values
- charts legible at 390px, legend does not overlap data
- sidebar collapsed at 390px
- both CSV downloads still work and their headers are unchanged

## [ ] V3 Colour and contrast

- body text on background meets WCAG AA. `#1A1D24` on `#FFFFFF` passes.
- `MUTED` `#5B6472` on `#FFFFFF` is 6.0:1, fine for captions.
- no chart distinguishes series by red versus green alone.
- print the cumulative chart in greyscale: all six series still tellable apart, and
  the portfolio still reads as the heaviest line.

## [ ] V4 Filter interaction

On Strategy Lab, deselect two strategies and confirm the remaining series keep their
colours, the portfolio stays on top, and the what-if flag still appears. Colour
stability under filtering is the thing most likely to break in T1.5.

## [ ] V5 Links and deploy

Every external link returns 200: all badges, the GitHub link, every README link.
Then deploy with `./deploy_hf.sh` and re-check the live Space, not just local.
