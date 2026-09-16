# Audit du backtest (Phase 3)

Skills appliqués : `backtest-review`, `strategy-critique`, `risk-report`, `backtest-expert`.
Objet : la **chaîne** (données → signaux → exécution → rapport) validée sur la fenêtre de mise au point
(QQQ 5 min, 2026-07-20 → 2026-09-16, yfinance). **Hors étude** : aucun réglage, aucune conclusion sur l'edge.
L'étude in-sample (2018 → 2024) n'a pas commencé : elle attend l'historique Alpaca.

## Essais (compteur, docs/HYPOTHESIS.md)

| # | Date | Période | Paramètres | Motif |
|---|---|---|---|---|
| 1 | 2026-09-16 | mise au point 60 j | script de l'ami, `index_reference = 24000` | première exécution de la chaîne |
| 2 | 2026-09-16 | mise au point 60 j | idem, `index_reference = 29000` | correction du niveau d'indice réel (29 159), pas une optimisation |

In-sample consommé : 0 fois. Out-of-sample consommé : 0 fois.

## Checklist `backtest-review`

| Point | Verdict | Constat |
|---|---|---|
| 1. Look-ahead | **OK** | Indicateurs causaux (rolling + shift, cumsum par séance, EMA récursive). `tests/test_no_lookahead.py` : troncature à t et perturbation du futur. Exécution à l'ouverture de t+1. |
| 2. Survivorship | **N/A** | Un seul instrument, un ETF indiciel toujours coté. |
| 3. Overfitting | **OK (pour l'instant)** | 3 paramètres (`lookback`, `ema_len`, TP/SL) fixés par le script de l'ami, aucune recherche faite. La surface de paramètres viendra en in-sample (skill `quant-research`, région à 1 écart-type, pas d'argmax). |
| 4. Coûts | **OK** | 0,01 % de frais + 0,01 % de slippage par côté, lus dans `config.yaml` ; `tests/test_execution.py::test_execution_params_from_config` refuse des coûts nuls. Sur 39 trades : 75 $ de coûts pour 100 000 $ de capital. |
| 5. Slippage | **OK / à surveiller** | Modélisé en % contre nous à chaque exécution, y compris sur les stops. Avec un TP de 0,10 %, les coûts aller-retour (0,04 %) mangent 40 % de l'objectif : sensibilité aux coûts à tester en in-sample (axe frais 0 → 0,05 %). |
| 6. Régimes | **KO (non testable ici)** | 60 jours = un seul régime. À faire en in-sample : 2018 Q4, 2020, 2022, 2023-24 séparément (tableau par année du tableau de bord). |
| 7. Sizing / risque | **OK** | 10 % de l'equity, actions entières ; risque par trade ≈ 0,005 % du capital, aucun levier. |
| 8. Exécution | **OK** | Ordre à l'ouverture de t+1 ; TP/SL actifs dès la bougie d'entrée, SL prioritaire si les deux sont touchés, gap exécuté à l'ouverture ; retournement sur signal inverse. Couvert par 13 tests. **Écart connu** : VectorBT `from_signals` n'active pas les stops sur la bougie d'entrée, d'où l'exécuteur maison (`docs/DECISIONS.md`). |
| 9. Parité batch / live | **OK** | `tests/test_parity.py` : mêmes signaux bougie par bougie, avec reconstruction 1 min → 5 min. |
| 10. Données | **OK / à refaire** | yfinance : bougies de séance, index New York, sans doublon (`backtest/data.py::normalize_bars`). `data-scrub` complet à passer sur l'historique Alpaca (gaps, jours fériés, volume IEX partiel). |

Verdict `backtest-review` sur la chaîne : **SHIP** (la mécanique est honnête). Verdict sur la stratégie :
**pas encore évaluable**.

## `backtest-expert` — score sur la fenêtre de mise au point

`python .claude/skills/backtest-expert/scripts/evaluate_backtest.py --total-trades 39 --win-rate 33.3
--avg-win-pct 0.069 --avg-loss-pct 0.079 --max-drawdown-pct 0.14 --years-tested 0 --num-parameters 3
--slippage-tested` → verdict attendu **Abandon** (échantillon < 30 ans-trades, < 5 ans), ce qui est la
lecture correcte d'une fenêtre de mise au point : il n'y a rien à conclure.

## `strategy-critique` — trois questions à l'auteur avant d'aller plus loin

1. **Le stop est plus petit que le bruit.** 15 points d'indice = 0,05 % du prix ; l'amplitude moyenne
   d'une bougie de 5 minutes de QQQ sur la fenêtre est de 0,13 %. Résultat observé : durée moyenne
   1,1 bougie, 26 stops pour 13 objectifs. Sur quel instrument et avec quelle taille de tick « 30 / 15 »
   ont-ils été mesurés ? (Question 4 de `docs/STRATEGY.md`.)
2. **Qui est de l'autre côté ?** Un sweep de 10 bougies (50 minutes) est un niveau très proche ; les stops
   chassés sont ceux des scalpeurs, pas d'une clientèle plus lente. L'edge, s'il existe, est de quelques
   ticks et vit ou meurt avec les coûts.
3. **Pourquoi 14h–18h ?** Si c'est UTC, c'est la matinée de New York (10h–14h l'été) ; si c'est l'heure
   d'un autre fuseau, la stratégie testée ici n'est pas la sienne.

Risque de la stratégie telle que codée : **MEDIUM** en paper (petites tailles, stops serrés, pas de levier),
**HIGH** en réel sans réponse aux trois questions.

## `risk-report` — fenêtre de mise au point (pour mémoire, pas pour décision)

| Métrique | Valeur |
|---|---|
| Rendement net | −0,11 % |
| Profit factor | 0,46 |
| Taux de réussite | 33,3 % (13 / 39) |
| Drawdown max | −0,14 % |
| Sharpe (journalier, annualisé) | −5,7 |
| Durée moyenne d'un trade | 1,1 bougie |
| Coûts | 75 $ |

## Prochaine étape

1. Clés Alpaca paper dans `.env` → `PERIOD=in_sample docker compose run backtest` (2018 → 2024).
2. `data-scrub` sur l'historique téléchargé.
3. Surface de paramètres in-sample (`lookback` 5–20, `ema_len` 30–100, TP/SL 20–40 / 10–20, coûts 0 → 0,05 %)
   avec `quant-research/scripts/region_pool.py`, verdict contre `docs/HYPOTHESIS.md`.
4. Seulement ensuite, une exécution out-of-sample, consignée ici.
