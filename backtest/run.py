"""Point d'entrée du backtest batch.

    python -m backtest.run --period smoke          # 60 derniers jours (yfinance), mise au point, hors étude
    python -m backtest.run --period in_sample      # étude (Alpaca, clés dans .env)
    python -m backtest.run --period out_of_sample  # UNE SEULE FOIS, après le verdict in-sample

Écrit dans `outputs/` : trades.csv, signals.csv, metrics.json, equity.png, tearsheet.html, dashboard.json.
Chaque exécution est journalisée dans `outputs/runs_log.csv` (compteur d'essais de docs/HYPOTHESIS.md).
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from backtest.data import load_bars
from backtest.engine import ExecutionParams, run_backtest
from backtest.report import write_outputs
from common.config import ROOT, load_config
from strategy import StrategyParams, generate_signals


def log_run(outputs_dir: Path, period: str, symbol: str, config: dict, metrics: dict) -> None:
    path = outputs_dir / "runs_log.csv"
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(["run_at", "period", "symbol", "strategy", "exits", "trades", "profit_factor",
                             "total_return_pct", "max_drawdown_pct"])
        writer.writerow([
            datetime.now(UTC).isoformat(timespec="seconds"), period, symbol,
            json.dumps(config["strategy"], sort_keys=True), json.dumps(config["exits"], sort_keys=True),
            metrics.get("trades_count"), metrics.get("profit_factor"), metrics.get("total_return_pct"),
            metrics.get("max_drawdown_pct"),
        ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest Liquidity Sweep + VWAP")
    parser.add_argument("--period", choices=["smoke", "in_sample", "out_of_sample"], default="smoke")
    parser.add_argument("--symbol", default=None, help="par défaut instrument.symbol de config.yaml")
    parser.add_argument("--config", default=None, help="chemin d'un config.yaml alternatif")
    parser.add_argument("--outputs", default=None, help="dossier de sortie (défaut : outputs/)")
    parser.add_argument("--no-cache", action="store_true", help="ignore le cache CSV de data/")
    parser.add_argument("--no-tearsheet", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    symbol = args.symbol or str(config["instrument"]["symbol"])
    outputs_dir = Path(args.outputs) if args.outputs else ROOT / "outputs"

    if args.period == "out_of_sample":
        print("ATTENTION : l'out-of-sample se consomme une seule fois (docs/HYPOTHESIS.md). Résultat à consigner "
              "dans docs/AUDIT.md.")

    bars = load_bars(config, args.period, symbol=symbol, use_cache=not args.no_cache)
    print(f"{symbol} {config['timeframe']} — {len(bars)} bougies du {bars.index[0]} au {bars.index[-1]}")

    signals = generate_signals(bars, StrategyParams.from_config(config))
    result = run_backtest(bars, signals, ExecutionParams.from_config(config))
    metrics = write_outputs(result, config, args.period, symbol, outputs_dir, with_tearsheet=not args.no_tearsheet)
    log_run(outputs_dir, args.period, symbol, config, metrics)

    print(f"signaux : {metrics['signals_long']} long / {metrics['signals_short']} short — "
          f"trades : {metrics['trades_count']} (TP {metrics['exits_tp']}, SL {metrics['exits_sl']}, "
          f"retournements {metrics['exits_reverse']})")
    print(f"rendement net : {metrics['total_return_pct']:+.2f} % — profit factor : {metrics['profit_factor']} — "
          f"drawdown max : {metrics['max_drawdown_pct']:.2f} % — Sharpe (journalier) : {metrics.get('sharpe_daily')}")
    if metrics.get("tearsheet_error"):
        print(f"tearsheet non généré : {metrics['tearsheet_error']}")
    print(f"sorties écrites dans {outputs_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
