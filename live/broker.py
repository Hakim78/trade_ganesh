"""Accès au compte Alpaca **paper**. Refuse tout autre endpoint (invariant 6 de CLAUDE.md).

Ordres : entrée au marché, puis, une fois le prix d'exécution connu, un OCO (take-profit limite + stop) calculé
sur ce prix, comme `strategy.exit` du script de l'ami et comme `backtest/engine.py`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

PAPER_HOST = "paper-api.alpaca.markets"


def assert_paper_url(base_url: str) -> str:
    if PAPER_HOST not in base_url:
        raise RuntimeError(f"endpoint refusé : {base_url!r}. Paper uniquement ({PAPER_HOST}).")
    return base_url


@dataclass(frozen=True)
class Account:
    equity: float
    cash: float
    last_equity: float  # equity à la clôture de la veille, base du coupe-circuit journalier


@dataclass(frozen=True)
class Position:
    side: Literal["long", "short"]
    qty: int
    avg_price: float


class AlpacaPaperBroker:
    def __init__(self, api_key: str, secret_key: str, base_url: str) -> None:
        from alpaca.trading.client import TradingClient

        assert_paper_url(base_url)
        self.client = TradingClient(api_key, secret_key, paper=True, url_override=base_url)

    # --- lecture -----------------------------------------------------------------------------

    def account(self) -> Account:
        acc = self.client.get_account()
        return Account(equity=float(acc.equity), cash=float(acc.cash), last_equity=float(acc.last_equity))

    def position(self, symbol: str) -> Position | None:
        from alpaca.common.exceptions import APIError

        try:
            pos = self.client.get_open_position(symbol)
        except APIError as exc:
            if getattr(exc, "status_code", None) == 404 or "position does not exist" in str(exc).lower():
                return None
            raise
        qty = abs(int(float(pos.qty)))
        side: Literal["long", "short"] = "short" if str(pos.side).lower().endswith("short") else "long"
        return Position(side=side, qty=qty, avg_price=float(pos.avg_entry_price))

    # --- ordres ------------------------------------------------------------------------------

    def submit_market(self, symbol: str, side: Literal["buy", "sell"], qty: int) -> str:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        order = self.client.submit_order(MarketOrderRequest(
            symbol=symbol, qty=qty, side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        ))
        return str(order.id)

    def wait_fill(self, order_id: str, timeout_s: float = 15.0) -> float | None:
        """Prix moyen d'exécution, ou None si l'ordre n'est pas exécuté dans le délai."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            order = self.client.get_order_by_id(order_id)
            if str(order.status).lower().endswith("filled") and order.filled_avg_price is not None:
                return float(order.filled_avg_price)
            time.sleep(0.5)
        return None

    def submit_oco_exit(self, symbol: str, position_side: Literal["long", "short"], qty: int,
                        tp_price: float, sl_price: float) -> str:
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, StopLossRequest, TakeProfitRequest

        side = OrderSide.SELL if position_side == "long" else OrderSide.BUY
        order = self.client.submit_order(LimitOrderRequest(
            symbol=symbol, qty=qty, side=side, time_in_force=TimeInForce.GTC, order_class=OrderClass.OCO,
            limit_price=round(tp_price, 2),
            take_profit=TakeProfitRequest(limit_price=round(tp_price, 2)),
            stop_loss=StopLossRequest(stop_price=round(sl_price, 2)),
        ))
        return str(order.id)

    def cancel_all(self, symbol: str) -> None:
        for order in self.client.get_orders():
            if str(order.symbol) == symbol:
                self.client.cancel_order_by_id(str(order.id))

    def close_position(self, symbol: str) -> None:
        self.cancel_all(symbol)
        self.client.close_position(symbol)
