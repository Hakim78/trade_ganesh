# Liquidity Sweep + VWAP — backtest et paper trading sur QQQ

Ce projet vérifie une stratégie d'entrée (« balayage de liquidité » + VWAP + EMA 50, bougies de 5 minutes)
sur le Nasdaq-100 via l'ETF **QQQ** :

1. **en batch** sur l'historique (backtest), avec frais et slippage ;
2. **en temps réel** sur un compte **paper** (fictif) Alpaca, avec un coupe-circuit de perte journalière.

> **Paper trading uniquement.** Aucun ordre réel n'est jamais passé : l'adresse utilisée est
> `paper-api.alpaca.markets`, un test automatique refuse toute autre valeur. **Un backtest mesure le passé,
> il ne prédit pas le futur.**

## Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, macOS ou Linux).
- Pour le temps réel et pour l'historique complet : un **compte Alpaca paper gratuit**
  (https://alpaca.markets → Paper Trading → API Keys). Sans compte, le backtest tourne quand même sur les
  60 derniers jours (données Yahoo Finance).

## Installation

```bash
git clone https://github.com/Hakim78/trade_ganesh.git
cd trade_ganesh
cp .env.example .env        # puis coller les deux clés Alpaca paper dans .env (facultatif pour le backtest 60 j)
```

## Les trois commandes

| Commande | Ce qu'elle fait | Résultat |
|---|---|---|
| `docker compose run backtest` | Backtest des 60 derniers jours (fenêtre de mise au point) | fichiers dans `outputs/` |
| `docker compose up dashboard` | Tableau de bord | http://localhost:8080 |
| `docker compose up live` | Paper trading en continu (clés Alpaca dans `.env`) | `outputs/live/`, visible dans le tableau de bord |

Backtest sur l'historique complet (clés Alpaca dans `.env`) :

```bash
PERIOD=in_sample docker compose run backtest        # 2018 → 2024 : la période de travail
PERIOD=out_of_sample docker compose run backtest    # 2025 → mi-2026 : UNE SEULE FOIS, à la fin (voir docs/HYPOTHESIS.md)
```

Sous Windows PowerShell : `$env:PERIOD="in_sample"; docker compose run backtest`.

## Lire les résultats

Le tableau de bord (http://localhost:8080) montre, de haut en bas :

- **les tuiles** : rendement net, profit factor, taux de réussite, nombre de trades, drawdown, Sharpe… tous
  **nets de frais et de slippage** ;
- **le graphique 5 minutes** : chandeliers, VWAP de séance (bleu), EMA 50 (orange), entrées (▲ L long,
  ▼ S short) et sorties (● vert = gain, rouge = perte). Les heures sont celles de New York ;
- **la courbe de capital** et le **drawdown** ;
- **le tableau par année** et les **règles** appliquées ;
- **la liste des trades** ;
- **le panneau paper trading** quand `docker compose up live` tourne : capital, position, dernier signal,
  état du coupe-circuit.

Les mêmes chiffres sont dans `outputs/` : `trades.csv` (un trade par ligne), `metrics.json`, `equity.png`,
`tearsheet.html` (rapport complet QuantStats, à ouvrir dans un navigateur), `dashboard.json`.

### Ce que veulent dire les chiffres

- **Taux de réussite (win rate)** : part des trades gagnants. Avec un objectif de gain deux fois plus grand
  que le stop (30 pts contre 15), il suffit de gagner plus d'une fois sur trois pour être à l'équilibre
  **avant** frais.
- **Profit factor** : total des gains ÷ total des pertes. Au-dessus de 1, la stratégie gagne ; au-dessus de
  1,3 elle commence à être confortable.
- **Drawdown max** : la pire baisse du capital depuis un sommet. C'est ce qu'il faut être prêt à encaisser.
- **Sharpe** : rendement rapporté au risque, calculé sur les rendements journaliers. Négatif = perdant.
- **Gain moyen par trade (expectancy)** : ce que rapporte un trade en moyenne, frais compris.

## La stratégie en deux phrases

Sur une bougie de 5 minutes, si le prix passe sous le plus bas des 10 bougies précédentes puis **clôture
au-dessus**, que la clôture est au-dessus du VWAP de la séance et de l'EMA 50, et qu'on est dans la fenêtre
horaire, on achète à l'ouverture de la bougie suivante avec un objectif de +30 points d'indice et un stop à
−15. Symétrique pour la vente à découvert. Détail règle par règle : [docs/STRATEGY.md](docs/STRATEGY.md) ;
script d'origine : [docs/STRATEGY_SOURCE.pine](docs/STRATEGY_SOURCE.pine).

Points encore à confirmer avec l'auteur de la stratégie (ils sont listés en fin de `docs/STRATEGY.md`) :
le symbole exact qu'il trade, le fuseau de sa fenêtre 14h–18h, et si « 30 points » sont bien des points
d'indice. Les choix faits en attendant sont datés dans [docs/DECISIONS.md](docs/DECISIONS.md) et modifiables
dans `config.yaml`.

## Où en est-on

- La chaîne complète fonctionne : données → signaux → exécution → rapports → tableau de bord → paper trading.
- Sur la fenêtre de mise au point (60 jours, **hors étude**), la stratégie perd légèrement : stop de
  15 points ≈ 0,05 % du prix, plus petit que l'amplitude moyenne d'une bougie de 5 minutes de QQQ (≈ 0,13 %),
  donc la plupart des trades se terminent sur le stop dans la bougie d'entrée. Voir
  [docs/AUDIT.md](docs/AUDIT.md).
- L'étude proprement dite (2018 → 2024 puis 2025 → 2026) demande l'historique Alpaca : mettre les clés dans
  `.env` et lancer `PERIOD=in_sample docker compose run backtest`.

## Sans Docker (développeurs)

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/Scripts/python.exe -e ".[dev]"   # Windows
.venv/Scripts/python.exe -m pytest                     # 49 tests : règles, look-ahead, exécution, parité, paper-only
.venv/Scripts/python.exe -m backtest.run --period smoke
cd frontend && npm install && npm run dev              # http://localhost:5173, lit ../outputs
.venv/Scripts/python.exe -m live.run                   # paper trading
git config core.hooksPath .claude/hooks                # hook pre-commit anti-biais
```

`make test`, `make smoke`, `make live`, `make dashboard-build` font la même chose si `make` est installé.

## Structure

```
config.yaml            tous les paramètres (instrument, fenêtre horaire, TP/SL, coûts, split, live)
strategy/strategy.py   la stratégie, fonction pure : bougies → signaux (aucun accès réseau)
backtest/              data.py (yfinance / Alpaca), engine.py (exécution), report.py, run.py
live/                  feed.py (bougies 5 min), engine.py (décision), broker.py (Alpaca paper), run.py
frontend/              tableau de bord React (Vite, lightweight-charts)
tests/                 invariants : règles, look-ahead, exécution, parité batch/live, paper-only
docs/                  STRATEGY.md, HYPOTHESIS.md, AUDIT.md, DECISIONS.md
.claude/               skills et hook git du projet (voir .claude/skills/README.md)
```
