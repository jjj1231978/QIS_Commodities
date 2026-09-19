"""Transaction cost model for commodity futures."""

from __future__ import annotations

import pandas as pd


class CostModel:
    """Commodity-specific transaction cost model.

    Costs include:
    - Bid-ask spread (varies by commodity liquidity)
    - Commission per contract (converted to bps via notional)
    - Time-spread discount (spread trades are cheaper than outrights)
    """

    def __init__(self, config: dict):
        self.default_spread_bps = config["costs"]["default_spread_bps"]
        self.spread_overrides = config["costs"].get("spread_overrides", {})
        self.time_spread_discount = config["costs"]["time_spread_discount"]
        self.commission_per_contract = config["costs"]["commission_per_contract"]

    def spread_cost_bps(self, root: str, is_spread_trade: bool = False) -> float:
        """Get the half-spread cost in bps for a commodity.

        Args:
            root: Commodity root symbol.
            is_spread_trade: If True, apply time-spread discount.

        Returns:
            One-way cost in bps.
        """
        cost = self.spread_overrides.get(root, self.default_spread_bps)
        if is_spread_trade:
            cost *= self.time_spread_discount
        return cost

    def compute_turnover_cost(
        self,
        weights: pd.DataFrame,
        is_spread_trade: bool = False,
    ) -> pd.Series:
        """Compute daily transaction costs from weight changes.

        Args:
            weights: Daily position weights (dates × commodities).
            is_spread_trade: Whether this strategy trades spreads.

        Returns:
            Series of daily costs (positive = cost, reduces returns).
        """
        # Turnover = sum of absolute weight changes
        weight_changes = weights.diff().abs()

        # Apply per-commodity spread costs
        costs_per_commodity = pd.DataFrame(
            0.0, index=weight_changes.index, columns=weight_changes.columns
        )
        for root in weight_changes.columns:
            cost_bps = self.spread_cost_bps(root, is_spread_trade)
            costs_per_commodity[root] = weight_changes[root] * cost_bps / 10000

        # Total daily cost across all commodities
        total_cost = costs_per_commodity.sum(axis=1)
        total_cost.iloc[0] = 0.0  # no cost on first day

        return total_cost
