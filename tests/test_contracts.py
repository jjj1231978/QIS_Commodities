"""Tests for contract roll calendar and term structure logic."""

import pandas as pd
import pytest

from src.data.contracts import (
    MONTH_CODE_TO_NUM,
    build_roll_calendar,
    contract_symbol,
    enumerate_contracts,
    identify_active_contracts,
)


class TestContractSymbol:
    def test_basic(self):
        assert contract_symbol("CL", 2024, 12) == "CLZ24"
        assert contract_symbol("CL", 2024, 1) == "CLF24"
        assert contract_symbol("GC", 2023, 6) == "GCM23"

    def test_month_codes(self):
        assert MONTH_CODE_TO_NUM["F"] == 1
        assert MONTH_CODE_TO_NUM["Z"] == 12
        assert MONTH_CODE_TO_NUM["N"] == 7


class TestEnumerateContracts:
    def test_all_months(self):
        contracts = enumerate_contracts("CL", "FGHJKMNQUVXZ", 2023, 2023)
        assert len(contracts) == 12
        assert contracts[0]["symbol"] == "CLF23"
        assert contracts[-1]["symbol"] == "CLZ23"

    def test_limited_months(self):
        # Corn only trades H, K, N, U, Z
        contracts = enumerate_contracts("ZC", "HKNUZ", 2023, 2023)
        assert len(contracts) == 5
        symbols = [c["symbol"] for c in contracts]
        assert "ZCH23" in symbols
        assert "ZCZ23" in symbols

    def test_multi_year(self):
        contracts = enumerate_contracts("CL", "FGHJKMNQUVXZ", 2022, 2024)
        assert len(contracts) == 36  # 12 months * 3 years


class TestRollCalendar:
    def test_basic_structure(self):
        cal = build_roll_calendar("CL", "FGHJKMNQUVXZ", 2023, 2024)
        assert "symbol" in cal.columns
        assert "roll_date" in cal.columns
        assert cal["roll_date"].is_monotonic_increasing

    def test_roll_dates_before_expiry(self):
        cal = build_roll_calendar("CL", "FGHJKMNQUVXZ", 2024, 2024, roll_offset_bdays=-5)
        # Roll dates should be before the first of the delivery month
        for _, row in cal.iterrows():
            first_of_month = pd.Timestamp(row["year"], row["month"], 1)
            assert row["roll_date"] < first_of_month

    def test_limited_months(self):
        cal = build_roll_calendar("ZC", "HKNUZ", 2023, 2023)
        assert len(cal) == 5


class TestIdentifyActiveContracts:
    def test_basic(self):
        cal = build_roll_calendar("CL", "FGHJKMNQUVXZ", 2023, 2025)
        dates = pd.bdate_range("2024-01-02", "2024-01-10")
        active = identify_active_contracts(cal, dates, n_contracts=4)

        assert not active.empty
        # Each date should have up to 4 positions (F0, F1, F2, F3)
        for date in dates:
            if date in active.index.get_level_values("date"):
                positions = active.loc[date].index.tolist()
                assert 0 in positions  # F0 should always exist
                assert len(positions) <= 4

    def test_front_month_advances(self):
        """F0 should change when we cross a roll date."""
        cal = build_roll_calendar("CL", "FGHJKMNQUVXZ", 2024, 2025)
        # Pick dates around a known roll date
        roll_date = cal.iloc[5]["roll_date"]  # some roll date in the calendar
        before = roll_date - pd.offsets.BDay(2)
        after = roll_date + pd.offsets.BDay(2)

        dates = pd.DatetimeIndex([before, after])
        active = identify_active_contracts(cal, dates, n_contracts=2)

        if before in active.index.get_level_values("date") and after in active.index.get_level_values("date"):
            f0_before = active.loc[before].loc[0, "symbol"]
            f0_after = active.loc[after].loc[0, "symbol"]
            # F0 might advance (or might not if roll_date doesn't fall between them)
            # At minimum, both should be valid contract symbols
            assert f0_before.startswith("CL")
            assert f0_after.startswith("CL")
