---
name: friend-strategy
description: Source de vérité de la stratégie « Liquidity Sweep + VWAP » de l'ami (QQQ 5 min) — où sont les règles, comment les modifier sans casser les invariants, quels tests prouvent chaque règle. À utiliser dès qu'on touche à strategy/strategy.py, config.yaml (strategy, exits, session) ou docs/STRATEGY.md, ou qu'on doit répondre à « que fait exactement la stratégie ? ».
---

# friend-strategy — source de vérité de la stratégie

## Où est la vérité (dans cet ordre)

1. `docs/STRATEGY_SOURCE.pine` : le script Pine v5 de l'ami, **jamais modifié**.
2. `docs/STRATEGY.md` : sa traduction règle par règle, avec les points **À CONFIRMER** et les questions à
   lui poser. En cas de divergence, le Pine fait foi après validation de l'ami.
3. `config.yaml` : les valeurs (`strategy`, `exits`, `execution`, `instrument`). Zéro paramètre en dur.
4. `strategy/strategy.py` : `generate_signals(df, params)`, fonction pure. Elle ne connaît ni VectorBT,
   ni Alpaca, ni le sizing, ni les TP/SL (ce sont des ordres persistants gérés par `backtest/engine.py`
   et `live/broker.py`).
5. `docs/DECISIONS.md` : chaque choix fait à la place de l'ami, daté (symbole QQQ, points d'indice,
   fenêtre 14h–18h en UTC, VWAP ancré 09:30 ET, exécuteur maison).

## Les règles en une table

| Règle | Code | Test |
|---|---|---|
| Sweep bas : `low < prev_low` et `close > prev_low`, prev_low = min des 10 bougies **précédentes** | `generate_signals`, `compute_indicators` | `test_long_sweep_low_wick_below_close_above`, `test_long_rejected_if_close_below_prev_low`, `test_current_bar_is_not_in_prev_levels` |
| Sweep haut symétrique | idem | `test_short_sweep_high_symmetric`, `test_short_rejected_if_close_above_prev_high` |
| Filtre VWAP de séance sur `close`, remis à zéro chaque séance | `session_vwap` | `test_long_requires_close_above_vwap`, `test_vwap_resets_each_session`, `test_vwap_uses_close_weighted_by_volume` |
| Filtre EMA 50 | `ema` | `test_long_requires_close_above_ema` |
| Fenêtre 14h ≤ heure < 18h (UTC), entrées seulement | `in_session` | `test_session_filter_boundaries`, `test_session_filter_applies_to_short_too` |
| Signal inverse = sortie + retournement, pas de renfort | `exits`, `short_exits` ; `live.engine.decide` | `test_reverse_signal_is_an_exit`, `test_opposite_signal_reverses_position`, `test_same_side_signal_is_ignored_no_pyramiding`, `test_decision_rules` |
| Exécution à l'ouverture de t+1 | `backtest/engine.py` | `test_entry_fills_at_next_open_with_slippage` |
| TP 30 / SL 15 points d'indice, actifs dès la bougie d'entrée, SL d'abord, gap à l'ouverture | `backtest/engine.py`, `live/run.py::_open` | `test_tp_can_trigger_on_entry_bar`, `test_sl_first_when_both_hit_in_same_bar`, `test_gap_through_sl_fills_at_open`, `test_short_*` |
| Pas de look-ahead | tout `strategy.py` | `tests/test_no_lookahead.py` |
| Parité batch / live | `live/engine.py` | `tests/test_parity.py` |

## Comment modifier une règle (procédure)

1. Écrire la nouvelle règle dans `docs/STRATEGY.md` et une ligne datée dans `docs/DECISIONS.md` (qui l'a
   décidée : l'ami, ou un choix provisoire).
2. Écrire ou modifier **d'abord** le test correspondant dans `tests/test_strategy_rules.py` (mini-série de
   bougies construite à la main), le voir échouer.
3. Modifier `strategy/strategy.py` (ou `config.yaml` si c'est une valeur). Aucune valeur en dur.
4. `make test` : les 49 tests doivent passer, y compris look-ahead et parité. **Ne jamais** modifier
   `strategy.py` pour faire passer un test de parité : c'est le test qui a raison.
5. Relancer `python -m backtest.run --period smoke` et vérifier le tableau de bord. Un essai de plus
   dans le compteur de `docs/AUDIT.md` si c'est une variante de paramètres.

## Ce que la stratégie ne fait pas (à ne pas ajouter sans décision écrite)

Pas de sortie en fin de séance, pas de trailing stop, pas de break-even, pas de filtre de nouvelles ou de
calendrier, pas de paramètres différents entre long et short, pas de volume comme filtre direct.
