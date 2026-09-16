"""Contrat de `outputs/dashboard.json` (lu par le frontend React) : horodatages en secondes UTC, uniques."""

from __future__ import annotations

import json

import pandas as pd

from backtest.engine import ExecutionParams, run_backtest
from backtest.report import build_dashboard, compute_metrics
from strategy import StrategyParams, generate_signals


def test_dashboard_json_contract(bars_short: pd.DataFrame, params: StrategyParams, config: dict) -> None:
    signals = generate_signals(bars_short, params)
    result = run_backtest(bars_short, signals, ExecutionParams.from_config(config))
    metrics = compute_metrics(result, config)
    dashboard = build_dashboard(result, config, "smoke", "QQQ", metrics)

    times = [b["t"] for b in dashboard["bars"]]
    assert times == sorted(times) and len(set(times)) == len(times)
    assert times[0] == int(bars_short.index[0].timestamp())  # secondes UTC, pas nanosecondes
    assert times[-1] == int(bars_short.index[-1].timestamp())
    assert all(s["t"] in set(times) for s in dashboard["signals"])
    assert all(t["entry_t"] in set(times) for t in dashboard["trades"])
    assert all(t["exit_t"] is None or t["exit_t"] in set(times) for t in dashboard["trades"])
    assert dashboard["equity"][0]["t"] == times[0]
    assert {m["key"] for m in dashboard["metrics"]} >= {"total_return_pct", "profit_factor", "trades_count"}
    json.dumps(dashboard)  # sérialisable (pas de NaN / numpy)


def test_bars_have_no_nan_in_ohlc(bars_short: pd.DataFrame, params: StrategyParams, config: dict) -> None:
    signals = generate_signals(bars_short, params)
    result = run_backtest(bars_short, signals, ExecutionParams.from_config(config))
    dashboard = build_dashboard(result, config, "smoke", "QQQ", compute_metrics(result, config))
    assert all(b[k] is not None for b in dashboard["bars"] for k in ("o", "h", "l", "c"))
