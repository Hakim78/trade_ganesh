"""Invariant 3 : sur une même série de bougies, backtest et live produisent exactement les mêmes signaux.

Chemin batch : `generate_signals(bars)` d'un coup. Chemin live : `LiveEngine.on_closed_bar` bougie par bougie,
avec les bougies 5 min reconstruites à partir de bougies 1 min par `BarAggregator`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from live.engine import LiveEngine, decide
from live.feed import BarAggregator, MinuteBar
from strategy import StrategyParams, generate_signals

ET = "America/New_York"


def split_into_minutes(bars: pd.DataFrame, seed: int = 3) -> list[MinuteBar]:
    """Découpe chaque bougie 5 min en 5 bougies 1 min cohérentes (mêmes open/high/low/close/volume agrégés)."""
    rng = np.random.default_rng(seed)
    minutes: list[MinuteBar] = []
    for stamp, row in bars.iterrows():
        o, h, low, c, v = row["open"], row["high"], row["low"], row["close"], row["volume"]
        closes = [o, h, low, c, c]
        rng.shuffle(closes[1:3])  # le high et le low tombent sur des minutes différentes
        closes[0] = o
        closes[-1] = c
        prev = o
        for k in range(5):
            close = closes[k]
            hi = max(prev, close, h if close == h else -np.inf)
            lo = min(prev, close, low if close == low else np.inf)
            minutes.append(MinuteBar(pd.Timestamp(stamp) + pd.Timedelta(minutes=k), prev, hi, lo, close, v / 5))
            prev = close
    return minutes


def test_live_signals_equal_batch_signals(bars_short: pd.DataFrame, params: StrategyParams) -> None:
    bars = bars_short
    batch = generate_signals(bars, params)
    engine = LiveEngine(params, history=None)
    live_long, live_short = [], []
    for stamp, row in bars.iterrows():
        bar = row.copy()
        bar.name = stamp
        signal = engine.on_closed_bar(bar)
        live_long.append(signal == "long")
        live_short.append(signal == "short")
    assert live_long == batch["entries"].tolist()
    assert live_short == batch["short_entries"].tolist()
    assert batch["entries"].sum() + batch["short_entries"].sum() > 0, "le jeu de test doit produire des signaux"


def test_aggregated_minutes_rebuild_the_same_five_minute_bars(bars: pd.DataFrame, config: dict) -> None:
    instrument = config["instrument"]
    aggregator = BarAggregator(5, instrument["exchange_tz"], instrument["rth_start"], instrument["rth_end"])
    rebuilt = []
    for minute in split_into_minutes(bars):
        completed = aggregator.push(minute)
        if completed is not None:
            rebuilt.append(completed)
    final = aggregator.flush_if_elapsed(bars.index[-1] + pd.Timedelta(minutes=5))
    assert final is not None
    rebuilt.append(final)
    rebuilt_df = pd.DataFrame(rebuilt)
    rebuilt_df.index = pd.DatetimeIndex(rebuilt_df.index)
    pd.testing.assert_frame_equal(rebuilt_df, bars.tz_convert(instrument["exchange_tz"]), check_freq=False,
                                  check_names=False)


def test_live_path_with_aggregation_matches_batch(bars_short: pd.DataFrame, params: StrategyParams,
                                                  config: dict) -> None:
    bars = bars_short
    instrument = config["instrument"]
    aggregator = BarAggregator(5, instrument["exchange_tz"], instrument["rth_start"], instrument["rth_end"])
    engine = LiveEngine(params, history=None)
    signals: dict[pd.Timestamp, str | None] = {}
    for minute in split_into_minutes(bars):
        completed = aggregator.push(minute)
        if completed is not None:
            signals[pd.Timestamp(completed.name)] = engine.on_closed_bar(completed)
    final = aggregator.flush_if_elapsed(bars.index[-1] + pd.Timedelta(minutes=5))
    assert final is not None
    signals[pd.Timestamp(final.name)] = engine.on_closed_bar(final)
    batch = generate_signals(bars, params)
    for stamp, row in batch.iterrows():
        expected = "long" if row["entries"] else ("short" if row["short_entries"] else None)
        assert signals[pd.Timestamp(stamp).tz_convert(instrument["exchange_tz"])] == expected, stamp


def test_decision_rules() -> None:
    assert decide(None, None, False) is None
    assert decide("long", None, False) == "open_long"
    assert decide("short", None, False) == "open_short"
    assert decide("long", "long", False) == "ignore"  # pas de renfort
    assert decide("short", "long", False) == "reverse_to_short"
    assert decide("long", "short", False) == "reverse_to_long"
    assert decide("long", None, True) == "halted"  # coupe-circuit : aucune entrée
