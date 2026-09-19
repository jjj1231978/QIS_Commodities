"""Assemble the research pack: structured JSON facts fed to all three agents.

Reads whatever pipeline outputs are available in `data/processed/` (per-strategy
backtest parquets, weights parquets, overlay_portfolio.parquet, stats.csv) and
combines them with hardcoded paper reference values plus the universe / strategy
inventory and known implementation gaps.

Robust to missing files — flags them as `not_yet_produced` rather than failing,
so the report can be smoke-tested before the full pipeline runs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import PROCESSED_DIR, PROJECT_ROOT, load_config

log = logging.getLogger(__name__)

PAPER_PDF = PROJECT_ROOT / "reference_paper.pdf"
PAPER_TEXT_CACHE = PROCESSED_DIR / "_cache" / "paper_text.txt"

STRATEGIES = [
    "carry",
    "value",
    "trend",
    "congestion",
    "basis_momentum",
    "backwardation_momentum",
]


def _extract_paper_text() -> str:
    """Extract text from `reference_paper.pdf`, cached after first extraction."""
    if PAPER_TEXT_CACHE.exists():
        return PAPER_TEXT_CACHE.read_text()
    if not PAPER_PDF.exists():
        log.warning(
            f"Paper PDF not found at {PAPER_PDF}; agents will rely only on "
            "hardcoded reference values."
        )
        return ""
    try:
        import pypdf
    except ImportError:
        log.warning("pypdf not installed; cannot extract paper text. Install: pip install pypdf")
        return ""
    # pypdf emits hundreds of "Ignoring wrong pointing object" warnings on this
    # PDF — silence them so they don't drown the run log.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = pypdf.PdfReader(str(PAPER_PDF))
    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        parts.append(f"\n========== PAGE {i+1} ==========\n")
        parts.append(page.extract_text() or "")
    text = "\n".join(parts)
    PAPER_TEXT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    PAPER_TEXT_CACHE.write_text(text)
    log.info(f"Extracted {len(text):,} chars from paper PDF; cached at {PAPER_TEXT_CACHE}")
    return text


# Strategy inventory — authoritative names + signal source files. Agents must
# reference strategies by these exact names rather than inventing variants.
STRATEGY_INVENTORY = [
    {"name": "carry", "module": "src/signals/carry.py",
     "definition": "Carry F3-F0 baseline (paper p.8 variant 1): long F3, short F0, BCOM-weighted, dollar-neutral."},
    {"name": "carry_f6", "module": "src/signals/carry.py",
     "definition": "Carry F6-F0 (paper p.8 variant 2): long F6, short F0, BCOM-weighted, dollar-neutral."},
    {"name": "carry_beta_hedged", "module": "src/signals/carry.py",
     "definition": "Carry F6-F0 with rolling beta hedge on the front leg (paper p.8 variant 3); orthogonalises spread to F0."},
    {"name": "carry_optimised", "module": "src/signals/carry.py",
     "definition": "Carry with per-commodity contract pair selected ex-ante by realised Sharpe over a 504-day warmup (paper p.8 variant 4)."},
    {"name": "value", "module": "src/signals/value.py",
     "definition": "Cross-sectional mean reversion of front-month price vs 1–5y moving average."},
    {"name": "trend", "module": "src/signals/trend.py",
     "definition": "Multi-lookback momentum (1m/3m/6m/12m) on ratio-adjusted F0 using sign(momentum); equal-weight within sector then across sectors."},
    {"name": "congestion", "module": "src/signals/congestion.py",
     "definition": "Two-basket pre-roll (paper p.16-17): long basket fully rolled by BD pre_roll_end, short basket replicates BCOM rolling BD 5-9. Net = LONG (F1-F0) spread, ramping BD 1->pre_roll_end, decaying BD roll_start->roll_end. Flat otherwise."},
    {"name": "basis_momentum", "module": "src/signals/basis_momentum.py",
     "definition": "Cross-sectional: rank by 3-month change in curve slope (2nd-order polyfit to log term structure, the reference paper's preferred method)."},
    {"name": "backwardation_momentum", "module": "src/signals/backwardation_momentum.py",
     "definition": "Cross-sectional level of F0/F12 (seasonality-neutral curve slope); long backwardated, short contangoed."},
]


# Reference-report figures are NOT in this repo. They are transcribed from a
# third-party research report licensed for personal use, so they live in a
# gitignored local file and are absent from GitHub and the Space. Everything
# downstream degrades to an empty reference rather than failing.
REFERENCE_FILE = PROJECT_ROOT / "data" / "reference" / "benchmark.json"

_REFERENCE_ABSENT = {
    "source": "not published — reference figures are third-party research, kept local",
    "available": False,
}


def load_paper_reference() -> dict:
    """Reference-report benchmark figures, or a placeholder when absent."""
    if not REFERENCE_FILE.exists():
        return dict(_REFERENCE_ABSENT)
    try:
        payload = json.loads(REFERENCE_FILE.read_text())
    except (OSError, ValueError) as exc:
        log.warning(f"Could not read {REFERENCE_FILE}: {exc}")
        return dict(_REFERENCE_ABSENT)
    ref = payload.get("paper_reference", {})
    return {**ref, "available": True} if ref else dict(_REFERENCE_ABSENT)


PAPER_REFERENCE = load_paper_reference()


# Known gaps in this implementation relative to the reference paper. Surfaced to
# agents so they don't have to discover them from the data alone.
KNOWN_GAPS = [
    "Universe is restricted to BCOM constituents available on Databento `GLBX.MDP3` (CME). ICE-listed soft commodities (Sugar, Cotton, Coffee on IFUS.IMPACT) and Gas Oil (IFEU.IMPACT) are stubbed in config but disabled — the paper uses the full BCOM universe.",
    "Backtest start is 2015-06-08 (5y warmup after data lake start 2010-06-06 to give the value strategy's longest 5y MA enough history). Paper sample windows are 2003–2024 for carry / 2002–2024 for trend / 2006–2024 for value, basis momentum, backwardation momentum.",
    "Intraday trend (paper page 13–15, SR 0.50) is out of scope — it requires minute bars. The signal module is stubbed in `src/signals/` and disabled in `configs/default.yaml`.",
    "All four paper carry variants are now implemented and run side-by-side: carry (F3-F0), carry_f6 (F6-F0), carry_beta_hedged (F6-F0 with rolling 252d beta), carry_optimised (per-commodity best-pair selection from candidate set [(0,2),(0,3),(0,4),(0,6),(0,8)] using a 504-day pre-backtest warmup).",
    "Cost model is per-commodity bid-ask spread (default 2 bps, NG/ZNC/NI/ALI/CT/SB overrides) plus a fixed commission per contract. Time-spread trades (carry, congestion) get a 50% spread discount. No market-impact term and no borrow / margin financing.",
    "Roll calendar is approximated as `roll_offset_days` business days before the first of the delivery month; real BCOM-index rolls happen BD 5-9. Per-commodity exchange-specific notice-day rules (e.g. WTI's last-trade-day) are not modelled.",
    "Term structure F0..F12; for less liquid base/precious metals at the long end (F11/F12), the panel often has NaNs. Backwardation momentum falls back from F12 to the nearest available far contract.",
    "Trend uses sign(momentum) per lookback (1m/3m/6m/12m) averaged across windows, matching the paper. Seasonal rolls for NG/Corn/Wheat are not implemented (paper notes they help but does not specify exact contract calendars).",
    "Basis momentum uses the reference paper's preferred 2nd-order polynomial fit to log(term structure) to extract curve slope, then takes the 63-day change. Set `slope_method: front_spread` in config for the alternative Boons-Prado-style (F1-F0)/F0 momentum.",
    "Congestion now implements the paper's full two-basket pre-roll structure (page 16-17): a long basket rolled BD 1..pre_roll_end and a short basket replicating BCOM's BD 5-9 roll. Net is long the front (F1-F0) time spread during BD 1-roll_end and flat otherwise. Realized vol matches the paper's 'exceptionally low' description (~0.6% vs paper 0.9%).",
    "BCOM weights in `configs/default.yaml` are static — real BCOM weights rebalance annually with target weights set by methodology committee.",
    "Funding rate is treated as zero (excess returns) — matches the paper convention.",
]


def _safe_read_parquet(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as e:
        log.warning(f"Failed to read {path}: {e}")
        return None


def _safe_read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path, index_col=0)
    except Exception as e:
        log.warning(f"Failed to read {path}: {e}")
        return None


def _summarize_strategy(df: pd.DataFrame | None, name: str) -> dict:
    """Headline stats from a `<strategy>_backtest.parquet` (gross/net/turnover)."""
    if df is None or df.empty or "net_return" not in df.columns:
        return {"status": "not_yet_produced"}
    r = df["net_return"].dropna()
    if r.empty:
        return {"status": "not_yet_produced"}
    ann_ret = float(r.mean() * 252)
    ann_vol = float(r.std() * (252 ** 0.5))
    cum = (1 + r).cumprod()
    max_dd = float((cum / cum.cummax() - 1).min())
    out = {
        "status": "available",
        "name": name,
        "n_obs": int(len(r)),
        "date_first": str(r.index.min().date()) if hasattr(r.index, "min") else None,
        "date_last": str(r.index.max().date()) if hasattr(r.index, "max") else None,
        "ann_return": round(ann_ret, 4),
        "ann_vol": round(ann_vol, 4),
        "sharpe": round(ann_ret / ann_vol, 3) if ann_vol > 0 else None,
        "max_dd": round(max_dd, 4),
        "calmar": round(ann_ret / abs(max_dd), 3) if max_dd != 0 else None,
    }
    if "turnover" in df.columns:
        out["avg_daily_turnover"] = round(float(df["turnover"].mean()), 4)
    if "cost" in df.columns:
        out["avg_daily_cost_bps"] = round(float(df["cost"].mean()) * 10000, 4)
    return out


def _summarize_overlay(df: pd.DataFrame | None) -> dict:
    if df is None or df.empty or "scaled_return" not in df.columns:
        return {"status": "not_yet_produced"}
    r = df["scaled_return"].dropna()
    if r.empty:
        return {"status": "not_yet_produced"}
    ann_ret = float(r.mean() * 252)
    ann_vol = float(r.std() * (252 ** 0.5))
    cum = (1 + r).cumprod()
    max_dd = float((cum / cum.cummax() - 1).min())
    out: dict[str, Any] = {
        "status": "available",
        "n_obs": int(len(r)),
        "ann_return": round(ann_ret, 4),
        "ann_vol": round(ann_vol, 4),
        "sharpe": round(ann_ret / ann_vol, 3) if ann_vol > 0 else None,
        "max_dd": round(max_dd, 4),
        "calmar": round(ann_ret / abs(max_dd), 3) if max_dd != 0 else None,
    }
    if "rolling_vol" in df.columns:
        out["realised_rolling_vol_mean"] = round(float(df["rolling_vol"].mean()), 4)
    if "scale_factor" in df.columns:
        out["scale_factor_mean"] = round(float(df["scale_factor"].mean()), 4)
        out["scale_factor_max"] = round(float(df["scale_factor"].max()), 4)
    return out


def _summarize_stats_csv(df: pd.DataFrame | None) -> dict:
    if df is None or df.empty:
        return {"status": "not_yet_produced"}
    return {"status": "available", "rows": df.to_dict(orient="index")}


def _correlation_matrix(strategy_returns: dict[str, pd.Series]) -> dict:
    """Pairwise correlations of net returns; helps gauge diversification."""
    if len(strategy_returns) < 2:
        return {"status": "not_yet_produced"}
    df = pd.DataFrame(strategy_returns).dropna()
    if df.empty:
        return {"status": "not_yet_produced"}
    corr = df.corr().round(3)
    return {"status": "available", "matrix": corr.to_dict()}


def build_research_pack(processed_dir: Path | None = None) -> dict:
    """Assemble the JSON-serialisable research pack."""
    cfg = load_config()
    p_dir = processed_dir or PROCESSED_DIR

    strategies_summary: dict[str, dict] = {}
    strategy_returns: dict[str, pd.Series] = {}
    for name in STRATEGIES:
        df = _safe_read_parquet(p_dir / f"{name}_backtest.parquet")
        strategies_summary[name] = _summarize_strategy(df, name)
        if df is not None and not df.empty and "net_return" in df.columns:
            strategy_returns[name] = df["net_return"].dropna()

    overlay = _safe_read_parquet(p_dir / "overlay_portfolio.parquet")
    stats_csv = _safe_read_csv(p_dir / "stats.csv")

    paper_text = _extract_paper_text()

    pack = {
        "schema_version": 1,
        "source_paper_full_text": paper_text or "(paper PDF not available; agents must rely on hardcoded reference values in `paper_reference`)",
        "run_metadata": {
            "config_universe_size": len(cfg["universe"]["commodities"]),
            "config_data_window": {
                "start": cfg["data"]["start_date"],
                "end": cfg["data"]["end_date"],
            },
            "config_backtest_window": {
                "start": cfg["backtest"]["start_date"],
                "end": cfg["backtest"]["end_date"],
            },
            "config_n_contracts": cfg["data"]["max_contracts"],
            "config_overlay": cfg.get("overlay", {}),
            "config_costs": cfg.get("costs", {}),
            "enabled_strategies": [
                k for k, v in cfg.get("strategies", {}).items()
                if v.get("enabled", False)
            ],
        },
        "strategy_inventory": STRATEGY_INVENTORY,
        "strategies_summary": strategies_summary,
        "overlay_summary": _summarize_overlay(overlay),
        "stats_csv": _summarize_stats_csv(stats_csv),
        "correlation_matrix": _correlation_matrix(strategy_returns),
        "paper_reference": PAPER_REFERENCE,
        "known_implementation_gaps": KNOWN_GAPS,
        "spec_pointer": "specs/001-qis-commodities/ — see spec.md, plan.md, data-model.md",
    }

    has_any_run = (
        any(v.get("status") == "available" for v in strategies_summary.values())
        or pack["overlay_summary"].get("status") == "available"
    )
    pack["pipeline_run_status"] = "completed" if has_any_run else "no_run_yet"

    return pack


def render_pack_markdown(pack: dict) -> str:
    """Render the research pack as a markdown JSON code block."""
    return "```json\n" + json.dumps(pack, indent=2, default=str) + "\n```"


if __name__ == "__main__":
    pack = build_research_pack()
    print(json.dumps(pack, indent=2, default=str))
