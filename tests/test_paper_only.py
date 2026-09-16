"""Invariant 6 : aucun ordre réel, jamais. L'endpoint Alpaca est paper-api.alpaca.markets, partout."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from common.config import ROOT
from live.broker import assert_paper_url
from live.engine import breaker_tripped

LIVE_HOST_PATTERN = re.compile(r"https?://api\.alpaca\.markets")


def test_config_endpoint_is_paper(config: dict) -> None:
    assert config["live"]["paper_only"] is True
    assert "paper-api.alpaca.markets" in config["live"]["base_url"]


def test_env_example_endpoint_is_paper() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ALPACA_BASE_URL=https://paper-api.alpaca.markets" in text


def test_assert_paper_url_refuses_live_endpoint() -> None:
    assert assert_paper_url("https://paper-api.alpaca.markets") == "https://paper-api.alpaca.markets"
    with pytest.raises(RuntimeError):
        assert_paper_url("https://" + "api.alpaca.markets")


def test_no_live_endpoint_in_source_code() -> None:
    for path in list(Path(ROOT / "live").glob("*.py")) + list(Path(ROOT / "backtest").glob("*.py")):
        assert not LIVE_HOST_PATTERN.search(path.read_text(encoding="utf-8")), path


def test_breaker_threshold() -> None:
    assert breaker_tripped(98_000, 100_000, 2.0) is True
    assert breaker_tripped(98_500, 100_000, 2.0) is False
    assert breaker_tripped(100_000, 0, 2.0) is False
