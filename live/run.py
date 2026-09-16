"""Paper trading Alpaca en streaming.

    python -m live.run            # clés dans .env, endpoint paper vérifié au démarrage

Boucle : flux de bougies 1 min (websocket Alpaca) → bougies 5 min de séance → `generate_signals` à chaque
clôture → décision (`live.engine.decide`) → ordre paper (marché puis OCO TP/SL) → journal.
Coupe-circuit : plus aucune entrée si la perte du jour dépasse `live.daily_drawdown_halt_pct`.

Sorties : `outputs/live/signals.csv`, `outputs/live/state.json` (lu par le frontend), `outputs/live/live.log`.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import math
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import pandas as pd
from dotenv import load_dotenv

from backtest.data import fetch_alpaca
from common.config import ROOT, load_config, tp_sl_fractions
from live.broker import AlpacaPaperBroker, Position, assert_paper_url
from live.engine import LiveEngine, breaker_tripped, decide
from live.feed import BarAggregator, MinuteBar
from strategy import StrategyParams

log = logging.getLogger("live")


class LiveTrader:
    def __init__(self, config: dict[str, Any], broker: AlpacaPaperBroker, history: pd.DataFrame) -> None:
        self.config = config
        self.symbol = str(config["instrument"]["symbol"])
        self.params = StrategyParams.from_config(config)
        self.tp_frac, self.sl_frac = tp_sl_fractions(config)
        self.size_pct = float(config["execution"]["size_pct_equity"])
        self.breaker_pct = float(config["live"]["daily_drawdown_halt_pct"])
        self.broker = broker
        self.engine = LiveEngine(self.params, history)
        instrument = config["instrument"]
        self.aggregator = BarAggregator(int(str(config["timeframe"]).replace("min", "")), instrument["exchange_tz"],
                                        instrument["rth_start"], instrument["rth_end"])
        self.outputs = ROOT / config["live"]["outputs_dir"]
        self.outputs.mkdir(parents=True, exist_ok=True)
        self.status: Literal["starting", "running", "halted", "stopped"] = "starting"
        self.breaker_reason: str | None = None
        self.message: str | None = None
        self.recent_signals: list[dict[str, Any]] = []
        self.last_account = broker.account()

    # --- journal et état ------------------------------------------------------------------------

    def log_signal(self, stamp: pd.Timestamp, side: str, price: float, order_id: str | None, status: str) -> None:
        row = {"t": stamp.isoformat(), "side": side, "price": price, "order_id": order_id, "status": status}
        self.recent_signals = (self.recent_signals + [row])[-50:]
        path = self.outputs / "signals.csv"
        is_new = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            if is_new:
                writer.writeheader()
            writer.writerow(row)

    def write_state(self, position: Position | None) -> None:
        acc = self.last_account
        last = self.engine.last_bar
        daily_pnl = (acc.equity / acc.last_equity - 1.0) * 100.0 if acc.last_equity else None
        state = {
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "status": self.status,
            "symbol": self.symbol,
            "equity": acc.equity,
            "cash": acc.cash,
            "daily_pnl_pct": daily_pnl,
            "position": None if position is None else {"side": position.side, "qty": position.qty,
                                                       "avg_price": position.avg_price},
            "breaker": {"active": self.status == "halted", "reason": self.breaker_reason,
                        "threshold_pct": self.breaker_pct},
            "last_bar": None if last is None else {
                "t": pd.Timestamp(last.name).isoformat(), "o": float(last["open"]), "h": float(last["high"]),
                "l": float(last["low"]), "c": float(last["close"]), "v": float(last["volume"]),
            },
            "recent_signals": self.recent_signals,
            "message": self.message,
        }
        tmp = self.outputs / "state.json.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self.outputs / "state.json")

    # --- exécution ------------------------------------------------------------------------------

    def _size(self, price: float) -> int:
        return int(math.floor(self.last_account.cash * self.size_pct / 100.0 / price))

    def _open(self, side: Literal["long", "short"], stamp: pd.Timestamp, reference_price: float) -> None:
        qty = self._size(reference_price)
        if qty < 1:
            self.log_signal(stamp, side, reference_price, None, "rejected: taille < 1 action")
            return
        order_id = self.broker.submit_market(self.symbol, "buy" if side == "long" else "sell", qty)
        fill = self.broker.wait_fill(order_id)
        base = fill if fill is not None else reference_price
        if side == "long":
            tp, sl = base * (1.0 + self.tp_frac), base * (1.0 - self.sl_frac)
        else:
            tp, sl = base * (1.0 - self.tp_frac), base * (1.0 + self.sl_frac)
        self.broker.submit_oco_exit(self.symbol, side, qty, tp, sl)
        if fill is not None:
            status = f"filled @ {fill:.2f}, OCO TP {tp:.2f} / SL {sl:.2f}"
        else:
            status = f"fill non confirmé, OCO sur {base:.2f}"
        self.log_signal(stamp, side, base, order_id, status)
        log.info("%s %s x%d : %s", stamp, side, qty, status)

    def on_closed_bar(self, bar: pd.Series) -> None:
        stamp = pd.Timestamp(bar.name)
        signal = self.engine.on_closed_bar(bar)
        self.last_account = self.broker.account()
        if self.status != "halted" and breaker_tripped(self.last_account.equity, self.last_account.last_equity,
                                                        self.breaker_pct):
            self.status = "halted"
            day_pnl = (self.last_account.equity / self.last_account.last_equity - 1) * 100
            self.breaker_reason = f"perte du jour {day_pnl:.2f} % <= -{self.breaker_pct} %"
            log.warning("COUPE-CIRCUIT : %s", self.breaker_reason)
        position = self.broker.position(self.symbol)
        action = decide(signal, None if position is None else position.side, self.status == "halted")
        price = float(bar["close"])
        if action is None:
            self.write_state(position)
            return
        log.info("signal %s à %s → %s", signal, stamp, action)
        if action in ("ignore", "halted"):
            self.log_signal(stamp, signal or "flat", price, None, action)
        elif action in ("open_long", "open_short"):
            self._open("long" if action == "open_long" else "short", stamp, price)
        elif action in ("reverse_to_long", "reverse_to_short"):
            self.broker.close_position(self.symbol)
            self.last_account = self.broker.account()
            self._open("long" if action == "reverse_to_long" else "short", stamp, price)
        self.write_state(self.broker.position(self.symbol))

    def on_minute_bar(self, bar: MinuteBar) -> None:
        completed = self.aggregator.push(bar)
        if completed is not None:
            self.on_closed_bar(completed)

    def tick(self, now: pd.Timestamp) -> None:
        completed = self.aggregator.flush_if_elapsed(now)
        if completed is not None:
            self.on_closed_bar(completed)
        # nouvelle journée : le coupe-circuit se réarme (last_equity change à la clôture Alpaca)
        if self.status == "halted":
            acc = self.broker.account()
            if not breaker_tripped(acc.equity, acc.last_equity, self.breaker_pct):
                self.status, self.breaker_reason = "running", None
                log.info("coupe-circuit réarmé")


def bootstrap_history(config: dict[str, Any], symbol: str, days: int = 30) -> pd.DataFrame:
    end = datetime.now(UTC).date()
    return fetch_alpaca(symbol, end - timedelta(days=days), end, config)


async def run_async(trader: LiveTrader, api_key: str, secret_key: str, feed: str, poll_seconds: float) -> None:
    from alpaca.data.enums import DataFeed
    from alpaca.data.live import StockDataStream

    stream = StockDataStream(api_key, secret_key, feed=DataFeed(feed))

    async def on_bar(bar: Any) -> None:
        stamp = pd.Timestamp(bar.timestamp)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        trader.on_minute_bar(MinuteBar(stamp, float(bar.open), float(bar.high), float(bar.low), float(bar.close),
                                       float(bar.volume)))

    async def ticker() -> None:
        while True:
            await asyncio.sleep(poll_seconds)
            try:
                trader.tick(pd.Timestamp.now(tz="UTC"))
                trader.write_state(trader.broker.position(trader.symbol))
            except Exception:  # noqa: BLE001 - un tick raté ne doit pas arrêter le flux
                log.exception("tick")

    stream.subscribe_bars(on_bar, trader.symbol)
    trader.status = "running"
    trader.write_state(trader.broker.position(trader.symbol))
    log.info("flux %s démarré sur %s (%s)", feed, trader.symbol, trader.broker.client._base_url)  # noqa: SLF001
    await asyncio.gather(stream._run_forever(), ticker())  # noqa: SLF001 - API interne mais stable d'alpaca-py


def main() -> int:
    config = load_config()
    load_dotenv(ROOT / ".env")
    api_key, secret_key = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL", str(config["live"]["base_url"]))
    if not config["live"].get("paper_only", True):
        raise RuntimeError("live.paper_only doit rester true")
    assert_paper_url(base_url)
    assert_paper_url(str(config["live"]["base_url"]))
    if not api_key or not secret_key:
        raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY absents de .env (voir .env.example)")

    outputs = ROOT / config["live"]["outputs_dir"]
    outputs.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(outputs / "live.log", encoding="utf-8")])

    symbol = str(config["instrument"]["symbol"])
    broker = AlpacaPaperBroker(api_key, secret_key, base_url)
    history = bootstrap_history(config, symbol)
    log.info("historique chargé : %d bougies jusqu'à %s", len(history), history.index[-1])
    trader = LiveTrader(config, broker, history)
    try:
        asyncio.run(run_async(trader, api_key, secret_key, str(config["live"]["data_feed"]),
                              float(config["live"]["poll_seconds"])))
    except KeyboardInterrupt:
        trader.status = "stopped"
        trader.write_state(broker.position(symbol))
        log.info("arrêt demandé ; les positions ouvertes gardent leur OCO TP/SL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
