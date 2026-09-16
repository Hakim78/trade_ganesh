# Makefile — commandes du projet (CLAUDE.md). Sous Windows sans make : voir README, section « Commandes ».
PY ?= .venv/Scripts/python.exe
ifeq ($(wildcard $(PY)),)
PY := python
endif

.PHONY: install test lint smoke backtest backtest-oos live dashboard-build hooks clean

install:            ## venv + dépendances Python (uv) + frontend (npm)
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -e ".[dev]"
	cd frontend && npm install

test:               ## pytest, doit passer avant tout commit
	$(PY) -m pytest

lint:               ## ruff
	$(PY) -m ruff check .

smoke:              ## backtest sur la fenêtre de mise au point (60 jours yfinance, hors étude)
	$(PY) -m backtest.run --period smoke

backtest:           ## backtest in-sample (historique Alpaca, clés dans .env)
	$(PY) -m backtest.run --period in_sample

backtest-oos:       ## out-of-sample : UNE SEULE FOIS, après le verdict in-sample (docs/AUDIT.md)
	$(PY) -m backtest.run --period out_of_sample

live:               ## paper trading Alpaca (streaming), logs dans outputs/live/
	$(PY) -m live.run

dashboard-build:    ## build du frontend React dans frontend/dist
	cd frontend && npm run build

hooks:              ## active le hook git pre-commit du projet
	git config core.hooksPath .claude/hooks

clean:
	rm -rf outputs/*.csv outputs/*.json outputs/*.png outputs/*.html .pytest_cache .ruff_cache
