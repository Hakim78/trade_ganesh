"""Invariant 1 : à l'index t, `generate_signals` ne voit que les bougies <= t clôturées.

Pour des t tirés au hasard, on tronque la série à t et on vérifie que la dernière ligne est identique à la
ligne t obtenue sur la série complète. On vérifie aussi qu'altérer le futur ne change rien au passé.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategy import StrategyParams, generate_signals
from strategy.strategy import SIGNAL_COLUMNS

INDICATOR_COLUMNS = ("vwap", "ema", "prev_high", "prev_low", "in_session")


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_truncated_series_gives_same_row(bars: pd.DataFrame, params: StrategyParams, seed: int) -> None:
    rng = np.random.default_rng(seed)
    full = generate_signals(bars, params)
    for t in rng.integers(params.ema_len, len(bars) - 1, size=25):
        truncated = generate_signals(bars.iloc[: t + 1], params)
        last = truncated.iloc[-1]
        expected = full.iloc[t]
        for column in SIGNAL_COLUMNS:
            assert bool(last[column]) == bool(expected[column]), f"{column} diffère à t={t}"
        for column in INDICATOR_COLUMNS:
            a, b = last[column], expected[column]
            if isinstance(a, (bool, np.bool_)):
                assert a == b
            else:
                assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b, rel=1e-12), f"{column} à t={t}"


def test_future_bars_do_not_change_past_signals(bars: pd.DataFrame, params: StrategyParams) -> None:
    t = len(bars) // 2
    reference = generate_signals(bars, params)
    altered = bars.copy()
    altered.iloc[t + 1 :, :4] *= 1.05  # choc de +5 % sur tout le futur
    altered.iloc[t + 1 :, 4] *= 3.0  # et triple volume
    perturbed = generate_signals(altered, params)
    for column in SIGNAL_COLUMNS:
        pd.testing.assert_series_equal(perturbed[column].iloc[: t + 1], reference[column].iloc[: t + 1])
    for column in ("vwap", "ema", "prev_high", "prev_low"):
        pd.testing.assert_series_equal(perturbed[column].iloc[: t + 1], reference[column].iloc[: t + 1])


def test_current_bar_is_not_in_prev_levels(bars: pd.DataFrame, params: StrategyParams) -> None:
    """prev_high / prev_low = extrêmes des `lookback` bougies précédentes, bougie courante exclue."""
    ind = generate_signals(bars, params)
    n = params.lookback
    for t in (n, n + 7, len(bars) - 1):
        window = bars.iloc[t - n : t]
        assert ind["prev_high"].iloc[t] == pytest.approx(window["high"].max())
        assert ind["prev_low"].iloc[t] == pytest.approx(window["low"].min())
