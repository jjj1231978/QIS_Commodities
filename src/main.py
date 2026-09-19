"""Pipeline orchestrator — fetch data, compute signals, run backtests."""

import argparse
import logging
import sys

import pandas as pd

from src.backtest.costs import CostModel
from src.backtest.engine import run_strategy_backtest
from src.backtest.metrics import compute_diversification_ratio, compute_metrics
from src.backtest.portfolio import build_overlay_portfolio
from src.reporting.pack import load_paper_reference
from src.config import PROCESSED_DIR, load_config
from src.data.fetch import fetch_all_commodities
from src.data.term_structure import build_term_structure
from src.data.universe import Universe
from src.signals.basis_momentum import BasisMomentumSignal
from src.signals.carry import (
    CarryBetaHedged,
    CarryF6,
    CarryOptimised,
    CarrySignal,
)
from src.signals.congestion import CongestionSignal
from src.signals.trend import TrendSignal
from src.signals.value import ValueSignal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

STRATEGY_CLASSES = {
    "carry": CarrySignal,
    "carry_f6": CarryF6,
    "carry_beta_hedged": CarryBetaHedged,
    "carry_optimised": CarryOptimised,
    "value": ValueSignal,
    "trend": TrendSignal,
    "congestion": CongestionSignal,
    "basis_momentum": BasisMomentumSignal,
}

# Which strategies trade time spreads (affects cost model)
SPREAD_STRATEGIES = {
    "carry",
    "carry_f6",
    "carry_beta_hedged",
    "carry_optimised",
    "congestion",
}

# Reference-report figures are third-party research kept out of this repo (see
# README, "What is and isn't published"). Loaded from the gitignored local file
# when present; the validation log below simply reports nothing without it.
def _load_ref_benchmark() -> dict[str, tuple]:
    ref = load_paper_reference()
    if not ref.get("available"):
        return {}
    out = {
        name: (v["sharpe"], v["ann_return"], v["ann_vol"], v["max_dd"])
        for name, v in ref.get("per_strategy", {}).items()
    }
    ew = ref.get("equal_weight_overlay")
    if ew:
        out["portfolio"] = (ew["sharpe"], ew["ann_return"], ew["ann_vol"], ew["max_dd"])
    return out


REF_BENCHMARK = _load_ref_benchmark()


def main(
    config_name: str = "default",
    only_strategy: str | None = None,
    skip_overlay: bool = False,
    output_dir=None,
):
    """Run the full pipeline.

    Args:
        config_name: YAML config name in `configs/` (without `.yaml`).
        only_strategy: If set, run just this one strategy and skip the overlay.
        skip_overlay: If True, run all strategies but skip the overlay step.
        output_dir: Override `PROCESSED_DIR`. Defaults to `data/processed/`.
    """
    cfg = load_config(config_name)
    universe = Universe.from_config(cfg)
    cost_model = CostModel(cfg)
    out_dir = output_dir if output_dir is not None else PROCESSED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Universe: {len(universe.commodities)} commodities")

    # --- Phase 1: Fetch data ---
    log.info("=== Fetching futures data ===")
    raw_data = fetch_all_commodities(
        universe,
        start=cfg["data"]["start_date"],
        end=cfg["data"]["end_date"],
    )
    log.info(f"Fetched data for {len(raw_data)} commodities")

    # --- Phase 2: Build term structures ---
    log.info("=== Building term structures ===")
    term_structures = {}
    for commodity in universe.commodities:
        if commodity.root not in raw_data:
            continue
        ts = build_term_structure(
            raw_prices=raw_data[commodity.root],
            root=commodity.root,
            months=commodity.months,
            start_year=int(cfg["data"]["start_date"][:4]),
            end_year=int(cfg["data"]["end_date"][:4]),
            n_contracts=cfg["data"]["max_contracts"],
            roll_offset_bdays=cfg["data"]["roll_offset_days"],
        )
        if not ts.empty:
            term_structures[commodity.root] = ts

    log.info(f"Built term structures for {len(term_structures)} commodities")

    # --- Phase 3: Compute signals and run backtests ---
    log.info("=== Running strategy backtests ===")
    strategy_returns: dict[str, pd.Series] = {}
    metrics_rows: list[dict] = []

    candidate_strategies = (
        [only_strategy] if only_strategy else list(STRATEGY_CLASSES)
    )

    for strategy_name in candidate_strategies:
        if strategy_name not in STRATEGY_CLASSES:
            log.error(f"Unknown strategy: {strategy_name}")
            continue
        if not cfg["strategies"].get(strategy_name, {}).get("enabled", False):
            log.info(f"  {strategy_name}: disabled, skipping")
            continue

        SignalClass = STRATEGY_CLASSES[strategy_name]
        log.info(f"  {strategy_name}: computing signal...")
        signal = SignalClass(cfg, universe)
        result = signal.compute(term_structures)

        if result.weights.empty:
            log.warning(f"  {strategy_name}: no weights produced")
            continue

        is_spread = strategy_name in SPREAD_STRATEGIES
        bt = run_strategy_backtest(
            result,
            term_structures,
            cost_model,
            start_date=cfg["backtest"]["start_date"],
            end_date=cfg["backtest"]["end_date"],
            is_spread_trade=is_spread,
        )

        if bt.empty:
            log.warning(f"  {strategy_name}: backtest produced no results")
            continue

        m = compute_metrics(bt["net_return"])
        log.info(
            f"  {strategy_name}: SR={m['sharpe_ratio']:.2f}, "
            f"Ret={m['annualized_return']:.1%}, "
            f"Vol={m['annualized_vol']:.1%}, "
            f"MaxDD={m['max_drawdown']:.1%}"
        )

        strategy_returns[strategy_name] = bt["net_return"]
        metrics_rows.append(_metrics_row(strategy_name, bt, m))

        bt.to_parquet(out_dir / f"{strategy_name}_backtest.parquet")
        result.weights.to_parquet(out_dir / f"{strategy_name}_weights.parquet")

    # --- Phase 4: Build overlay portfolio ---
    overlay_metrics = None
    if not skip_overlay and not only_strategy and len(strategy_returns) >= 2:
        log.info("=== Building overlay portfolio ===")
        overlay_returns = {
            name: r
            for name, r in strategy_returns.items()
            if cfg["strategies"].get(name, {}).get("in_overlay", True)
        }
        excluded = sorted(set(strategy_returns) - set(overlay_returns))
        if excluded:
            log.info(f"  Excluded from overlay (in_overlay=false): {', '.join(excluded)}")
        overlay = build_overlay_portfolio(
            overlay_returns,
            weighting=cfg["overlay"]["weighting"],
            vol_target=cfg["overlay"]["vol_target"],
            vol_lookback=cfg["overlay"]["vol_lookback_days"],
        )
        if not overlay.empty:
            overlay.to_parquet(out_dir / "overlay_portfolio.parquet")
            scaled = overlay["scaled_return"].dropna()
            overlay_metrics = compute_metrics(scaled)
            dr = compute_diversification_ratio(overlay_returns)
            row = _metrics_row("overlay", overlay, overlay_metrics)
            row["diversification_ratio"] = dr
            metrics_rows.append(row)

    # --- Phase 5: Write consolidated stats.csv ---
    if metrics_rows:
        stats = pd.DataFrame(metrics_rows).set_index("strategy")
        stats.to_csv(out_dir / "stats.csv")
        log.info(f"Wrote {out_dir / 'stats.csv'} ({len(stats)} rows)")
        _log_vs_benchmark(stats)

    log.info("=== Done ===")


def _metrics_row(name: str, bt: pd.DataFrame, m: dict) -> dict:
    return {
        "strategy": name,
        "start": bt.index.min().date().isoformat() if not bt.empty else None,
        "end": bt.index.max().date().isoformat() if not bt.empty else None,
        "ann_return": m["annualized_return"],
        "ann_vol": m["annualized_vol"],
        "sharpe": m["sharpe_ratio"],
        "sortino": m["sortino_ratio"],
        "max_dd": m["max_drawdown"],
        "calmar": m["calmar_ratio"],
        "n_obs": int(len(bt)),
    }


def _log_vs_benchmark(stats: pd.DataFrame) -> None:
    """Log each strategy's realised SR vs reference report ±20% tolerance band."""
    for name in stats.index:
        if name not in REF_BENCHMARK:
            continue
        ref_sr, *_ = REF_BENCHMARK[name]
        realised = stats.loc[name, "sharpe"]
        lo, hi = 0.80 * ref_sr, 1.20 * ref_sr
        in_band = lo <= realised <= hi
        flag = "OK " if in_band else "OUT"
        log.info(
            f"  [{flag}] {name}: realised SR={realised:.2f} "
            f"vs reference {ref_sr:.2f} (band {lo:.2f}–{hi:.2f})"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Run the QIS commodities backtest pipeline.",
    )
    parser.add_argument(
        "--config", default="default", help="Config name in configs/ (default: default)"
    )
    parser.add_argument(
        "--strategy",
        default=None,
        choices=sorted(STRATEGY_CLASSES.keys()),
        help="Run a single strategy and skip the overlay.",
    )
    parser.add_argument(
        "--no-overlay",
        action="store_true",
        help="Run all enabled strategies but skip the overlay step.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Backwards compat: `python -m src.main <config>` still works.
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        main(config_name=sys.argv[1])
    else:
        args = _parse_args()
        main(
            config_name=args.config,
            only_strategy=args.strategy,
            skip_overlay=args.no_overlay,
        )
