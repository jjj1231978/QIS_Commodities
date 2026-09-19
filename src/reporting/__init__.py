"""Multi-agent reporting: pack → briefing → critique → synthesis.

Mirrors the framework in ~/projects/ML_short_reversion/src/reporting.

Usage:
    pip install -e ".[reporting]"           # or: pip install -r requirements-reporting.txt
    cp .env.example .env && edit .env        # add ANTHROPIC_API_KEY (or OPENAI_API_KEY)
    python -m src.reporting.run_report --dry-run             # estimate cost
    python -m src.reporting.run_report                       # run cheap profile
    python -m src.reporting.run_report --profile quality     # opus + sonnet
    python -m src.reporting.run_report --rounds 2            # extra critique→synth pass

Outputs land under `data/processed/reports/<timestamp>/` with `latest`
symlinked to the most recent run. Each run writes:
    research_pack.json   the JSON pack fed to all three agents
    draft.md             briefing-agent output
    critique.md          critique-agent output
    final.md             synthesis-agent output (the report)
    meta.json            per-call usage + actual $ cost
"""
