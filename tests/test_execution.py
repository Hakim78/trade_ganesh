"""Sémantique d'exécution (docs/STRATEGY.md, section Sortie), sur des bougies construites à la main.

Paramètres de test : TP 2 %, SL 1 %, frais 0, slippage 0 sauf mention, capital 10 000, 10 % par trade.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.engine import ExecutionParams, run_backtest

ET = "America/New_York"


def make_bars(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    index = pd.date_range("2026-08-04 09:30", periods=len(rows), freq="5min", tz=ET)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)
    df["volume"] = 1_000.0
    return df


def make_signals(bars: pd.DataFrame, longs: list[int] = (), shorts: list[int] = ()) -> pd.DataFrame:
    sig = pd.DataFrame(index=bars.index)
    sig["entries"] = False
    sig["short_entries"] = False
    sig.loc[bars.index[list(longs)], "entries"] = True
    sig.loc[bars.index[list(shorts)], "short_entries"] = True
    sig["exits"] = sig["short_entries"]
    sig["short_exits"] = sig["entries"]
    return sig


def params(**overrides: float | int | str) -> ExecutionParams:
    base = dict(tp_frac=0.02, sl_frac=0.01, fees_frac=0.0, slippage_frac=0.0, init_cash=10_000.0,
                size_pct_equity=10.0, size_granularity=1, same_bar_conflict="sl_first")
    base.update(overrides)
    return ExecutionParams(**base)  # type: ignore[arg-type]


def test_entry_fills_at_next_open_with_slippage() -> None:
    bars = make_bars([(100, 100, 100, 100), (101, 101, 101, 101), (101, 101, 101, 101)])
    result = run_backtest(bars, make_signals(bars, longs=[0]), params(slippage_frac=0.001), close_at_end=False)
    trade = result.trades[0]
    assert trade.entry_index == 1 and trade.entry_time == bars.index[1]
    assert trade.entry_price == pytest.approx(101 * 1.001)
    assert trade.size == 9  # floor(1000 / 101.101)


def test_tp_can_trigger_on_entry_bar() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 103, 100, 101), (101, 101, 101, 101)])
    result = run_backtest(bars, make_signals(bars, longs=[0]), params(), close_at_end=False)
    trade = result.trades[0]
    assert trade.exit_index == 1 and trade.exit_reason == "tp"
    assert trade.exit_price == pytest.approx(102.0)
    assert trade.pnl == pytest.approx(10 * 2.0)


def test_sl_first_when_both_hit_in_same_bar() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 105, 95, 100)])
    result = run_backtest(bars, make_signals(bars, longs=[0]), params(), close_at_end=False)
    trade = result.trades[0]
    assert trade.exit_reason == "sl" and trade.exit_price == pytest.approx(99.0)


def test_tp_first_option_is_respected() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 105, 95, 100)])
    result = run_backtest(bars, make_signals(bars, longs=[0]), params(same_bar_conflict="tp_first"),
                          close_at_end=False)
    assert result.trades[0].exit_reason == "tp"


def test_gap_through_sl_fills_at_open() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 100, 100, 100), (97, 97, 96, 96)])
    result = run_backtest(bars, make_signals(bars, longs=[0]), params(), close_at_end=False)
    trade = result.trades[0]
    assert trade.exit_index == 2 and trade.exit_reason == "sl"
    assert trade.exit_price == pytest.approx(97.0)  # pire que le niveau 99


def test_opposite_signal_reverses_position() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 100, 100, 100), (100, 100, 100, 100), (100, 100, 100, 100)])
    result = run_backtest(bars, make_signals(bars, longs=[0], shorts=[1]), params(), close_at_end=False)
    assert [t.side for t in result.trades] == ["long", "short"]
    first, second = result.trades
    assert first.exit_index == 2 and first.exit_reason == "reverse"
    assert second.entry_index == 2 and second.is_open


def test_same_side_signal_is_ignored_no_pyramiding() -> None:
    bars = make_bars([(100, 100, 100, 100)] * 4)
    result = run_backtest(bars, make_signals(bars, longs=[0, 1]), params(), close_at_end=False)
    assert len(result.trades) == 1


def test_short_take_profit_symmetric() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 100, 97, 99)])
    result = run_backtest(bars, make_signals(bars, shorts=[0]), params(), close_at_end=False)
    trade = result.trades[0]
    assert trade.side == "short" and trade.exit_reason == "tp"
    assert trade.exit_price == pytest.approx(98.0)
    assert trade.pnl == pytest.approx(10 * 2.0)


def test_short_stop_loss_on_high() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 101.5, 100, 100)])
    result = run_backtest(bars, make_signals(bars, shorts=[0]), params(), close_at_end=False)
    trade = result.trades[0]
    assert trade.exit_reason == "sl" and trade.exit_price == pytest.approx(101.0)
    assert trade.pnl == pytest.approx(-10 * 1.0)


def test_fees_are_charged_both_ways() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 103, 100, 101)])
    result = run_backtest(bars, make_signals(bars, longs=[0]), params(fees_frac=0.001), close_at_end=False)
    trade = result.trades[0]
    expected_fees = 100 * 10 * 0.001 + 102 * 10 * 0.001
    assert trade.fees == pytest.approx(expected_fees)
    assert trade.pnl == pytest.approx(10 * 2.0 - expected_fees)
    assert result.fees_total == pytest.approx(expected_fees)


def test_no_trade_when_budget_below_one_share() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 100, 100, 100)])
    result = run_backtest(bars, make_signals(bars, longs=[0]), params(init_cash=500.0), close_at_end=False)
    assert result.trades == []


def test_equity_marks_open_position_to_close() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 100, 100, 101)])
    result = run_backtest(bars, make_signals(bars, longs=[0]), params(), close_at_end=False)
    assert result.equity.iloc[0] == pytest.approx(10_000.0)
    assert result.equity.iloc[1] == pytest.approx(10_000.0 + 10 * 1.0)


def test_open_position_is_closed_at_end_when_requested() -> None:
    bars = make_bars([(100, 100, 100, 100), (100, 100, 100, 101)])
    result = run_backtest(bars, make_signals(bars, longs=[0]), params(), close_at_end=True)
    assert result.trades[0].exit_reason == "end" and result.trades[0].exit_price == pytest.approx(101.0)


def test_execution_params_from_config(config: dict) -> None:
    p = ExecutionParams.from_config(config)
    reference = float(config["exits"]["index_reference"])
    assert p.tp_frac == pytest.approx(30 / reference) and p.sl_frac == pytest.approx(15 / reference)
    assert p.tp_frac == pytest.approx(2 * p.sl_frac)  # ratio 2:1 du script de l'ami
    assert p.fees_frac > 0 and p.slippage_frac > 0  # invariant 2 : jamais de backtest sans coûts
