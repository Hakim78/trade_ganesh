"""Reconstruction des bougies 5 minutes de séance à partir des bougies 1 minute du flux Alpaca.

Une bougie 5 min est **clôturée** quand arrive une bougie 1 min d'un seau suivant, ou quand l'horloge dépasse
la fin du seau (`flush_if_elapsed`). Les bougies hors séance (RTH) sont ignorées, comme dans le backtest
(`backtest.data.restrict_to_rth`), pour que les deux chemins voient exactement les mêmes bougies.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MinuteBar:
    timestamp: pd.Timestamp  # ouverture de la minute, tz-aware
    open: float
    high: float
    low: float
    close: float
    volume: float


def bucket_start(timestamp: pd.Timestamp, minutes: int) -> pd.Timestamp:
    """Début du seau de `minutes` minutes contenant `timestamp` (heure murale du fuseau de l'horodatage)."""
    if timestamp.tzinfo is None:
        raise ValueError("horodatage tz-aware requis")
    return timestamp.floor(f"{minutes}min")


class BarAggregator:
    def __init__(self, minutes: int, exchange_tz: str, rth_start: str, rth_end: str) -> None:
        self.minutes = minutes
        self.exchange_tz = exchange_tz
        start, end = pd.Timestamp(rth_start).time(), pd.Timestamp(rth_end).time()
        self._rth_lo = start.hour * 60 + start.minute
        self._rth_hi = end.hour * 60 + end.minute
        self._bucket: pd.Timestamp | None = None
        self._o = self._h = self._l = self._c = 0.0
        self._v = 0.0

    def in_rth(self, timestamp: pd.Timestamp) -> bool:
        local = timestamp.tz_convert(self.exchange_tz)
        minute = local.hour * 60 + local.minute
        return self._rth_lo <= minute < self._rth_hi

    def _emit(self) -> pd.Series | None:
        if self._bucket is None:
            return None
        bar = pd.Series(
            {"open": self._o, "high": self._h, "low": self._l, "close": self._c, "volume": self._v},
            name=self._bucket,
        )
        self._bucket = None
        return bar

    def push(self, bar: MinuteBar) -> pd.Series | None:
        """Absorbe une bougie 1 min ; renvoie la bougie 5 min clôturée s'il y en a une, sinon None."""
        stamp = bar.timestamp.tz_convert(self.exchange_tz)
        bucket = bucket_start(stamp, self.minutes)
        completed: pd.Series | None = None
        if self._bucket is not None and bucket != self._bucket:
            if bucket < self._bucket:
                return None  # bougie en retard d'un seau déjà clôturé : ignorée
            completed = self._emit()
        if not self.in_rth(stamp):
            return completed
        if self._bucket is None:
            self._bucket = bucket
            self._o, self._h, self._l, self._c, self._v = bar.open, bar.high, bar.low, bar.close, bar.volume
        else:
            self._h = max(self._h, bar.high)
            self._l = min(self._l, bar.low)
            self._c = bar.close
            self._v += bar.volume
        return completed

    def flush_if_elapsed(self, now: pd.Timestamp) -> pd.Series | None:
        """Clôture le seau courant si l'horloge a dépassé sa fin (dernière bougie de la séance, minute vide)."""
        if self._bucket is None:
            return None
        end = self._bucket + pd.Timedelta(minutes=self.minutes)
        if now.tz_convert(self.exchange_tz) >= end:
            return self._emit()
        return None

    @property
    def pending_bucket(self) -> pd.Timestamp | None:
        return self._bucket
