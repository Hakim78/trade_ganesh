"""Rapports du backtest : métriques, fichiers `outputs/` et `dashboard.json` pour le frontend React.

VectorBT (accesseur `vbt.returns`) calcule les ratios sur les rendements journaliers ; les statistiques de
trades viennent du journal de l'exécuteur.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backtest.engine import BacktestResult

PERIOD_LABELS = {
    "smoke": "Fenêtre de mise au point (60 j)",
    "in_sample": "In-sample",
    "out_of_sample": "Out-of-sample",
}


def _clean(value: Any) -> Any:
    """JSON-safe : NaN / inf → None, numpy → Python."""
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def daily_returns(equity: pd.Series, exchange_tz: str) -> pd.Series:
    """Rendements journaliers : equity à la dernière bougie de chaque séance, index tz-naive (dates)."""
    local = equity.tz_convert(exchange_tz)
    end_of_day = local.groupby(np.asarray(local.index.date)).last()
    end_of_day.index = pd.to_datetime(end_of_day.index)
    returns = end_of_day.pct_change().fillna(0.0)
    returns.name = "strategy"
    return returns


def benchmark_daily_returns(bars: pd.DataFrame, exchange_tz: str) -> pd.Series:
    """Buy & hold du sous-jacent, clôture à clôture de séance."""
    local = bars["close"].tz_convert(exchange_tz)
    end_of_day = local.groupby(np.asarray(local.index.date)).last()
    end_of_day.index = pd.to_datetime(end_of_day.index)
    returns = end_of_day.pct_change().fillna(0.0)
    returns.name = "buy_hold"
    return returns


def drawdown_pct(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return (equity / peak - 1.0) * 100.0


def vbt_ratios(returns: pd.Series) -> dict[str, float | None]:
    """Ratios VectorBT sur rendements journaliers (252 séances par an)."""
    import vectorbt as vbt  # noqa: F401  (enregistre l'accesseur .vbt)

    accessor = returns.vbt.returns(freq="1D", year_freq="252D")
    out: dict[str, float | None] = {}
    for key, fn in (
        ("sharpe_daily", accessor.sharpe_ratio),
        ("sortino_daily", accessor.sortino_ratio),
        ("calmar", accessor.calmar_ratio),
        ("annualized_return_pct", accessor.annualized),
        ("annualized_vol_pct", accessor.annualized_volatility),
    ):
        try:
            value = float(fn())
        except Exception:  # noqa: BLE001 - un ratio indisponible ne doit pas casser le rapport
            value = float("nan")
        if key.endswith("_pct"):
            value *= 100.0
        out[key] = _clean(value)
    return out


def compute_metrics(result: BacktestResult, config: dict[str, Any]) -> dict[str, Any]:
    trades = result.trades_frame()
    closed = trades[trades["status"] == "closed"]
    init_cash = result.params.init_cash
    final_equity = float(result.equity.iloc[-1]) if len(result.equity) else init_cash
    wins = closed[closed["pnl"] > 0]
    losses = closed[closed["pnl"] < 0]
    gross_profit = float(wins["pnl"].sum())
    gross_loss = float(-losses["pnl"].sum())
    if gross_loss > 0:
        profit_factor: float | None = gross_profit / gross_loss
    else:
        profit_factor = None if gross_profit == 0 else float("inf")
    exchange_tz = config["instrument"]["exchange_tz"]
    returns = daily_returns(result.equity, exchange_tz) if len(result.equity) else pd.Series(dtype=float)

    metrics: dict[str, Any] = {
        "init_cash": init_cash,
        "final_equity": final_equity,
        "net_pnl": final_equity - init_cash,
        "total_return_pct": (final_equity / init_cash - 1.0) * 100.0,
        "max_drawdown_pct": float(drawdown_pct(result.equity).min()) if len(result.equity) else 0.0,
        "trades_count": int(len(closed)),
        "trades_long": int((closed["side"] == "long").sum()),
        "trades_short": int((closed["side"] == "short").sum()),
        "win_rate_pct": (100.0 * len(wins) / len(closed)) if len(closed) else None,
        "profit_factor": profit_factor,
        "expectancy": float(closed["pnl"].mean()) if len(closed) else None,
        "avg_trade_pct": float(closed["return_pct"].mean()) if len(closed) else None,
        "avg_win_pct": float(wins["return_pct"].mean()) if len(wins) else None,
        "avg_loss_pct": float(losses["return_pct"].mean()) if len(losses) else None,
        "avg_bars_held": float(closed["bars_held"].mean()) if len(closed) else None,
        "exits_tp": int((closed["exit_reason"] == "tp").sum()),
        "exits_sl": int((closed["exit_reason"] == "sl").sum()),
        "exits_reverse": int((closed["exit_reason"] == "reverse").sum()),
        "fees_total": result.fees_total,
        "signals_long": int(result.signals["entries"].sum()),
        "signals_short": int(result.signals["short_entries"].sum()),
        "bars": int(len(result.bars)),
        "sessions": int(len(returns)),
    }
    if len(returns) > 1:
        metrics.update(vbt_ratios(returns))
    return {k: _clean(v) for k, v in metrics.items()}


def yearly_table(result: BacktestResult, exchange_tz: str) -> list[dict[str, Any]]:
    if result.equity.empty:
        return []
    local_equity = result.equity.tz_convert(exchange_tz)
    years = np.asarray(local_equity.index.year)
    trades = result.trades_frame()
    closed = trades[trades["status"] == "closed"].copy()
    if not closed.empty:
        closed["year"] = pd.DatetimeIndex(closed["exit_time"]).tz_convert(exchange_tz).year
    rows = []
    previous_end: float | None = None
    for year in sorted(set(years)):
        segment = local_equity[years == year]
        start = previous_end if previous_end is not None else float(segment.iloc[0])
        end = float(segment.iloc[-1])
        previous_end = end
        year_trades = closed[closed["year"] == year] if not closed.empty else closed
        win_rate = (100.0 * (year_trades["pnl"] > 0).mean()) if len(year_trades) else None
        rows.append({
            "year": int(year),
            "return_pct": _clean((end / start - 1.0) * 100.0 if start else None),
            "trades": int(len(year_trades)),
            "win_rate_pct": _clean(win_rate),
        })
    return rows


def metric_tiles(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Tuiles affichées en tête du tableau de bord, dans cet ordre."""
    spec = [
        ("total_return_pct", "Rendement net", "pct", "frais et slippage déduits"),
        ("net_pnl", "P&L net", "money", None),
        ("profit_factor", "Profit factor", "ratio", "gains bruts / pertes brutes, > 1 = rentable"),
        ("win_rate_pct", "Taux de réussite", "pct", "part des trades gagnants"),
        ("trades_count", "Trades", "int", None),
        ("max_drawdown_pct", "Drawdown max", "pct", "pire recul depuis un sommet"),
        ("sharpe_daily", "Sharpe", "ratio", "sur rendements journaliers, annualisé"),
        ("expectancy", "Gain moyen / trade", "money", None),
        ("avg_bars_held", "Durée moyenne", "number", "en bougies de 5 min"),
        ("fees_total", "Coûts payés", "money", "frais + slippage"),
    ]
    tiles = []
    for key, label, fmt, hint in spec:
        value = metrics.get(key)
        if key == "win_rate_pct" and isinstance(value, (int, float)):
            value = value  # déjà en %
        tiles.append({"key": key, "label": label, "value": value, "format": fmt, "hint": hint})
    return tiles


def _downsample(series: pd.Series, max_points: int) -> pd.Series:
    if len(series) <= max_points:
        return series
    idx = np.unique(np.concatenate([np.linspace(0, len(series) - 1, max_points).astype(int), [len(series) - 1]]))
    return series.iloc[idx]


def build_dashboard(result: BacktestResult, config: dict[str, Any], period: str, symbol: str,
                    metrics: dict[str, Any]) -> dict[str, Any]:
    exchange_tz = config["instrument"]["exchange_tz"]
    max_bars = int(config.get("dashboard", {}).get("max_bars", 20000))
    sig = result.signals
    tail = sig.iloc[-max_bars:]
    # as_unit("s") : l'index peut être en secondes ou en nanosecondes selon la source (pandas >= 2 / 3)
    unix = tail.index.tz_convert("UTC").as_unit("s").asi8.astype(int)

    bars = [
        {
            "t": int(t), "o": _clean(o), "h": _clean(h), "l": _clean(lo), "c": _clean(c), "v": _clean(v),
            "vwap": _clean(vw), "ema": _clean(e), "ph": _clean(ph), "pl": _clean(pl), "s": int(bool(s)),
        }
        for t, o, h, lo, c, v, vw, e, ph, pl, s in zip(
            unix, tail["open"], tail["high"], tail["low"], tail["close"], tail["volume"], tail["vwap"], tail["ema"],
            tail["prev_high"], tail["prev_low"], tail["in_session"], strict=True,
        )
    ]
    first_exported = tail.index[0] if len(tail) else None
    signals = [
        {"t": int(ts.tz_convert("UTC").timestamp()), "side": "long"}
        for ts in sig.index[sig["entries"].to_numpy(bool)]
        if first_exported is None or ts >= first_exported
    ] + [
        {"t": int(ts.tz_convert("UTC").timestamp()), "side": "short"}
        for ts in sig.index[sig["short_entries"].to_numpy(bool)]
        if first_exported is None or ts >= first_exported
    ]
    signals.sort(key=lambda s: s["t"])

    trades = []
    for t in result.trades:
        trades.append({
            "id": t.id, "side": t.side,
            "entry_t": int(t.entry_time.tz_convert("UTC").timestamp()),
            "exit_t": int(t.exit_time.tz_convert("UTC").timestamp()) if t.exit_time is not None else None,
            "entry_px": _clean(t.entry_price), "exit_px": _clean(t.exit_price), "size": int(t.size),
            "pnl": _clean(t.pnl), "ret_pct": _clean(t.return_pct), "status": "open" if t.is_open else "closed",
            "reason": t.exit_reason,
        })

    equity = _downsample(result.equity, 5000)
    dd = drawdown_pct(result.equity).reindex(equity.index)
    equity_points = [
        {"t": int(ts.tz_convert("UTC").timestamp()), "value": _clean(v), "dd_pct": _clean(d)}
        for ts, v, d in zip(equity.index, equity, dd, strict=True)
    ]

    tp_frac, sl_frac = result.params.tp_frac, result.params.sl_frac
    session = config["strategy"]["session_filter"]
    start = result.bars.index[0].tz_convert(exchange_tz).strftime("%Y-%m-%d") if len(result.bars) else ""
    end = result.bars.index[-1].tz_convert(exchange_tz).strftime("%Y-%m-%d") if len(result.bars) else ""
    return {
        "meta": {
            "symbol": symbol,
            "timeframe": str(config["timeframe"]),
            "period": period,
            "period_label": PERIOD_LABELS.get(period, period),
            "start": start,
            "end": end,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": str(config["data"]["source"]),
            "bars_total": int(len(result.bars)),
            "bars_exported": int(len(bars)),
            "strategy": {
                "lookback": int(config["strategy"]["lookback"]),
                "ema_len": int(config["strategy"]["ema_len"]),
                "session": f"{session['start_hour']:02d}h–{session['end_hour']:02d}h {session['tz']}",
                "tp_points": float(config["exits"]["tp_points"]),
                "sl_points": float(config["exits"]["sl_points"]),
                "tp_pct": tp_frac,
                "sl_pct": sl_frac,
                "fees_pct": result.params.fees_frac,
                "slippage_pct": result.params.slippage_frac,
                "init_cash": result.params.init_cash,
                "size_pct_equity": result.params.size_pct_equity,
            },
        },
        "metrics": metric_tiles(metrics),
        "bars": bars,
        "signals": signals,
        "trades": trades,
        "equity": equity_points,
        "yearly": yearly_table(result, exchange_tz),
    }


def write_equity_png(result: BacktestResult, path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    equity = result.equity
    ax1.plot(equity.index, equity.values, color="#4f8cff", linewidth=1.2)
    ax1.axhline(result.params.init_cash, color="#888", linestyle="--", linewidth=0.8)
    ax1.set_title(title)
    ax1.set_ylabel("Capital ($)")
    ax1.grid(alpha=0.3)
    dd = drawdown_pct(equity)
    ax2.fill_between(dd.index, dd.values, 0, color="#ef4444", alpha=0.5)
    ax2.set_ylabel("Drawdown (%)")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_tearsheet(result: BacktestResult, config: dict[str, Any], path: Path, title: str) -> str | None:
    """Tearsheet QuantStats (rendements journaliers vs buy & hold). Renvoie un message d'erreur, ou None."""
    try:
        import quantstats as qs

        exchange_tz = config["instrument"]["exchange_tz"]
        returns = daily_returns(result.equity, exchange_tz)
        benchmark = benchmark_daily_returns(result.bars, exchange_tz).reindex(returns.index).fillna(0.0)
        qs.reports.html(returns, benchmark=benchmark, output=str(path), title=title, download_filename=path.name)
        return None
    except Exception as exc:  # noqa: BLE001 - le tearsheet est un bonus, jamais bloquant
        return f"{type(exc).__name__}: {exc}"


def write_outputs(result: BacktestResult, config: dict[str, Any], period: str, symbol: str, outputs_dir: Path,
                  with_tearsheet: bool = True) -> dict[str, Any]:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    metrics = compute_metrics(result, config)
    metrics["period"], metrics["symbol"] = period, symbol
    title = f"{symbol} {config['timeframe']} — {PERIOD_LABELS.get(period, period)}"

    result.trades_frame().to_csv(outputs_dir / "trades.csv", index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    result.signals.to_csv(outputs_dir / "signals.csv", date_format="%Y-%m-%dT%H:%M:%S%z")
    with open(outputs_dir / "metrics.json", "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, ensure_ascii=False)
    dashboard = build_dashboard(result, config, period, symbol, metrics)
    with open(outputs_dir / "dashboard.json", "w", encoding="utf-8") as handle:
        json.dump(dashboard, handle, ensure_ascii=False, separators=(",", ":"))
    write_equity_png(result, outputs_dir / "equity.png", title)
    if with_tearsheet:
        error = write_tearsheet(result, config, outputs_dir / "tearsheet.html", title)
        metrics["tearsheet_error"] = error
    return metrics
