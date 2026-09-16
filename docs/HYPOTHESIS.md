# Hypothèse — cadrage avant tout code (Phase 0, skill quant-research)

Écrit le 2026-09-16, **avant** `strategy/strategy.py` et `backtest/run.py`. Rien ici ne se modifie après
avoir regardé l'out-of-sample.

## Mécanisme testé

Sur QQQ en bougies de 5 minutes, pendant la matinée de New York, une mèche qui passe sous le plus bas des
10 bougies précédentes puis clôture au-dessus (« liquidity sweep ») déclenche des stops de vendeurs et des
achats de rattrapage. Si le marché est déjà haussier (clôture au-dessus de l'EMA 50 et du VWAP de session),
ce rebond se prolonge d'au moins 30 points d'indice Nasdaq-100 avant de reculer de 15 points. Symétrique
pour les shorts. Qui est de l'autre côté : les stops des traders de cassure et les market makers qui
rétablissent le prix après le balayage.

## Ce qui falsifierait l'hypothèse

- Profit factor net de coûts ≤ 1,0 sur l'in-sample : pas d'edge, on arrête.
- Un edge qui disparaît quand les coûts passent de 0,02 % à 0,05 % aller-retour : l'edge est plus petit que
  l'incertitude d'exécution, on arrête.
- Un plateau de paramètres (`lookback` 5–20, `ema_len` 30–100, TP/SL 20–40 / 10–20) qui n'existe pas :
  seule une cellule isolée est rentable, c'est du bruit.
- Résultat porté par une seule année ou un seul régime (2020, 2022).

## Split figé (`config.yaml` → `split`)

| Période | Dates | Usage |
|---|---|---|
| In-sample | 2018-01-01 → 2024-12-31 | Tout le travail : surface de paramètres, walk-forward, audit |
| Out-of-sample | 2025-01-01 → 2026-06-30 | **Consommé une seule fois**, après le verdict in-sample |
| Fenêtre de mise au point | 60 derniers jours (yfinance) | Développement du pipeline et du tableau de bord uniquement. Hors étude : aucune conclusion, aucun réglage |

L'in-sample et l'out-of-sample nécessitent l'historique minute Alpaca (clés gratuites dans `.env`). Tant
qu'elles ne sont pas là, seule la fenêtre de mise au point tourne, et elle ne compte pas.

## Taille minimale pour conclure

- Au moins 200 trades in-sample et 100 out-of-sample.
- Au moins 30 observations effectives (rendements **journaliers** de la stratégie, `effective_n.py` du skill
  quant-research), jamais un t-stat sur les trades.
- Toute statistique est reportée avec son erreur standard et le nombre d'essais (compteur ci-dessous).

## Critère de décision fixé à l'avance

La stratégie passe en paper trading si, **sur l'out-of-sample, net de frais et de slippage** :

1. Profit factor ≥ 1,2.
2. Sharpe annualisé sur rendements journaliers ≥ 0,8, et Sharpe déflaté (`selection_bias.py`, N = nombre
   d'essais) > 0.
3. Drawdown maximal ≤ 10 % du capital initial.
4. Dégradation in-sample → out-of-sample < 50 % sur le profit factor.
5. Aucune année négative sur l'in-sample.

Un seul critère manqué = « pas d'edge démontré ». C'est un résultat acceptable et attendu.

## Compteur d'essais

Chaque backtest regardé compte, y compris les variantes de paramètres et les autres symboles. Tenir le
compte dans `docs/AUDIT.md` (section « Essais »). Point de départ : 0.

## Paramètres retenus pour la première mesure (ceux du script de l'ami)

`lookback = 10`, `ema_len = 50`, TP 30 / SL 15 points d'indice, session 14h–18h UTC, sizing 10 % de
l'equity. Aucun paramètre n'est choisi sur l'out-of-sample.
