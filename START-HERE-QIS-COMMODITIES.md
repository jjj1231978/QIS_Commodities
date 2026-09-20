# Start here

A refinement package for the Sys Commodities Research Demo viewer, built to be handed
to Claude CLI. Same shape and palette as the `dl-research-demo` and
`ml-short-reversion` packages.

## What is in it

```
refinement/
  START-HERE.md              this file
  BRIEF.md                   findings, evidence, and the visual system spec
  TASKS.md                   18 tasks in 3 tiers, each independently committable
  assets/
    streamlit-config.toml    drop-in replacement for .streamlit/config.toml
    theme.py                 new file: app/lib/theme.py
```

## Install

From the repo root:

```bash
git checkout -b refine/visual-system
unzip ~/Downloads/qis-commodities-refinement.zip -d .
git add refinement && git commit -m "docs: add refinement package"
```

Add it to `deploy_hf.sh`'s exclusions (T0.8) so it does not ship to the Space, and
delete it once the work is merged.

## Kick off the CLI

```bash
cd /path/to/qis-commodities
claude
```

Then paste this:

> Read `refinement/BRIEF.md` and `refinement/TASKS.md`. You are implementing this
> package.
>
> First, run `git remote -v` and tell me the GitHub URL. Several tasks need it.
>
> Then work one task at a time, in order, starting with T0.1. For each task: make the
> change, verify it against the task's acceptance criteria, show me the diff, and wait
> for me to approve before you commit. Do not start the next task until I say go.
>
> Hard constraints:
> - Presentation only. Nothing under `src/` changes. If a task appears to need it,
>   stop and tell me.
> - Never change a number, or a caption that states a result or a limitation.
> - The Data page's CSV downloads keep their current column keys. Display names go on
>   figures and rendered tables only.
> - The correlation heatmap's cmin/cmax of -1/+1 and its texttemplate stay. They are
>   correct.
> - Anything the app imports must be in `requirements-space.txt`.
> - Deploy with `./deploy_hf.sh`, never a direct push to the `hf` remote.
> - Tick the checkbox in `TASKS.md` as each task lands.
>
> Start with T0.1 and stop when it is ready for review.

## Suggested order across sittings

| Sitting | Tasks | Roughly |
|---|---|---|
| 1 | T0.1, T0.2, T0.6, T0.7 | 1 hour, naming and packaging |
| 2 | T0.4, T0.5, T0.8 | 45 min, file cleanup. Review these yourself, they move and delete files |
| 3 | T1.1, T1.2, T1.3 | 1 hour, and the site changes character |
| 4 | T1.4, T1.5, T0.3 | 2 hours, the charts and the names |
| 5 | T1.6, T1.7 | 1 hour, Sharpe chart and heading semantics |
| 6 | Tier 2, V1 to V5 | half a day, framing and verification |

T0.3 sits in sitting 4 rather than its numbered slot because it depends on T1.2
shipping the display-name mapping.

Stopping after sitting 5 leaves a site that looks finished. Tier 2 is what makes a
visitor read 0.47 as rigour rather than as a weak result.

## The thing this package is really about

The portfolio Sharpe is 0.47, and three of five sleeves are negative or flat.

Your README handles that well: carry and value carry the book, congestion is flat by
construction, and four limitations are named. The app says none of it. A visitor
lands on "Data", two tables, and no statement of what any of it is.

So the point is not to dress up 0.47. It is that the method is the result here: a
common term structure panel, five signals on it, a cost model, a vol-targeting
overlay with the lookahead removed, and a sixth strategy dropped for a stated reason
rather than quietly redefined. T2.2 is the task that puts that in front of a visitor,
and it is the highest-value task in the package.

## Three decisions that are yours

**The project name (T0.1).** It currently has three: `qis-commodities` in the URL,
"Sys Commodities Research Demo" on the page, and neither is a phrase anyone will
recognise. Renaming the Space means a new URL and breaks any link you have shared.
Accepting the slug means everything else has to agree with it. The task will not pick
for you.

**URL paths (T0.2).** "Strategy Lab" currently lives at `/performance` and
"Performance Metrics" at `/stats`. Fixing that breaks old links. Check whether you
have sent either to anyone before letting the CLI do it.

**Dependency ceilings (T0.7).** The suggested `plotly<7.0` will break the build
immediately if the Space already resolves to Plotly 7. Check first. This is the one
task that can take the Space down.

## What the package deliberately protects

Three things this site already gets right, called out in the brief so nobody
"improves" them:

- **The correlation heatmap** fixes `cmin`/`cmax` at -1 and +1 and annotates every
  cell. That is exactly the mistake dl-research-demo makes, and you did not make it
  here.
- **Data is the first page**, and it is the source tables with CSV downloads and
  derivation expanders. Leading with inputs rather than a headline is unusual and
  good.
- **"Why there are five strategies, not six."** The F12 coverage numbers and the
  refusal to quietly redefine the sleeve as F0/F6 is the best writing on the site.

If the CLI proposes touching any of those, say no.

## Where the findings came from

Measured against the deployed Space on 2026-09-20, or read from the Space's own file
tree: the six injected trace colours, the 8-button modebar, the vertical legend at
x=1.02, the mixed scattergl/scatter renderers, the full `.streamlit/config.toml`, the
four nav hrefs, and caption line lengths taken from range rectangles rather than
container widths (131 and 138 characters on a single line).

One thing I checked and am **not** reporting: the correlation heatmap carries
`"Click to enter X axis title"` in its internal layout object. No title node is
rendered in the DOM. It is Plotly's placeholder, not something a visitor sees, and
needs no task.
