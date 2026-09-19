"""Smoke test for the main pipeline orchestrator using synthetic data.

Bypasses the data-fetch + term-structure phases by monkey-patching
`src.main` so the test runs offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import yaml

from src.config import CONFIGS_DIR


def _write_minimal_config(tmp_path) -> str:
    """Materialise a tiny config under configs/ so load_config can find it."""
    cfg = {
        "universe": {
            "commodities": {
                "energy": [
                    {"name": "WTI", "root": "CL", "exchange": "GLBX.MDP3",
                     "bcom_weight": 0.08, "months": "FGHJKMNQUVXZ", "seasonal": False},
                ],
                "grains": [
                    {"name": "Corn", "root": "ZC", "exchange": "GLBX.MDP3",
                     "bcom_weight": 0.06, "months": "HKNUZ", "seasonal": True},
                ],
                "base_metals": [
                    {"name": "Copper", "root": "HG", "exchange": "GLBX.MDP3",
                     "bcom_weight": 0.07, "months": "HKNUZ", "seasonal": False},
                ],
                "precious_metals": [
                    {"name": "Gold", "root": "GC", "exchange": "GLBX.MDP3",
                     "bcom_weight": 0.07, "months": "GJMQVZ", "seasonal": False},
                ],
            }
        },
        "data": {
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
            "max_contracts": 13,
            "roll_offset_days": -5,
        },
        "strategies": {
            "carry": {"enabled": True, "front_contract": 0, "deferred_contract": 3,
                       "rebalance_freq": "monthly", "dollar_neutral": True},
            "value": {"enabled": False, "ma_windows_years": [1, 2], "n_long": 1,
                       "n_short": 1, "rebalance_freq": "monthly"},
            "trend": {"enabled": False, "lookback_days": [21, 63], "sector_equal_weight": True,
                       "rebalance_freq": "daily"},
            "congestion": {"enabled": True, "pre_roll_end_day": 4,
                            "roll_start_day": 5, "roll_end_day": 9, "index": "BCOM"},
            "basis_momentum": {"enabled": False, "poly_order": 2,
                                "slope_lookback_days": 63, "n_long": 1, "n_short": 1,
                                "rebalance_freq": "monthly"},
            "backwardation_momentum": {"enabled": False, "n_long": 1, "n_short": 1,
                                         "rebalance_freq": "monthly"},
        },
        "overlay": {"weighting": "equal", "vol_target": 0.05, "vol_lookback_days": 63},
        "costs": {"default_spread_bps": 2.0, "spread_overrides": {},
                   "time_spread_discount": 0.5, "commission_per_contract": 2.50},
        "backtest": {"start_date": "2020-06-01", "end_date": "2023-12-31"},
    }
    name = "test_smoke"
    path = CONFIGS_DIR / f"{name}.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return name


def _make_synthetic_term_structures() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", "2023-12-31")
    out = {}
    for root in ("CL", "ZC", "HG", "GC"):
        base = 100 + np.cumsum(rng.standard_normal(len(dates)) * 0.3)
        df = pd.DataFrame(
            {f"F{i}": base * (1 + 0.002 * i) + rng.standard_normal(len(dates)) * 0.05
             for i in range(13)},
            index=dates,
        )
        out[root] = df.clip(lower=1.0)
    return out


def test_main_pipeline_writes_outputs(tmp_path, monkeypatch):
    """End-to-end pipeline writes per-strategy parquets + stats.csv."""
    cfg_name = _write_minimal_config(tmp_path)
    try:
        # Stub data fetch + term-structure construction so we don't touch the lake.
        synth_raw = {root: pd.DataFrame() for root in ("CL", "ZC", "HG", "GC")}
        synth_ts = _make_synthetic_term_structures()

        from src import main as main_module

        monkeypatch.setattr(main_module, "fetch_all_commodities", lambda *a, **kw: synth_raw)
        monkeypatch.setattr(main_module, "build_term_structure", lambda **kw: synth_ts[kw["root"]])

        out_dir = tmp_path / "processed"
        main_module.main(config_name=cfg_name, output_dir=out_dir)

        # Carry produced PnL + weights + stats.
        assert (out_dir / "carry_backtest.parquet").exists()
        assert (out_dir / "carry_weights.parquet").exists()
        assert (out_dir / "stats.csv").exists()
        stats = pd.read_csv(out_dir / "stats.csv", index_col="strategy")
        assert "carry" in stats.index
        # Stats columns match the spec FR-042 schema.
        for col in ("ann_return", "ann_vol", "sharpe", "sortino", "max_dd",
                     "calmar", "n_obs"):
            assert col in stats.columns
    finally:
        (CONFIGS_DIR / f"{cfg_name}.yaml").unlink(missing_ok=True)
