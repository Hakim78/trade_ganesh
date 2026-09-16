"""Stratégie « Liquidity Sweep + VWAP » — fonction pure, sans I/O, sans état, sans réseau.

Traduction de `docs/STRATEGY_SOURCE.pine` (règles détaillées dans `docs/STRATEGY.md`).
Invariant 1 (CLAUDE.md) : à l'index t, seules les bougies ≤ t, clôturées, sont utilisées. Tous les calculs
sont causaux (rolling, shift, cumsum par session, EMA récursive).

Conventions d'entrée :
- `df` indexé par un `DatetimeIndex` **tz-aware**, trié, sans doublon ; horodatage = ouverture de la bougie
  (convention TradingView, yfinance et Alpaca).
- colonnes `open, high, low, close, volume`.
- uniquement des bougies de séance (RTH), comme un graphique TradingView sans extended hours.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")
SIGNAL_COLUMNS: tuple[str, ...] = ("entries", "exits", "short_entries", "short_exits")


@dataclass(frozen=True)
class StrategyParams:
    """Paramètres de la stratégie, lus dans `config.yaml` (jamais en dur ailleurs)."""

    lookback: int = 10
    ema_len: int = 50
    session_tz: str = "UTC"
    session_start_hour: int = 14
    session_end_hour: int = 18
    exchange_tz: str = "America/New_York"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> StrategyParams:
        strategy = config["strategy"]
        session = strategy["session_filter"]
        return cls(
            lookback=int(strategy["lookback"]),
            ema_len=int(strategy["ema_len"]),
            session_tz=str(session["tz"]),
            session_start_hour=int(session["start_hour"]),
            session_end_hour=int(session["end_hour"]),
            exchange_tz=str(config["instrument"]["exchange_tz"]),
        )

    def __post_init__(self) -> None:
        if self.lookback < 1 or self.ema_len < 1:
            raise ValueError("lookback et ema_len doivent être >= 1")
        if not 0 <= self.session_start_hour < self.session_end_hour <= 24:
            raise ValueError("fenêtre horaire invalide : 0 <= start < end <= 24")


def validate_bars(df: pd.DataFrame) -> None:
    """Refuse toute série qui ne respecte pas les conventions (mieux qu'un signal faux silencieux)."""
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"colonnes manquantes : {missing}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("l'index doit être un DatetimeIndex")
    if df.index.tz is None:
        raise ValueError("l'index doit être tz-aware (horodatage d'ouverture de bougie)")
    if not df.index.is_monotonic_increasing:
        raise ValueError("l'index doit être trié par ordre croissant")
    if df.index.has_duplicates:
        raise ValueError("l'index contient des doublons")


def session_vwap(df: pd.DataFrame, exchange_tz: str, source: str = "close") -> pd.Series:
    """VWAP de session : somme(prix × volume) / somme(volume) depuis l'ouverture de la séance.

    Reproduit `ta.vwap(close)` : prix = close, remise à zéro à chaque nouvelle date en heure de la bourse.
    Causal : à t, seules les bougies de la séance courante ≤ t interviennent.
    """
    session_key = np.asarray(df.index.tz_convert(exchange_tz).date)
    price_volume = df[source] * df["volume"]
    cumulative_pv = price_volume.groupby(session_key).cumsum()
    cumulative_volume = df["volume"].groupby(session_key).cumsum()
    return (cumulative_pv / cumulative_volume.replace(0, np.nan)).rename("vwap")


def ema(series: pd.Series, length: int) -> pd.Series:
    """EMA récursive alpha = 2 / (n + 1), initialisée sur la première valeur, comme `ta.ema`."""
    return series.ewm(span=length, adjust=False).mean()


def compute_indicators(df: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
    """Ajoute vwap, ema, prev_high, prev_low et in_session aux bougies. Aucune valeur future utilisée."""
    validate_bars(df)
    out = df.loc[:, list(REQUIRED_COLUMNS)].astype(float).copy()
    out["vwap"] = session_vwap(out, params.exchange_tz)
    out["ema"] = ema(out["close"], params.ema_len)
    # ta.highest(high, n)[1] : plus haut des n bougies PRÉCÉDENTES, bougie courante exclue.
    out["prev_high"] = out["high"].rolling(params.lookback).max().shift(1)
    out["prev_low"] = out["low"].rolling(params.lookback).min().shift(1)
    hours = out.index.tz_convert(params.session_tz).hour
    out["in_session"] = (hours >= params.session_start_hour) & (hours < params.session_end_hour)
    return out


def generate_signals(df: pd.DataFrame, params: StrategyParams) -> pd.DataFrame:
    """Signaux évalués à la clôture de chaque bougie t (exécution à l'ouverture de t+1, hors de ce module).

    Renvoie les bougies + indicateurs + colonnes booléennes :
    - `entries` / `short_entries` : entrée long / short.
    - `exits` / `short_exits` : un signal inverse ferme la position en cours (retournement, pyramiding = 0).
    Les sorties TP/SL ne sont pas des signaux : ce sont des ordres persistants gérés par l'exécuteur.
    """
    ind = compute_indicators(df, params)
    sweep_low = (ind["low"] < ind["prev_low"]) & (ind["close"] > ind["prev_low"])
    sweep_high = (ind["high"] > ind["prev_high"]) & (ind["close"] < ind["prev_high"])
    bull_trend = ind["close"] > ind["ema"]
    bear_trend = ind["close"] < ind["ema"]
    above_vwap = ind["close"] > ind["vwap"]
    below_vwap = ind["close"] < ind["vwap"]

    long_entry = sweep_low & above_vwap & bull_trend & ind["in_session"]
    short_entry = sweep_high & below_vwap & bear_trend & ind["in_session"]

    ind["entries"] = long_entry.astype(bool)
    ind["short_entries"] = short_entry.astype(bool)
    ind["exits"] = ind["short_entries"]
    ind["short_exits"] = ind["entries"]
    return ind
