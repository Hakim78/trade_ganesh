"""Fixtures : bougies synthétiques de séance (RTH), tz-aware, horodatées à l'ouverture."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from common.config import load_config
from strategy import StrategyParams

ET = "America/New_York"


def rth_index(start_date: str, n_days: int, freq: str = "5min") -> pd.DatetimeIndex:
    """Horodatages d'ouverture des bougies de séance 09:30–15:55 ET sur n jours ouvrés."""
    days = pd.bdate_range(start_date, periods=n_days)
    stamps: list[pd.Timestamp] = []
    for day in days:
        session = pd.date_range(f"{day.date()} 09:30", f"{day.date()} 15:55", freq=freq, tz=ET)
        stamps.extend(session)
    return pd.DatetimeIndex(stamps)


def random_walk_bars(index: pd.DatetimeIndex, seed: int = 7, start_price: float = 500.0) -> pd.DataFrame:
    """Marche aléatoire OHLCV déterministe, cohérente (low <= open/close <= high, volume > 0)."""
    rng = np.random.default_rng(seed)
    n = len(index)
    returns = rng.normal(0.0, 0.0008, size=n)
    close = start_price * np.cumprod(1.0 + returns)
    open_ = np.concatenate([[start_price], close[:-1]])
    wick_up = np.abs(rng.normal(0.0, 0.3, size=n))
    wick_down = np.abs(rng.normal(0.0, 0.3, size=n))
    high = np.maximum(open_, close) + wick_up
    low = np.minimum(open_, close) - wick_down
    volume = rng.integers(10_000, 200_000, size=n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index
    )


@pytest.fixture(scope="session")
def config() -> dict:
    return load_config()


@pytest.fixture(scope="session")
def params(config: dict) -> StrategyParams:
    return StrategyParams.from_config(config)


@pytest.fixture(scope="session")
def bars() -> pd.DataFrame:
    """20 jours de séance en 5 minutes (été : 14h UTC = 10h ET)."""
    return random_walk_bars(rth_index("2026-08-03", n_days=20))


@pytest.fixture(scope="session")
def bars_short() -> pd.DataFrame:
    """8 jours : suffisant pour les tests de parité, qui rejouent bougie par bougie (coût quadratique)."""
    return random_walk_bars(rth_index("2026-08-03", n_days=8), seed=11)
