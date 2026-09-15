# Stratégie — règles exactes

Source de vérité : le script Pine v5 de l'ami, « Liquidity Sweep + VWAP (Optimized) », conservé tel quel
dans `docs/STRATEGY_SOURCE.pine`. Ce fichier en est la traduction règle par règle. Toute divergence se
tranche en faveur du Pine, après validation de l'ami.

Les points marqués **À CONFIRMER** ne sont pas déductibles du script. Ils bloquent le code (Prompt 2).
Confirmé le 2026-09-15 par Hakim : timeframe 5 minutes, TP/SL exprimés en ticks. Le symbole exact
n'est pas connu d'Hakim : voir les questions à poser à l'ami en fin de fichier.

Instrument : **À CONFIRMER**. Le doc dit NASDAQ / S&P ; le script ne fixe pas le symbole. Candidats : NQ (CME), ES (CME), QQQ / SPY (ETF), CFD NAS100 / US100.
Timeframe : **5 minutes** (confirmé).
Session : entrées autorisées uniquement si `14 <= hour < 18`, où `hour` est l'heure du **fuseau de la bourse du symbole** (sémantique Pine v5 de la variable `hour`, indépendante du fuseau d'affichage du graphique). Fenêtre en heure de New York **À CONFIRMER**, car elle dépend du symbole : CME (Chicago) → 15h–19h ET ; NYSE/NASDAQ (New York) → 14h–18h ET ; CFD coté en UTC → 10h–14h ET en été, 9h–13h en hiver.

## Paramètres (à reporter dans `config.yaml`)

| Nom | Valeur | Rôle |
|---|---|---|
| `timeframe` | 5 min | Bougies de 5 minutes (confirmé) |
| `lookback` | 10 | Fenêtre des plus hauts / plus bas précédents (10 bougies = 50 minutes) |
| `tp_ticks` | 30 | Take-profit en **ticks** (confirmé : sémantique Pine de `strategy.exit(profit=)`). Valeur en points / dollars **À CONFIRMER** via la taille du tick du symbole |
| `sl_ticks` | 15 | Stop-loss en ticks, même remarque |
| `tick_size` | **À CONFIRMER** | 0,25 pt pour NQ / ES ; 0,01 $ pour QQQ / SPY ; selon broker pour un CFD |
| `ema_len` | 50 | Période de l'EMA de tendance (50 bougies = 4 h 10) |
| `sizing` | 10 % de l'equity | `default_qty_type = percent_of_equity`, `default_qty_value = 10` |

## Indicateurs (calculés sur bougies clôturées uniquement)

- `vwap[t]` : VWAP de session sur `close` : `ta.vwap(close)` = somme(close × volume) / somme(volume) depuis le début de la session courante, remis à zéro à chaque nouvelle session du symbole. Le prix pondéré est `close`, pas `hlc3`. Ancre de session **À CONFIRMER** (dépend du symbole : 09:30 ET pour un ETF, 17:00 CT pour NQ/ES, journée broker pour un CFD).
- `ema50[t]` : EMA(close, 50).
- `prev_high[t]` : `ta.highest(high, 10)[1]` = maximum des `high` des 10 bougies **précédentes** (t-10 à t-1), bougie courante exclue.
- `prev_low[t]` : `ta.lowest(low, 10)[1]` = minimum des `low` des 10 bougies précédentes (t-10 à t-1).

## Entrée long (« BUY »)

Toutes les conditions évaluées sur la bougie t clôturée :
1. Sweep des plus bas : `low[t] < prev_low[t]` **et** `close[t] > prev_low[t]` (mèche sous le plus bas des 10 bougies précédentes, clôture au-dessus).
2. `close[t] > vwap[t]`.
3. Tendance haussière : `close[t] > ema50[t]`.
4. Session : heure de la bougie t dans [14h, 18h) au fuseau de la bourse.

Déclencheur : clôture de la bougie t. Ordre au marché exécuté à l'**ouverture de la bougie t+1** (comportement Pine par défaut, `process_orders_on_close = false`).

## Entrée short (« SELL »)

1. Sweep des plus hauts : `high[t] > prev_high[t]` **et** `close[t] < prev_high[t]`.
2. `close[t] < vwap[t]`.
3. Tendance baissière : `close[t] < ema50[t]`.
4. Même filtre horaire.

Déclencheur : idem, ouverture de t+1.

## Sortie

- Take-profit : prix d'entrée + 30 ticks (long) / prix d'entrée − 30 ticks (short).
- Stop : prix d'entrée − 15 ticks (long) / prix d'entrée + 15 ticks (short). Ratio gain/risque 2:1.
- Les deux ordres sont un OCO **persistant** : actifs hors session, la nuit et le week-end (si l'instrument cote) jusqu'à exécution. Le filtre horaire ne s'applique pas aux sorties.
- Sortie temporelle : **aucune**. Pas de sortie en fin de session.
- TP et SL touchés dans la même bougie : le Pine ne le tranche pas explicitement (TradingView suppose un parcours open → extrémité la plus proche → autre extrémité). Le backtest prendra l'hypothèse **pessimiste, SL d'abord**. **À CONFIRMER** que c'est acceptable.
- Retournement : `pyramiding = 0` (défaut) et un `strategy.entry` en sens inverse **ferme la position en cours et ouvre l'inverse** au même instant. Un signal SELL pendant un long = sortie du long au marché à l'ouverture de t+1 + entrée short. Un signal BUY pendant un long est ignoré (pas de renfort).

## Sizing

- 10 % de l'equity courante par entrée : quantité = 10 % × equity / prix d'entrée, arrondie à l'unité inférieure (actions entières).
- Pour des futures : **À CONFIRMER**. 10 % de l'equity en notionnel ne donne aucun nombre entier de contrats NQ (1 contrat ≈ 20 $ × indice). Alternative probable : 1 micro-contrat (MNQ / MES) par signal.

## Filtres

- Filtre horaire uniquement, sur les **entrées** : 14h–18h au fuseau de la bourse.
- Aucun filtre de jour (FOMC, expirations, jours fériés), aucun filtre de volatilité ou de volume.

## Ce que la stratégie NE fait PAS

- Pas de sortie en fin de session, pas de trailing stop, pas de mise à break-even.
- Pas de renfort de position (`pyramiding = 0`).
- Pas de filtre de nouvelles ni de calendrier.
- Pas de paramètres différents entre long et short : mêmes TP / SL des deux côtés.
- Pas de volume comme filtre direct (il n'intervient que dans le VWAP).
- Ne compare jamais la bougie courante à elle-même : `prev_high` / `prev_low` excluent la bougie t.

## Points à confirmer avant tout code (bloquants)

1. Symbole TradingView exact. Il fixe le fuseau du filtre horaire, la taille du tick (donc la valeur réelle de 30 / 15 ticks), l'ancre du VWAP et la source de données.
2. Source de données historiques 5 minutes (yfinance ne couvre pas au-delà de 60 jours). Hakim mentionne une solution gratuite récente, à nommer.
3. Sizing pour des futures.
4. Hypothèse « SL d'abord » quand TP et SL sont dans la même bougie.

## Questions à poser à l'ami (à transmettre telles quelles)

1. **Quel symbole exactement ?** Le nom affiché en haut à gauche du graphique TradingView (par exemple `NQ1!`, `MNQ1!`, `NAS100`, `US100`, `QQQ`) et la bourse ou le broker indiqué à côté (CME, OANDA, Pepperstone…).
2. **Chez quel broker trades-tu réellement cette stratégie**, et sur quel produit (futures, micro-futures, CFD, ETF) ?
3. **Sur ton graphique, quel fuseau horaire est réglé** (en bas à droite, à côté de l'heure) ? Et la fenêtre 14h–18h du script, c'est censé être quelle heure de New York pour toi ?
4. **Dans l'onglet « Strategy Tester » → « Liste des trades »**, une sortie « TP/SL BUY » gagnante fait combien en points ou en dollars par contrat / action ? (Ça donne la taille du tick.)
5. **Combien de contrats ou d'actions passes-tu par signal**, et avec quel capital ? Le script dit « 10 % du capital », c'est ce que tu fais vraiment ?
6. **Peux-tu exporter la liste des trades du Strategy Tester** (bouton d'export en CSV) sur une période d'au moins 3 mois, avec les réglages exacts que tu utilises ? Elle servira de référence pour vérifier que notre backtest produit les mêmes trades que TradingView.
