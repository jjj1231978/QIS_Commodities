"""CLI entry point for data fetching: python -m src.data"""

import logging
import sys

from src.config import load_config
from src.data.fetch import fetch_all_commodities
from src.data.universe import Universe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main():
    config_name = sys.argv[1] if len(sys.argv) > 1 else "default"
    cfg = load_config(config_name)
    universe = Universe.from_config(cfg)

    print(f"Fetching futures data for {len(universe.commodities)} commodities...")
    raw_data = fetch_all_commodities(
        universe,
        start=cfg["data"]["start_date"],
        end=cfg["data"]["end_date"],
    )
    print(f"Done. Fetched data for {len(raw_data)} commodities.")


if __name__ == "__main__":
    main()
