# Backtest & Live — NASDAQ / S&P

## But
Vérifier une stratégie d'entrée discrétionnaire-devenue-systématique sur NASDAQ et S&P 500 :
1. en batch sur l'historique (VectorBT),
2. en streaming sur les séances live via Alpaca paper trading.
Aucun ordre réel, jamais. Paper uniquement.

## Stratégie
@docs/STRATEGY.md

## Architecture (un seul code de stratégie, deux points d'entrée)
- `strategy/strategy.py` — fonction pure `generate_signals(df: DataFrame[OHLCV]) -> DataFrame[entries, exits]`. Aucun I/O, aucun état, aucun accès réseau.
- `backtest/run.py` — charge l'historique, appelle `generate_signals`, exécute via VectorBT, écrit `outputs/`.
- `live/run.py` — consomme le flux Alpaca (websocket), reconstruit les bougies, appelle `generate_signals` à la clôture de chaque bougie, logue le signal, passe un ordre paper.
- `config.yaml` — instrument, timeframe, paramètres, frais, slippage, capital, sizing. Zéro paramètre en dur dans le code.
- `tests/` — voir invariants.

## Invariants (bloquants)
1. Pas de look-ahead : à l'index t, `generate_signals` ne voit que les bougies ≤ t **clôturées**. La bougie en cours n'existe pas pour la stratégie.
2. Frais + slippage toujours appliqués dans le backtest, valeurs lues dans `config.yaml`.
3. Parité batch/live : sur une même série de bougies, `backtest` et `live` produisent exactement les mêmes signaux. Test obligatoire.
4. Split out-of-sample figé dans `config.yaml` avant tout backtest. Aucun paramètre n'est choisi sur l'OOS.
5. Clés API uniquement via `.env` (gitignored). `.env.example` committé.
6. Aucun ordre live réel : l'endpoint Alpaca est `paper-api.alpaca.markets`, vérifié par un test.

## Stack
Python 3.12 · pandas · vectorbt · alpaca-py · quantstats · pyyaml · pytest · Docker + docker-compose

## Commandes
- `make test` — pytest, doit passer avant tout commit
- `docker compose run backtest` — batch, écrit `outputs/{trades.csv, metrics.json, equity.png, tearsheet.html}`
- `docker compose up live` — streaming paper, logs dans `outputs/live/`

## Conventions
- Type hints partout, `ruff` propre.
- Une fonction = une responsabilité. La stratégie ne connaît ni VectorBT ni Alpaca.
- Toute décision d'architecture notée dans `docs/DECISIONS.md` (une ligne, datée).
- Langue des commentaires et docs : français. Noms de code : anglais.

## Skills disponibles (ordre d'usage)
quant-research (cadrage) → setup/backtest/optimize (moteur) → backtest-review + strategy-critique (audit) → tearsheet-generator (rapport) → position-sizer + drawdown-circuit-breaker (live) → friend-strategy (source de vérité de la stratégie)

## Ne fais jamais
- Optimiser des paramètres sur l'OOS.
- Passer un backtest sans coûts.
- Modifier `strategy.py` pour "faire passer" un test de parité : c'est le test qui a raison.
- Commiter `.env`, des données brutes, ou `outputs/`.
