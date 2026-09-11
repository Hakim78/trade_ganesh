# Skills du projet — inventaire, provenance, revue de sécurité

Installés le 2026-09-11 (Prompt 1 de `claude-code-trading-setup.md`). Emplacement projet
`.claude/skills/<nom>/SKILL.md` (doc officielle : https://code.claude.com/docs/en/skills), commités et
donc partagés avec toute personne qui clone le repo. Chaque skill tiers porte en tête une note
**« Adaptation projet »** qui dit ce qui change par rapport à son contexte d'origine.

Règle d'or : `CLAUDE.md` = quoi et pourquoi, skills = comment.

## Skills installés

| Skill | Source | Rôle | Description (une ligne) | Modifications apportées |
|---|---|---|---|---|
| `quant-research` | [Jimmy7892/quant-research-skill](https://github.com/Jimmy7892/quant-research-skill) | Cadrage (Phase 0) | Recherche quantitative rigoureuse : hypothèse falsifiable, split IS/OOS figé, surface de paramètres, région poolée plutôt qu'argmax, Sharpe déflaté, walk-forward, verdict écrit. 4 scripts numpy avec `--selftest`. | Section « One thing to pass on » retirée (instruction d'appel `gh api` pour étoiler le repo) ; note d'adaptation. |
| `setup` | [marketcalls/vectorbt-backtesting-skills](https://github.com/marketcalls/vectorbt-backtesting-skills) | Moteur (Phase 1-2) | Mise en place de l'environnement Python VectorBT : venv, dépendances, dossiers, `.env`. | Note d'adaptation (US / yfinance, pas OpenAlgo, TA-Lib, DuckDB). |
| `backtest` | idem | Moteur (Phase 2) | Génère un backtest VectorBT complet : signaux, frais, benchmark, stats, tearsheet, export des trades. | Note d'adaptation (stratégie unique `strategy.py`, `config.yaml`, QuantStats). |
| `optimize` | idem | Moteur (Phase 2) | Grid search de paramètres VectorBT avec heatmaps. | Note d'adaptation (in-sample uniquement, surface plutôt qu'argmax). |
| `vectorbt-expert` | idem | Moteur (référence, `user-invocable: false`) | 21 fiches de règles VectorBT : modes de simulation, sizing, stops, optimisation, walk-forward, robustesse, pièges, coûts US. | `rules/assets/*.py` (12 templates) retirés ; note d'adaptation ; table des templates annotée. |
| `backtest-review` | [shakeebshaan/claude-code-quant-skills](https://github.com/shakeebshaan/claude-code-quant-skills) | Audit (Phase 3) | Checklist look-ahead, survivorship, overfitting, coûts, slippage, régimes → PASS/FAIL par point, verdict SHIP/FIX/SCRAP. | Note d'adaptation. |
| `strategy-critique` | idem | Audit (Phase 3) | Revue adverse façon risk manager : edge, capacité, modes de défaillance, risques cachés → rating + 3 questions. | Note d'adaptation. |
| `risk-report` | idem | Audit (Phase 3) | Résumé de risque une page à partir d'une série de rendus : Sharpe, Sortino, drawdown, CVaR, queues, stabilité. | Note d'adaptation. |
| `data-scrub` | idem | Audit données (Phase 2) | Audit d'un CSV OHLCV : gaps, timezone, doublons, barres figées, ajustements dividendes/splits. | Note d'adaptation. |
| `tearsheet-generator` | [HyperFrequency/skills](https://github.com/HyperFrequency/skills) | Rapport (Phase 4) | Tearsheet HTML de performance façon QuantStats, helpers MAE (`tearsheet_helpers.py`), gabarits HTML/CSS. | `commands/` retiré (chemin local privé de l'auteur, Nautilus Trader) ; sections Quick Start / Commands / Installation réécrites ; note d'adaptation. |
| `backtest-expert` | [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) | Audit + live (Phase 3-5) | Méthodologie « casser la stratégie » et script de scoring en 5 dimensions → Deploy / Refine / Abandon. | Note d'adaptation. |
| `position-sizer` | idem | Live (Phase 5) | Calcul de taille de position : fixed fractional, ATR, demi-Kelly, contraintes de concentration. | Note d'adaptation. |
| `drawdown-circuit-breaker` | idem | Live (Phase 5) | Règles de coupe-circuit : perte journalière max, cooldown après série perdante, limites hebdo/mensuelles en heure de New York. | Note d'adaptation. |

Skill à créer plus tard, **une fois `docs/STRATEGY.md` rempli** : `friend-strategy`, avec le skill
officiel `skill-creator` (plugin `example-skills` du marketplace `anthropics/skills`). Il deviendra la
source de vérité de la stratégie (règles, invariants, tests).

## Skills et fichiers rejetés

| Élément | Source | Raison |
|---|---|---|
| `quick-stats`, `strategy-compare` | marketcalls | Hors périmètre : orientés OpenAlgo / NIFTY et comparaison multi-stratégies ; le projet n'a qu'une stratégie. |
| `vectorbt-expert/rules/assets/*.py` (12 fichiers) | marketcalls | **Sécurité** : scripts exécutables qui lisent `OPENALGO_API_KEY` via `os.getenv` et appellent l'API OpenAlgo. Non nécessaires (stratégie unique). Les fiches `rules/*.md` sont conservées. |
| `hedge-lab`, `indicator-design` | shakeebshaan | Hors périmètre (hedging crypto, conception d'indicateurs interactive). |
| `hooks/pre-commit-backtest-check.sh` | shakeebshaan | **Absent du repo** : cité dans le README, mais le dépôt ne contient que `skills/` et `LICENSE`. Un hook équivalent a été écrit pour ce projet, voir `.claude/hooks/`. |
| `arxiv-research-search`, `context7-documentation-lookup`, `continuous-learning-pattern-extraction`, `ml-pipeline`, `nautilus-trader`, `order-flow-opt`, `research-documentation`, `strategy-translator`, `strategy-workflow` | HyperFrequency | Hors périmètre, conformément au doc (crypto, NautilusTrader, ML). Leurs scripts n'ont pas été audités puisque non retenus. |
| `tearsheet-generator/commands/*` | HyperFrequency | `generate-tearsheet.md` fait `sys.path.insert(0, '/Users/DanBot/Desktop/dev/Backtests')` (chemin hors projet, module inexistant) ; `verify-*` dépendent de Nautilus Trader. |
| `portfolio-manager` | tradermonty (marqué Alpaca) | Revue de portefeuille hebdomadaire via MCP Alpaca ; `scripts/check_alpaca_connection.py` lit `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` via `os.environ` et appelle `requests.get` sur l'API Alpaca. Hors périmètre (pas une boucle d'exécution) et lecture de secrets. |
| `parabolic-short-trade-planner` | tradermonty (marqué Alpaca) | Stratégie short discrétionnaire (~100 fichiers) ; nécessite FMP (payant) ; adaptateurs Alpaca en `requests` qui lisent `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`. Hors périmètre et lecture de secrets. |
| `breakout-trade-planner` | tradermonty (marqué Alpaca) | Plans de trade Minervini/VCP ; ne génère que des gabarits d'ordres, aucun appel réseau. Hors périmètre (discrétionnaire, dépend d'un screener VCP). |
| 72 autres skills | tradermonty | Hors périmètre (screeners, calendriers, dividendes, mémoire de trader, etc.). |

Conclusion sur le besoin n° 5 du doc : **aucun skill tiers n'implémente une boucle live Alpaca
paper pour une stratégie systématique**. La Phase 5 (`live/feed.py`, `live/run.py`) sera écrite
directement avec `alpaca-py`, endpoint `paper-api.alpaca.markets` vérifié par
`tests/test_paper_only.py`.

## Revue de sécurité (méthode et résultats)

Méthode : lecture intégrale de chaque `SKILL.md` et de chaque script retenu, puis `grep` sur
`getenv`, `environ`, `requests`, `urllib`, `socket`, `subprocess`, `open(..., 'w')`, `shutil`,
`~/`, `/Users/`, `/home/`. Critères de rejet (doc) : appel réseau non documenté, lecture de
variables d'environnement, écriture hors du dossier projet, clé API dans un skill.

| Script | Imports | Réseau | Env | Écritures | Verdict |
|---|---|---|---|---|---|
| `quant-research/scripts/{effective_n,region_pool,selection_bias,sizing}.py` | numpy, stdlib (pandas optionnel pour lire un CSV) | non | non | stdout seulement | OK |
| `tearsheet-generator/tearsheet_helpers.py` | numpy, scipy.stats | non | non | aucune (fonctions pures) | OK |
| `backtest-expert/scripts/evaluate_backtest.py` | stdlib | non | non | `reports/` (paramètre `--output-dir`) | OK |
| `position-sizer/scripts/position_sizer.py` | stdlib | non | non | `reports/` | OK |
| `drawdown-circuit-breaker/scripts/check_circuit_breaker.py` + `_market_calendar.py` | yaml, zoneinfo, pandas-market-calendars | non | non | `reports/` ; lit `state/theses/*.yaml` | OK |
| `*/scripts/tests/*.py` | pytest, subprocess (lance le script frère uniquement) | non | non | dossiers temporaires pytest | OK |

Points d'attention conservés volontairement :
- `setup/SKILL.md` décrit un `wget` de TA-Lib (étape optionnelle, désactivée par la note d'adaptation).
- `vectorbt-expert/rules/data-fetching.md` contient des extraits de code qui lisent des clés de
  fournisseurs de données via `os.getenv` : c'est de la documentation, pas un script exécuté, et
  la lecture de `.env` pour Alpaca est précisément l'invariant 5 de `CLAUDE.md`.
- Les fichiers `conftest.py` des skills ne sont pas collectés par pytest : `.claude/` est un
  dossier caché, exclu par `norecursedirs` par défaut. Garder `testpaths = ["tests"]` dans
  `pyproject.toml`.

## Ordre d'usage (rappel de `CLAUDE.md`)

quant-research (cadrage) → setup / backtest / optimize (moteur) → backtest-review + strategy-critique
+ risk-report (audit) → tearsheet-generator (rapport) → position-sizer + drawdown-circuit-breaker
(live) → friend-strategy (source de vérité de la stratégie).

## Mise à jour d'un skill tiers

Recloner le dépôt source en shallow, relire `SKILL.md` et les scripts, refaire le `grep` ci-dessus,
copier, puis réappliquer la note d'adaptation en tête de fichier. Noter la date dans
`docs/DECISIONS.md`.
