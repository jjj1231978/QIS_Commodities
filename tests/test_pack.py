"""Smoke tests for the research-pack assembler.

These do NOT call any LLM API. They verify the pack contains the right keys
and survives missing pipeline outputs.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from src.reporting.pack import (
    KNOWN_GAPS,
    PAPER_REFERENCE,
    STRATEGY_INVENTORY,
    build_research_pack,
    render_pack_markdown,
)


def test_pack_has_required_top_level_keys(tmp_path):
    pack = build_research_pack(processed_dir=tmp_path)
    for key in (
        "schema_version",
        "source_paper_full_text",
        "run_metadata",
        "strategy_inventory",
        "strategies_summary",
        "overlay_summary",
        "stats_csv",
        "correlation_matrix",
        "paper_reference",
        "known_implementation_gaps",
        "pipeline_run_status",
    ):
        assert key in pack, f"Pack missing top-level key: {key}"


def test_pack_marks_no_run_when_processed_empty(tmp_path):
    pack = build_research_pack(processed_dir=tmp_path)
    assert pack["pipeline_run_status"] == "no_run_yet"
    for name in ("carry", "value", "trend", "congestion", "basis_momentum",
                 ):
        assert pack["strategies_summary"][name]["status"] == "not_yet_produced"
    assert pack["overlay_summary"]["status"] == "not_yet_produced"
    assert pack["stats_csv"]["status"] == "not_yet_produced"
    assert pack["correlation_matrix"]["status"] == "not_yet_produced"


def test_pack_summarises_when_outputs_present(tmp_path):
    """Place a synthetic carry_backtest parquet and confirm the pack picks it up."""
    idx = pd.bdate_range("2020-01-01", periods=300)
    df = pd.DataFrame(
        {
            "gross_return": [0.0005] * len(idx),
            "cost": [0.0] * len(idx),
            "net_return": [0.0005] * len(idx),
            "turnover": [0.01] * len(idx),
        },
        index=idx,
    )
    df.to_parquet(tmp_path / "carry_backtest.parquet")
    pack = build_research_pack(processed_dir=tmp_path)
    assert pack["pipeline_run_status"] == "completed"
    assert pack["strategies_summary"]["carry"]["status"] == "available"
    assert pack["strategies_summary"]["carry"]["n_obs"] == 300
    assert pack["strategies_summary"]["carry"]["sharpe"] is not None


def test_pack_paper_reference_complete():
    """All reference benchmarks the prompts cite must be present when available.

    The figures are third-party research held in a gitignored local file, so a
    fresh clone (and the published build) legitimately has none — assert the
    documented placeholder shape there instead.
    """
    if not PAPER_REFERENCE.get("available"):
        assert PAPER_REFERENCE["available"] is False
        assert "source" in PAPER_REFERENCE
        pytest.skip("reference figures not present locally (data/reference/benchmark.json)")

    per = PAPER_REFERENCE["per_strategy"]
    for s in ("carry", "value", "trend", "congestion", "basis_momentum",
              ):
        assert s in per, f"PAPER_REFERENCE missing strategy {s}"
        for col in ("sharpe", "ann_return", "ann_vol", "max_dd"):
            assert col in per[s], f"PAPER_REFERENCE.{s} missing {col}"
    assert "equal_weight_overlay" in PAPER_REFERENCE
    assert "validation_checklist" in PAPER_REFERENCE
    # The figures themselves are third-party and not reproduced here; check the
    # loaded values are usable numbers rather than asserting a licensed datum.
    assert isinstance(per["carry"]["sharpe"], (int, float))
    assert 0 < per["carry"]["sharpe"] < 10


def test_strategy_inventory_matches_implementations():
    """STRATEGY_INVENTORY names must equal the names main.py actually runs."""
    from src.main import STRATEGY_CLASSES
    inventory_names = {s["name"] for s in STRATEGY_INVENTORY}
    impl_names = set(STRATEGY_CLASSES.keys())
    assert inventory_names == impl_names


def test_known_gaps_nontrivial():
    assert len(KNOWN_GAPS) >= 5
    assert any("ICE" in g or "GLBX" in g for g in KNOWN_GAPS), (
        "Known gaps should mention the GLBX-only universe restriction"
    )
    assert any("intraday" in g.lower() for g in KNOWN_GAPS), (
        "Known gaps should mention intraday trend being out of scope"
    )


def test_render_pack_markdown_is_valid_json_block(tmp_path):
    pack = build_research_pack(processed_dir=tmp_path)
    rendered = render_pack_markdown(pack)
    assert rendered.startswith("```json\n")
    assert rendered.endswith("\n```")
    # Strip fences and confirm the body parses.
    body = rendered[len("```json\n"):-len("\n```")]
    parsed = json.loads(body)
    assert parsed["schema_version"] == pack["schema_version"]
