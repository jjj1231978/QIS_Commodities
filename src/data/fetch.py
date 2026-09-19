"""Read futures OHLCV data from the local Databento data lake.

The data lake at ~/data_lake/databento is populated by
~/data_lake/databento/scripts/download_databento.py and stores all 18 BCOM
commodity roots in a single combined parquet. This module exposes the same
interface as the previous Databento-direct fetcher; all reads go through the
lake.
"""

import logging
import re
from pathlib import Path
from threading import Lock

import pandas as pd

log = logging.getLogger(__name__)

LAKE_PARQUET = (
    Path.home()
    / "data_lake/databento/futures/L0/ohlcv-1d"
    / "ohlcv-1d_GLBX.MDP3_bcom_2010-06-06_2026-05-05.parquet"
)
ALLOWED_DATASETS = {"GLBX.MDP3"}
MONTH_CODES = "FGHJKMNQUVXZ"

_lake_cache: pd.DataFrame | None = None
_lake_lock = Lock()


def _load_lake() -> pd.DataFrame:
    """Lazily load and cache the lake parquet (one in-process load)."""
    global _lake_cache
    with _lake_lock:
        if _lake_cache is None:
            if not LAKE_PARQUET.exists():
                raise FileNotFoundError(
                    f"Data lake parquet not found at {LAKE_PARQUET}. "
                    f"Populate it via "
                    f"`python ~/data_lake/databento/scripts/download_databento.py`."
                )
            df = pd.read_parquet(LAKE_PARQUET).reset_index()
            ts_col = "ts_event" if "ts_event" in df.columns else df.columns[0]
            if ts_col != "ts_event":
                df = df.rename(columns={ts_col: "ts_event"})
            df["ts_event"] = pd.to_datetime(df["ts_event"]).dt.normalize()
            _lake_cache = df
            log.info(f"Loaded {len(df):,} rows from lake: {LAKE_PARQUET.name}")
    return _lake_cache


def fetch_futures_data(
    root: str,
    exchange_dataset: str,
    start: str,
    end: str,
    schema: str = "ohlcv-1d",
    cache_dir: Path | None = None,
    api_key: str | None = None,
    preview_cost: bool = True,
) -> pd.DataFrame:
    """Return OHLCV data for ``root`` from the data lake, filtered by date.

    Same signature as the previous Databento-direct fetcher; ``cache_dir``,
    ``api_key`` and ``preview_cost`` are accepted for backward compatibility
    but unused — the lake is the only source.

    Args:
        root: Futures root symbol (e.g. "CL").
        exchange_dataset: Must be "GLBX.MDP3" (the only dataset in the lake).
        start: Start date inclusive (ISO 8601).
        end: End date exclusive (ISO 8601, matches Databento convention).
        schema: Must be "ohlcv-1d".

    Returns:
        Long-format DataFrame with columns
        ``[ts_event, symbol, open, high, low, close, volume]``. ``symbol`` is
        the specific contract (e.g. "CLZ4") or the continuous parent ("CL").
    """
    if exchange_dataset not in ALLOWED_DATASETS:
        raise ValueError(
            f"Dataset {exchange_dataset!r} not in lake. "
            f"Lake covers {sorted(ALLOWED_DATASETS)}."
        )
    if schema != "ohlcv-1d":
        raise ValueError(
            f"Lake only stores ohlcv-1d for futures; got schema={schema!r}."
        )

    df = _load_lake()

    # Match the continuous parent (e.g. "CL") OR any outright following the
    # {root}{month-code}{0-2 digit year} pattern (e.g. "CLZ", "CLZ4", "CLZ24").
    # Anchored regex prevents cross-root matches (e.g. ZC vs ZNC).
    pattern = re.compile(rf"^{re.escape(root)}([{MONTH_CODES}]\d{{0,2}})?$")
    mask = df["symbol"].str.match(pattern, na=False)

    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    mask &= (df["ts_event"] >= start_ts) & (df["ts_event"] < end_ts)

    cols = ["ts_event", "symbol", "open", "high", "low", "close", "volume"]
    available = [c for c in cols if c in df.columns]
    out = df.loc[mask, available].copy().reset_index(drop=True)
    log.info(f"Lake: {root} → {len(out):,} rows ({start}→{end})")
    return out


def fetch_all_commodities(
    universe,
    start: str,
    end: str,
    cache_dir: Path | None = None,
    preview_cost: bool = True,
) -> dict[str, pd.DataFrame]:
    """Fetch (from lake) for every commodity in the universe.

    Returns:
        Dict mapping root symbol to long-format DataFrame. Roots with zero
        rows in the lake are skipped (logged as a warning).
    """
    results: dict[str, pd.DataFrame] = {}
    for commodity in universe.commodities:
        try:
            df = fetch_futures_data(
                root=commodity.root,
                exchange_dataset=commodity.exchange,
                start=start,
                end=end,
            )
        except Exception as e:
            log.error(f"  {commodity.root}: FAILED - {e}")
            continue
        if len(df) == 0:
            log.warning(f"  {commodity.root}: 0 rows in lake — skipping")
            continue
        results[commodity.root] = df
        log.info(f"  {commodity.root}: {len(df)} rows")
    return results
