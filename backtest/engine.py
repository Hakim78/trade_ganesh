"""Exécuteur du backtest : transforme les signaux de `strategy.generate_signals` en trades.

Sémantique (docs/STRATEGY.md, section Sortie) :
- signal à la clôture de t → ordre au marché exécuté à l'**ouverture de t+1** (slippage contre nous) ;
- TP / SL en OCO persistant, actifs **dès la bougie d'entrée**, évalués sur high / low de chaque bougie ;
  si l'ouverture saute au-delà du niveau, exécution à l'ouverture (gap) ;
- TP et SL touchés dans la même bougie → SL d'abord (pessimiste) ;
- signal inverse pendant une position → clôture à l'ouverture de t+1 puis ouverture de l'inverse ;
  signal de même sens → ignoré (pyramiding = 0) ;
- taille = `size_pct_equity` % de l'equity (cash quand on est flat), actions entières.

Pourquoi un exécuteur maison plutôt que `vbt.Portfolio.from_signals` : VectorBT n'évalue les stops qu'à
partir de la bougie suivant l'entrée (vérifié sur la version installée), ce qui, avec un SL de 0,06 % sur des
bougies de 5 minutes, dénature la stratégie. VectorBT reste utilisé pour l'analyse des rendements.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from common.config import tp_sl_fractions

Side = Literal["long", "short"]
ExitReason = Literal["tp", "sl", "reverse", "end"]


@dataclass(frozen=True)
class ExecutionParams:
    tp_frac: float
    sl_frac: float
    fees_frac: float
    slippage_frac: float
    init_cash: float
    size_pct_equity: float
    size_granularity: int = 1
    same_bar_conflict: str = "sl_first"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> ExecutionParams:
        tp_frac, sl_frac = tp_sl_fractions(config)
        execution = config["execution"]
        return cls(
            tp_frac=tp_frac,
            sl_frac=sl_frac,
            fees_frac=float(execution["fees_pct"]),
            slippage_frac=float(execution["slippage_pct"]),
            init_cash=float(execution["init_cash"]),
            size_pct_equity=float(execution["size_pct_equity"]),
            size_granularity=int(execution["size_granularity"]),
            same_bar_conflict=str(config["exits"]["same_bar_conflict"]),
        )

    def __post_init__(self) -> None:
        if self.tp_frac <= 0 or self.sl_frac <= 0:
            raise ValueError("tp et sl doivent être strictement positifs")
        if self.fees_frac < 0 or self.slippage_frac < 0:
            raise ValueError("frais et slippage ne peuvent pas être négatifs")
        if self.same_bar_conflict not in ("sl_first", "tp_first"):
            raise ValueError("same_bar_conflict doit valoir sl_first ou tp_first")
        if self.size_granularity < 1:
            raise ValueError("size_granularity doit être >= 1")


@dataclass
class Trade:
    id: int
    side: Side
    entry_time: pd.Timestamp
    entry_index: int
    entry_price: float
    size: int
    tp_price: float
    sl_price: float
    exit_time: pd.Timestamp | None = None
    exit_index: int | None = None
    exit_price: float | None = None
    exit_reason: ExitReason | None = None
    fees: float = 0.0
    pnl: float = 0.0

    @property
    def direction(self) -> int:
        return 1 if self.side == "long" else -1

    @property
    def is_open(self) -> bool:
        return self.exit_index is None

    @property
    def return_pct(self) -> float:
        notional = self.entry_price * self.size
        return 100.0 * self.pnl / notional if notional else 0.0

    @property
    def bars_held(self) -> int | None:
        return None if self.exit_index is None else self.exit_index - self.entry_index


@dataclass
class BacktestResult:
    bars: pd.DataFrame
    signals: pd.DataFrame
    trades: list[Trade]
    equity: pd.Series  # valeur du portefeuille à la clôture de chaque bougie
    fees_total: float
    params: ExecutionParams

    def trades_frame(self) -> pd.DataFrame:
        rows = [
            {
                "id": t.id,
                "side": t.side,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "size": t.size,
                "tp_price": t.tp_price,
                "sl_price": t.sl_price,
                "exit_reason": t.exit_reason,
                "bars_held": t.bars_held,
                "fees": t.fees,
                "pnl": t.pnl,
                "return_pct": t.return_pct,
                "status": "open" if t.is_open else "closed",
            }
            for t in self.trades
        ]
        columns = [
            "id", "side", "entry_time", "exit_time", "entry_price", "exit_price", "size", "tp_price", "sl_price",
            "exit_reason", "bars_held", "fees", "pnl", "return_pct", "status",
        ]
        return pd.DataFrame(rows, columns=columns)


class _Book:
    """État du portefeuille pendant la simulation (cash, position, journal)."""

    def __init__(self, params: ExecutionParams) -> None:
        self.p = params
        self.cash = params.init_cash
        self.position: Trade | None = None
        self.trades: list[Trade] = []
        self.fees_total = 0.0

    # --- prix d'exécution --------------------------------------------------------------------------

    def _buy_price(self, price: float) -> float:
        return price * (1.0 + self.p.slippage_frac)

    def _sell_price(self, price: float) -> float:
        return price * (1.0 - self.p.slippage_frac)

    def _fee(self, price: float, size: int) -> float:
        return price * size * self.p.fees_frac

    # --- ouverture / fermeture ---------------------------------------------------------------------

    def open(self, side: Side, raw_price: float, index: int, time: pd.Timestamp) -> Trade | None:
        fill = self._buy_price(raw_price) if side == "long" else self._sell_price(raw_price)
        budget = self.cash * self.p.size_pct_equity / 100.0
        granularity = self.p.size_granularity
        size = int(math.floor(budget / fill / granularity)) * granularity
        if size < 1:
            return None
        fee = self._fee(fill, size)
        if side == "long":
            self.cash -= fill * size + fee
            tp_price, sl_price = fill * (1.0 + self.p.tp_frac), fill * (1.0 - self.p.sl_frac)
        else:
            self.cash += fill * size - fee
            tp_price, sl_price = fill * (1.0 - self.p.tp_frac), fill * (1.0 + self.p.sl_frac)
        trade = Trade(
            id=len(self.trades) + 1, side=side, entry_time=time, entry_index=index, entry_price=fill, size=size,
            tp_price=tp_price, sl_price=sl_price, fees=fee,
        )
        self.fees_total += fee
        self.trades.append(trade)
        self.position = trade
        return trade

    def close(self, raw_price: float, index: int, time: pd.Timestamp, reason: ExitReason) -> None:
        trade = self.position
        assert trade is not None
        fill = self._sell_price(raw_price) if trade.side == "long" else self._buy_price(raw_price)
        fee = self._fee(fill, trade.size)
        if trade.side == "long":
            self.cash += fill * trade.size - fee
        else:
            self.cash -= fill * trade.size + fee
        trade.exit_time, trade.exit_index, trade.exit_price, trade.exit_reason = time, index, fill, reason
        trade.fees += fee
        trade.pnl = (fill - trade.entry_price) * trade.size * trade.direction - trade.fees
        self.fees_total += fee
        self.position = None

    # --- stops ----------------------------------------------------------------------------------

    def stop_hit(self, o: float, h: float, low: float) -> tuple[float, ExitReason] | None:
        """Prix brut de sortie et raison si un stop est touché sur la bougie, sinon None."""
        t = self.position
        assert t is not None
        if t.side == "long":
            if o <= t.sl_price:
                return o, "sl"
            if o >= t.tp_price:
                return o, "tp"
            hit_sl, hit_tp = low <= t.sl_price, h >= t.tp_price
        else:
            if o >= t.sl_price:
                return o, "sl"
            if o <= t.tp_price:
                return o, "tp"
            hit_sl, hit_tp = h >= t.sl_price, low <= t.tp_price
        if hit_sl and hit_tp:
            return (t.sl_price, "sl") if self.p.same_bar_conflict == "sl_first" else (t.tp_price, "tp")
        if hit_sl:
            return t.sl_price, "sl"
        if hit_tp:
            return t.tp_price, "tp"
        return None

    def equity(self, close: float) -> float:
        if self.position is None:
            return self.cash
        return self.cash + self.position.direction * self.position.size * close


def run_backtest(bars: pd.DataFrame, signals: pd.DataFrame, params: ExecutionParams,
                 close_at_end: bool = True) -> BacktestResult:
    """Simule bougie par bougie. `signals` doit être aligné sur `bars` (sortie de `generate_signals`)."""
    if not bars.index.equals(signals.index):
        raise ValueError("bars et signals doivent partager le même index")
    o = bars["open"].to_numpy(dtype=float)
    h = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)
    long_sig = signals["entries"].to_numpy(dtype=bool)
    short_sig = signals["short_entries"].to_numpy(dtype=bool)
    index = bars.index
    n = len(bars)

    book = _Book(params)
    equity = np.empty(n, dtype=float)

    for i in range(n):
        # 1. Signal émis à la clôture de i-1 → exécution à l'ouverture de i.
        if i > 0:
            wanted: Side | None = "long" if long_sig[i - 1] else ("short" if short_sig[i - 1] else None)
            if wanted is not None:
                if book.position is not None and book.position.side != wanted:
                    book.close(o[i], i, index[i], "reverse")
                if book.position is None:
                    book.open(wanted, o[i], i, index[i])
        # 2. TP / SL sur la bougie i, y compris la bougie d'entrée.
        if book.position is not None:
            hit = book.stop_hit(o[i], h[i], low[i])
            if hit is not None:
                book.close(hit[0], i, index[i], hit[1])
        # 3. Valorisation à la clôture.
        equity[i] = book.equity(c[i])

    if close_at_end and book.position is not None and n > 0:
        book.close(c[-1], n - 1, index[-1], "end")
        equity[-1] = book.equity(c[-1])

    return BacktestResult(
        bars=bars, signals=signals, trades=book.trades,
        equity=pd.Series(equity, index=index, name="equity"), fees_total=book.fees_total, params=params,
    )
