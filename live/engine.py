"""Logique du live, sans I/O : fenêtre de bougies clôturées, signal de la dernière bougie, décision, coupe-circuit.

Parité (invariant 3) : `LiveEngine` appelle exactement la même fonction `generate_signals` que le backtest,
sur les mêmes bougies. `tests/test_parity.py` rejoue une série bougie par bougie et compare aux signaux batch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from strategy import StrategyParams, generate_signals
from strategy.strategy import REQUIRED_COLUMNS

Signal = Literal["long", "short"]
Action = Literal["open_long", "open_short", "reverse_to_long", "reverse_to_short", "ignore", "halted"]


@dataclass(frozen=True)
class Decision:
    time: pd.Timestamp
    signal: Signal
    action: Action
    price: float  # dernière clôture, référence pour le sizing


def decide(signal: Signal | None, position_side: Literal["long", "short"] | None, halted: bool) -> Action | None:
    """Règles de docs/STRATEGY.md : pas de renfort, retournement sur signal inverse, rien si coupe-circuit."""
    if signal is None:
        return None
    if halted:
        return "halted"
    if position_side is None:
        return "open_long" if signal == "long" else "open_short"
    if position_side == signal:
        return "ignore"
    return "reverse_to_long" if signal == "long" else "reverse_to_short"


def breaker_tripped(equity_now: float, day_start_equity: float, threshold_pct: float) -> bool:
    """Vrai si la perte du jour dépasse le seuil (en % de l'equity de début de journée)."""
    if day_start_equity <= 0:
        return False
    return (equity_now / day_start_equity - 1.0) * 100.0 <= -abs(threshold_pct)


class LiveEngine:
    def __init__(self, params: StrategyParams, history: pd.DataFrame | None = None, max_bars: int = 20_000) -> None:
        self.params = params
        self.max_bars = max_bars
        columns = list(REQUIRED_COLUMNS)
        if history is not None and len(history):
            self.bars = history.loc[:, columns].astype(float).copy()
        else:
            self.bars = pd.DataFrame(columns=columns, dtype=float)
        self.last_signals: pd.DataFrame | None = None

    def on_closed_bar(self, bar: pd.Series) -> Signal | None:
        """Ajoute une bougie 5 min clôturée (name = horodatage d'ouverture) et renvoie son signal."""
        stamp = pd.Timestamp(bar.name)
        row = pd.DataFrame([[float(bar[c]) for c in REQUIRED_COLUMNS]], columns=list(REQUIRED_COLUMNS),
                           index=pd.DatetimeIndex([stamp]))
        if len(self.bars) and stamp in self.bars.index:
            self.bars.loc[stamp] = row.iloc[0]
        else:
            self.bars = pd.concat([self.bars, row]) if len(self.bars) else row
        self.bars = self.bars.sort_index().iloc[-self.max_bars:]
        self.last_signals = generate_signals(self.bars, self.params)
        last = self.last_signals.iloc[-1]
        if bool(last["entries"]):
            return "long"
        if bool(last["short_entries"]):
            return "short"
        return None

    @property
    def last_bar(self) -> pd.Series | None:
        return self.bars.iloc[-1] if len(self.bars) else None
