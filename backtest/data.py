"""Chargement des bougies historiques (5 minutes, séance uniquement), avec cache CSV dans `data/`.

Deux sources, choisies dans `config.yaml` → `data.source` :
- `yfinance` : sans clé, mais limité aux 60 derniers jours en 5 minutes. Sert à la fenêtre de mise au point.
- `alpaca`   : historique complet (clés gratuites dans `.env`). Sert à l'étude in-sample / out-of-sample.

Convention de sortie (celle attendue par `strategy.generate_signals`) : index tz-aware `America/New_York`
horodaté à l'ouverture de la bougie, colonnes open/high/low/close/volume en float, bougies RTH uniquement.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from common.config import ROOT

BAR_COLUMNS = ["open", "high", "low", "close", "volume"]


def period_bounds(config: dict[str, Any], period: str, today: date | None = None) -> tuple[date, date]:
    """Bornes (incluses) d'une période nommée de `config.yaml` → `split`."""
    split = config["split"]
    if period == "smoke":
        end = today or date.today()
        return end - timedelta(days=int(split["smoke"]["days"])), end
    if period not in split or period in ("smoke", "min_trades", "min_effective_obs"):
        raise ValueError(f"période inconnue : {period!r} (attendu : smoke, in_sample, out_of_sample)")
    return date.fromisoformat(str(split[period]["start"])), date.fromisoformat(str(split[period]["end"]))


def restrict_to_rth(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Ne garde que les bougies dont l'ouverture est dans [rth_start, rth_end) en heure de la bourse."""
    instrument = config["instrument"]
    local = df.index.tz_convert(instrument["exchange_tz"])
    start = pd.Timestamp(instrument["rth_start"]).time()
    end = pd.Timestamp(instrument["rth_end"]).time()
    minutes = local.hour * 60 + local.minute
    lo = start.hour * 60 + start.minute
    hi = end.hour * 60 + end.minute
    return df[(minutes >= lo) & (minutes < hi)]


def normalize_bars(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Colonnes en minuscules, index tz-aware en heure de la bourse, tri, dédoublonnage, RTH, floats."""
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    out = out[BAR_COLUMNS]
    if out.index.tz is None:
        raise ValueError("les bougies doivent être tz-aware")
    out.index = out.index.tz_convert(config["instrument"]["exchange_tz"])
    out.index.name = "timestamp"
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = restrict_to_rth(out, config)
    out = out.dropna(subset=["open", "high", "low", "close"])
    return out.astype(float)


def _cache_path(config: dict[str, Any], symbol: str, start: date, end: date, source: str) -> Path:
    cache_dir = ROOT / config["data"]["cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{symbol}_{config['timeframe']}_{source}_{start}_{end}.csv"


def fetch_yfinance(symbol: str, start: date, end: date, config: dict[str, Any]) -> pd.DataFrame:
    import yfinance as yf

    span_days = (end - start).days
    if span_days > 60:
        raise ValueError(
            "yfinance ne fournit que 60 jours de bougies 5 minutes : passer data.source à `alpaca` "
            "pour l'in-sample / out-of-sample"
        )
    raw = yf.Ticker(symbol).history(period="60d", interval=config["timeframe"].replace("min", "m"), prepost=False,
                                    auto_adjust=False, actions=False)
    if raw.empty:
        raise RuntimeError(f"yfinance n'a renvoyé aucune bougie pour {symbol}")
    bars = normalize_bars(raw, config)
    local_dates = bars.index.tz_convert(config["instrument"]["exchange_tz"]).date
    return bars[(local_dates >= start) & (local_dates <= end)]


def fetch_alpaca(symbol: str, start: date, end: date, config: dict[str, Any]) -> pd.DataFrame:
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    api_key, secret_key = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY absents de .env (voir .env.example)")

    minutes = int(str(config["timeframe"]).replace("min", ""))
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame(minutes, TimeFrameUnit.Minute),
        start=datetime.combine(start, datetime.min.time()),
        end=datetime.combine(end + timedelta(days=1), datetime.min.time()),
        feed=DataFeed(config["data"]["alpaca_feed"]),
        adjustment=Adjustment.RAW,
    )
    client = StockHistoricalDataClient(api_key, secret_key)
    raw = client.get_stock_bars(request).df
    if raw.empty:
        raise RuntimeError(f"Alpaca n'a renvoyé aucune bougie pour {symbol}")
    if isinstance(raw.index, pd.MultiIndex):
        raw = raw.xs(symbol, level="symbol")
    return normalize_bars(raw, config)


def load_bars(config: dict[str, Any], period: str, symbol: str | None = None, use_cache: bool = True) -> pd.DataFrame:
    """Bougies d'une période nommée, depuis le cache CSV si présent, sinon depuis la source configurée."""
    symbol = symbol or str(config["instrument"]["symbol"])
    source = str(config["data"]["source"])
    start, end = period_bounds(config, period)
    cache = _cache_path(config, symbol, start, end, source)
    if use_cache and cache.exists():
        cached = pd.read_csv(cache, index_col="timestamp", parse_dates=True)
        cached.index = pd.DatetimeIndex(cached.index, tz="UTC") if cached.index.tz is None else cached.index
        return normalize_bars(cached, config)

    if source == "yfinance":
        bars = fetch_yfinance(symbol, start, end, config)
    elif source == "alpaca":
        bars = fetch_alpaca(symbol, start, end, config)
    else:
        raise ValueError(f"data.source inconnu : {source!r}")
    bars.to_csv(cache, date_format="%Y-%m-%dT%H:%M:%S%z")
    return bars
