"""BCOM commodity universe — constituents, sectors, weights."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import load_config


@dataclass(frozen=True)
class Commodity:
    """A single commodity future contract specification."""

    name: str
    root: str
    exchange: str
    bcom_weight: float
    sector: str
    months: str  # contract month codes, e.g. "FGHJKMNQUVXZ"
    seasonal: bool = False


class Universe:
    """Collection of BCOM commodity constituents."""

    def __init__(self, commodities: list[Commodity]):
        self.commodities = commodities
        self._by_root = {c.root: c for c in commodities}

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> Universe:
        """Build Universe from config YAML."""
        if cfg is None:
            cfg = load_config()

        commodities = []
        for sector, items in cfg["universe"]["commodities"].items():
            for item in items:
                commodities.append(
                    Commodity(
                        name=item["name"],
                        root=item["root"],
                        exchange=item["exchange"],
                        bcom_weight=item["bcom_weight"],
                        sector=sector,
                        months=item["months"],
                        seasonal=item.get("seasonal", False),
                    )
                )
        return cls(commodities)

    def get(self, root: str) -> Commodity:
        """Get commodity by root symbol."""
        return self._by_root[root]

    @property
    def roots(self) -> list[str]:
        """All root symbols."""
        return [c.root for c in self.commodities]

    def by_sector(self) -> dict[str, list[Commodity]]:
        """Group commodities by sector."""
        sectors: dict[str, list[Commodity]] = {}
        for c in self.commodities:
            sectors.setdefault(c.sector, []).append(c)
        return sectors

    def weights(self) -> pd.Series:
        """BCOM weights as Series indexed by root symbol."""
        return pd.Series(
            {c.root: c.bcom_weight for c in self.commodities}, name="bcom_weight"
        )

    def seasonal_roots(self) -> list[str]:
        """Root symbols of seasonal commodities."""
        return [c.root for c in self.commodities if c.seasonal]
