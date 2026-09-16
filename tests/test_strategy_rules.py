"""Un test par règle de docs/STRATEGY.md, sur des mini-séries de bougies construites à la main.

Contexte des scénarios : QQQ, été (EDT = UTC-4). La fenêtre 14h–18h UTC correspond à 10:00–13:55 ET.
Base : 30 bougies « plates » (open = close = 101, low = 100, high = 101.5), puis une bougie de test dont on
contrôle low / high / close et l'heure. Sur la base, prev_low = 100, prev_high = 101.5, VWAP ≈ EMA ≈ 101.
"""

from __future__ import annotations

import pandas as pd
import pytest

from strategy import StrategyParams, generate_signals

ET = "America/New_York"
BASE_LOW, BASE_HIGH, BASE_CLOSE = 100.0, 101.5, 101.0


def flat_bars(day: str, start: str, n: int, close: float = BASE_CLOSE) -> pd.DataFrame:
    index = pd.date_range(f"{day} {start}", periods=n, freq="5min", tz=ET)
    return flat_bars_on(index, close)


def flat_bars_on(index: pd.DatetimeIndex, close: float = BASE_CLOSE) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": close,
            "high": close + (BASE_HIGH - BASE_CLOSE),
            "low": close - (BASE_CLOSE - BASE_LOW),
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )


def with_test_bar(base: pd.DataFrame, *, low: float, high: float, close: float) -> pd.DataFrame:
    """Ajoute une bougie de test immédiatement après la base (open = dernière clôture)."""
    stamp = base.index[-1] + pd.Timedelta(minutes=5)
    row = pd.DataFrame(
        {"open": [base["close"].iloc[-1]], "high": [high], "low": [low], "close": [close], "volume": [1_000.0]},
        index=pd.DatetimeIndex([stamp]),
    )
    return pd.concat([base, row])


def base_in_session() -> pd.DataFrame:
    """30 bougies de 09:30 à 11:55 ET : la bougie de test tombe à 12:00 ET = 16:00 UTC, dans la fenêtre."""
    return flat_bars("2026-08-04", "09:30", 30)


@pytest.fixture
def params() -> StrategyParams:
    return StrategyParams(lookback=10, ema_len=50, session_tz="UTC", session_start_hour=14, session_end_hour=18)


# --- Entrée long ----------------------------------------------------------------------------------


def test_long_sweep_low_wick_below_close_above(params: StrategyParams) -> None:
    df = with_test_bar(base_in_session(), low=99.5, high=102.0, close=101.8)
    sig = generate_signals(df, params).iloc[-1]
    assert sig["entries"] and not sig["short_entries"]


def test_long_rejected_if_close_below_prev_low(params: StrategyParams) -> None:
    """Clôturer sous le plus bas précédent est une cassure, pas un sweep."""
    df = with_test_bar(base_in_session(), low=99.0, high=101.0, close=99.8)
    assert not generate_signals(df, params).iloc[-1]["entries"]


def test_long_rejected_if_low_not_below_prev_low(params: StrategyParams) -> None:
    df = with_test_bar(base_in_session(), low=100.0, high=102.0, close=101.8)
    assert not generate_signals(df, params).iloc[-1]["entries"]


def test_long_requires_close_above_vwap(params: StrategyParams) -> None:
    """Veille à 90 (EMA basse ≈ 97,7), VWAP du jour ≈ 101 : clôture 100,5 > EMA et > prev_low mais < VWAP."""
    previous_day = flat_bars("2026-08-03", "09:30", 78, close=90.0)
    df = with_test_bar(pd.concat([previous_day, base_in_session()]), low=99.5, high=101.0, close=100.5)
    sig = generate_signals(df, params).iloc[-1]
    assert sig["close"] > sig["ema"] and sig["close"] > sig["prev_low"]
    assert sig["close"] < sig["vwap"]
    assert not sig["entries"]


def test_long_requires_close_above_ema(params: StrategyParams) -> None:
    """Veille à 110 (EMA haute ≈ 103,7), VWAP du jour ≈ 101 : clôture 101,8 > VWAP mais < EMA."""
    previous_day = flat_bars("2026-08-03", "09:30", 78, close=110.0)
    df = with_test_bar(pd.concat([previous_day, base_in_session()]), low=99.5, high=102.0, close=101.8)
    sig = generate_signals(df, params).iloc[-1]
    assert sig["close"] > sig["vwap"] and sig["close"] < sig["ema"]
    assert not sig["entries"]


# --- Entrée short ---------------------------------------------------------------------------------


def test_short_sweep_high_symmetric(params: StrategyParams) -> None:
    """Mèche au-dessus du plus haut précédent (101,5), clôture en dessous, sous VWAP et EMA."""
    df = with_test_bar(base_in_session(), low=100.0, high=102.5, close=100.2)
    sig = generate_signals(df, params).iloc[-1]
    assert sig["short_entries"] and not sig["entries"]


def test_short_rejected_if_close_above_vwap(params: StrategyParams) -> None:
    """Veille à 112 (EMA ≈ 104, tendance baissière OK), mais clôture 101,4 > VWAP ≈ 101,01 : refus."""
    previous_day = flat_bars("2026-08-03", "09:30", 78, close=112.0)
    df = with_test_bar(pd.concat([previous_day, base_in_session()]), low=100.5, high=102.5, close=101.4)
    sig = generate_signals(df, params).iloc[-1]
    assert sig["close"] < sig["ema"] and sig["close"] < sig["prev_high"]
    assert sig["close"] > sig["vwap"]
    assert not sig["short_entries"]


def test_short_rejected_if_close_above_prev_high(params: StrategyParams) -> None:
    """Clôturer au-dessus du plus haut précédent est une cassure haussière, pas un sweep."""
    df = with_test_bar(base_in_session(), low=100.5, high=103.0, close=102.5)
    assert not generate_signals(df, params).iloc[-1]["short_entries"]


# --- Filtre horaire -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("test_bar_et", "expected"),
    [
        ("09:55", False),  # 13:55 UTC : avant la fenêtre
        ("10:00", True),  # 14:00 UTC : première bougie autorisée
        ("13:55", True),  # 17:55 UTC : dernière bougie autorisée
        ("14:00", False),  # 18:00 UTC : exclu
        ("15:55", False),  # 19:55 UTC : exclu
    ],
)
def test_session_filter_boundaries(params: StrategyParams, test_bar_et: str, expected: bool) -> None:
    """Même sweep haussier valide, seule l'heure de la bougie de test change."""
    test_stamp = pd.Timestamp(f"2026-08-04 {test_bar_et}", tz=ET)
    base_index = pd.date_range(end=test_stamp - pd.Timedelta(minutes=5), periods=30, freq="5min")
    df = with_test_bar(flat_bars_on(base_index), low=99.5, high=102.0, close=101.8)
    sig = generate_signals(df, params).iloc[-1]
    assert bool(sig["in_session"]) is expected
    assert bool(sig["entries"]) is expected


def test_session_filter_applies_to_short_too(params: StrategyParams) -> None:
    test_stamp = pd.Timestamp("2026-08-04 14:30", tz=ET)  # 18:30 UTC : hors fenêtre
    base_index = pd.date_range(end=test_stamp - pd.Timedelta(minutes=5), periods=30, freq="5min")
    df = with_test_bar(flat_bars_on(base_index), low=100.0, high=102.5, close=100.2)
    assert not generate_signals(df, params).iloc[-1]["short_entries"]


# --- Indicateurs ----------------------------------------------------------------------------------


def test_vwap_resets_each_session(params: StrategyParams) -> None:
    day1 = flat_bars("2026-08-03", "09:30", 78, close=110.0)
    day2 = flat_bars("2026-08-04", "09:30", 5, close=101.0)
    ind = generate_signals(pd.concat([day1, day2]), params)
    assert ind.loc[day1.index[-1], "vwap"] == pytest.approx(110.0)
    assert ind.loc[day2.index[0], "vwap"] == pytest.approx(101.0)  # une seule bougie : VWAP = close


def test_vwap_uses_close_weighted_by_volume(params: StrategyParams) -> None:
    index = pd.date_range("2026-08-04 09:30", periods=2, freq="5min", tz=ET)
    df = pd.DataFrame(
        {"open": [100.0, 100.0], "high": [110.0, 110.0], "low": [90.0, 90.0], "close": [100.0, 104.0],
         "volume": [1_000.0, 3_000.0]},
        index=index,
    )
    ind = generate_signals(df, params)
    assert ind["vwap"].iloc[1] == pytest.approx((100.0 * 1_000 + 104.0 * 3_000) / 4_000)


def test_reverse_signal_is_an_exit(params: StrategyParams) -> None:
    df = with_test_bar(base_in_session(), low=100.0, high=102.5, close=100.2)  # short valide
    sig = generate_signals(df, params)
    pd.testing.assert_series_equal(sig["exits"], sig["short_entries"], check_names=False)
    pd.testing.assert_series_equal(sig["short_exits"], sig["entries"], check_names=False)


def test_no_signal_during_warmup(params: StrategyParams) -> None:
    df = flat_bars("2026-08-04", "10:00", params.lookback)
    sig = generate_signals(df, params)
    assert not sig["entries"].any() and not sig["short_entries"].any()
    assert sig["prev_low"].isna().all()


def test_rejects_naive_index(params: StrategyParams) -> None:
    df = base_in_session()
    df.index = df.index.tz_localize(None)
    with pytest.raises(ValueError):
        generate_signals(df, params)


def test_params_from_config(config: dict) -> None:
    params = StrategyParams.from_config(config)
    assert params.lookback == 10 and params.ema_len == 50
    assert params.session_start_hour == 14 and params.session_end_hour == 18
