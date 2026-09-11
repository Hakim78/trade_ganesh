# Setup Claude Code — Backtest & Live NASDAQ / S&P

Ce document contient tout ce qu'il faut pour lancer le projet dans Claude Code :

1. Ce que dit la doc officielle (et ce qu'on en retient)
2. L'analyse du besoin en skills, besoin par besoin
3. Le `CLAUDE.md` du projet
4. **Prompt 1** — installation des skills et lecture de la doc
5. **Prompt 2** — création du projet
6. La checklist d'exécution

---

## 1. Doc officielle — les 3 pages à respecter

| Sujet | URL | Ce qu'on retient |
|---|---|---|
| Skills | https://code.claude.com/docs/en/skills | Un skill = `SKILL.md` avec frontmatter `name` + `description`. Emplacement projet : `.claude/skills/<nom>/SKILL.md` (à committer, l'ami l'aura). Emplacement perso : `~/.claude/skills/`. Les skills de plugins sont préfixés `/plugin:skill`. |
| CLAUDE.md | https://code.claude.com/docs/en/memory | `./CLAUDE.md` = mémoire projet, lue à chaque session. Faits et règles courtes, pas de procédures (une procédure = un skill). `@chemin/fichier` importe un autre fichier. `/init` génère un squelette. |
| Skills Anthropic | https://github.com/anthropics/skills | Marketplace officiel : `/plugin marketplace add anthropics/skills` puis `/plugin install example-skills@anthropic-agent-skills`. Contient `skill-creator`, l'outil officiel pour écrire ses propres skills. |

Règle d'or de la doc : **CLAUDE.md = quoi et pourquoi, skills = comment.**

---

## 2. Analyse du besoin en skills

| # | Besoin du projet | Skill(s) | Source | Pourquoi celui-là |
|---|---|---|---|---|
| 1 | Cadrer un backtest honnête : hypothèse écrite avant le code, split in-sample / out-of-sample, walk-forward, correction du biais de sélection (deflated Sharpe) | `quant-research` | https://github.com/Jimmy7892/quant-research-skill | Le seul qui impose des *gates* (on n'avance pas sans coûts, sans OOS, sans assez de trades). Livré avec scripts `selection_bias.py`, `sizing.py`, `effective_n.py`. |
| 2 | Moteur de backtest vectorisé : setup env, backtest rapide, optimisation de paramètres | `setup`, `backtest`, `optimize` (+ les autres du repo si utiles) | https://github.com/marketcalls/vectorbt-backtesting-skills | Skills prêts pour VectorBT, le moteur retenu. Structure `.claude/skills/` déjà conforme à la doc. |
| 3 | Audit anti-biais avant chaque livraison : look-ahead, survivorship, overfitting, réalisme des coûts, slippage, dépendance au régime | `backtest-review`, `strategy-critique`, `risk-report`, `data-scrub` + hook `pre-commit-backtest-check.sh` | https://github.com/shakeebshaan/claude-code-quant-skills | Checklist d'audit structurée + hook git qui bloque un commit de backtest douteux. |
| 4 | Rapport de performance lisible par l'ami (tearsheet QuantStats : equity, drawdown, mensuel) | `tearsheet-generator` | https://github.com/HyperFrequency/skills | Ne prendre **que** ce skill : le reste du repo est orienté crypto / NautilusTrader. |
| 5 | Live paper trading + garde-fous risque | `backtest-expert`, `position-sizer`, `drawdown-circuit-breaker`, et les skills marqués *Alpaca* dans `skills-index.yaml` | https://github.com/tradermonty/claude-trading-skills | Repo actions US, intégration Alpaca native, circuit-breaker de drawdown pour le live. |
| 6 | Encoder la stratégie de l'ami comme skill projet réutilisable (règles, invariants, tests) | `friend-strategy` **à créer** avec `skill-creator` | https://github.com/anthropics/skills (plugin `example-skills`) | Skill officiel Anthropic pour écrire un skill propre. Le skill maison devient la source de vérité de la stratégie. |

**Pas de skill nécessaire pour** : Docker, docker-compose, pytest, git, GitHub Actions — Claude Code les gère nativement.

**Sécurité, non négociable** : un skill tiers est du texte et parfois des scripts que l'agent va exécuter. Avant copie, Claude Code doit lire chaque `SKILL.md` et chaque script, et rejeter tout ce qui appelle un réseau, lit des variables d'environnement, ou sort du dossier projet. Aucune clé API dans un skill.

---

## 3. `CLAUDE.md` du projet

À placer à la racine du repo. Les règles de la stratégie vivent dans `docs/STRATEGY.md`, importé par `@`.

```markdown
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
```

### `docs/STRATEGY.md` (à remplir avec les règles de l'ami)

```markdown
# Stratégie — règles exactes

Instrument : [QQQ / SPY / NQ / ES]
Timeframe : [daily / 1h / 15m / 5m / 1m]
Session : [RTH 09:30–16:00 ET / ETH]

## Entrée long
- Condition 1 : …
- Condition 2 : …
- Déclencheur : [clôture de bougie / touche de niveau]

## Entrée short (si applicable)
- …

## Sortie
- Stop : [ATR × n / niveau fixe / % ]
- Take-profit : …
- Sortie temporelle : [fin de session / n bougies]

## Sizing
- [% du capital / risque fixe par trade / nombre de contrats]

## Filtres
- [pas de trade avant 10:00 ET, pas de trade jour de FOMC, etc.]

## Ce que la stratégie NE fait PAS
- …
```

---

## 4. Prompt 1 — Installation des skills et lecture de la doc

> À coller dans Claude Code, lancé dans un dossier vide `trading-backtest-live/` déjà initialisé avec `git init`.

```
Tu vas préparer l'environnement Claude Code de ce projet avant tout développement.
Ne crée aucun code applicatif dans cette session. Uniquement : doc, skills, CLAUDE.md.

## Étape 1 — Doc officielle
Lis ces trois pages avec WebFetch et résume-moi en 10 lignes maximum les règles que tu vas appliquer :
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/memory
- https://github.com/anthropics/skills (README)

## Étape 2 — Skill officiel Anthropic
Indique-moi la commande que je dois taper moi-même dans Claude Code pour installer le marketplace officiel et le plugin qui contient skill-creator (tu ne peux pas taper les commandes slash à ma place). Attends que je confirme que c'est fait.

## Étape 3 — Skills métier trading
Clone en shallow ces repos dans /tmp/skills-src/ :
- https://github.com/Jimmy7892/quant-research-skill
- https://github.com/marketcalls/vectorbt-backtesting-skills
- https://github.com/shakeebshaan/claude-code-quant-skills
- https://github.com/HyperFrequency/skills
- https://github.com/tradermonty/claude-trading-skills

Pour chaque repo : localise tous les SKILL.md (find), lis-les, et sélectionne UNIQUEMENT les skills qui répondent à ces besoins :
1. cadrage honnête du backtest (OOS, walk-forward, biais de sélection) → quant-research
2. moteur VectorBT (setup, backtest, optimize)
3. audit anti-biais (backtest-review, strategy-critique, risk-report, data-scrub) + le hook pre-commit
4. tearsheet de performance (tearsheet-generator) — rien d'autre du repo HyperFrequency
5. live paper Alpaca + risque (backtest-expert, position-sizer, drawdown-circuit-breaker, skills Alpaca listés dans skills-index.yaml)

Revue de sécurité obligatoire avant copie : lis chaque script bundlé. Rejette tout skill dont un script fait un appel réseau non documenté, lit des variables d'environnement, ou écrit hors du dossier projet. Dis-moi ce que tu as rejeté et pourquoi.

Copie les skills retenus dans .claude/skills/<nom>/ (emplacement projet, doc officielle) en conservant SKILL.md, references/, scripts/, assets/. Vérifie que chaque SKILL.md a un frontmatter valide avec name et description ; corrige le name s'il entre en collision avec un autre skill. Installe le hook pre-commit dans .claude/hooks/ et documente-le.

## Étape 4 — CLAUDE.md
Crée CLAUDE.md et docs/STRATEGY.md avec le contenu que je te fournis ci-dessous. Ne le reformule pas.
[COLLER ICI le CLAUDE.md et le docs/STRATEGY.md de la section 3]

## Étape 5 — Livrable de cette session
Donne-moi :
- la liste des skills installés dans .claude/skills/ avec leur description en une ligne,
- les skills rejetés et la raison,
- un .gitignore (venv, .env, outputs/, data/, __pycache__),
- un premier commit "chore: skills + CLAUDE.md".
Puis arrête-toi. Je vérifierai que les skills apparaissent dans le menu / avant de te donner le prompt de développement.
```

---

## 5. Prompt 2 — Création du projet

> À coller dans une **nouvelle session** Claude Code, une fois `docs/STRATEGY.md` rempli avec les règles de l'ami. Lance en mode plan (`Shift+Tab` deux fois) pour valider le plan avant l'exécution.

```
Lis CLAUDE.md et docs/STRATEGY.md. Le projet doit être livré à un trader non-développeur via GitHub + Docker : il clone, remplit .env, tape deux commandes.

Utilise les skills installés dans cet ordre. À chaque phase, dis-moi quel skill tu invoques et attends mon OK avant la phase suivante.

## Phase 0 — Cadrage (skill quant-research)
Écris docs/HYPOTHESIS.md : hypothèse testable, ce qui la falsifierait, split in-sample / out-of-sample (dates figées), nombre minimum de trades pour conclure, critère de décision fixé à l'avance. Reporte le split dans config.yaml.

## Phase 1 — Squelette + stratégie pure
- Arborescence de CLAUDE.md, pyproject.toml, Makefile, config.yaml, .env.example.
- strategy/strategy.py : traduis docs/STRATEGY.md en generate_signals(df). Fonction pure, aucun I/O.
- tests/test_no_lookahead.py : pour un t aléatoire, tronquer df à t et vérifier que le signal en t est identique à celui obtenu sur le df complet.
- tests/test_strategy_rules.py : un test par règle de STRATEGY.md, avec une mini-série de bougies construite à la main.
Fais tourner make test. Vert avant de continuer.

## Phase 2 — Backtest (skills setup, backtest, optimize)
- backtest/data.py : téléchargement historique (yfinance en daily/1h ; si le timeframe de STRATEGY.md est < 1h, arrête-toi et demande-moi quelle source payante utiliser).
- backtest/run.py : VectorBT, frais + slippage depuis config.yaml, sorties dans outputs/ (trades.csv, metrics.json, equity.png).
- Lance le backtest sur l'in-sample uniquement. Ne touche pas à l'OOS.
- Si optimisation de paramètres : uniquement in-sample, et rapporte la surface de paramètres, pas l'argmax (règle du skill quant-research).

## Phase 3 — Audit (skills backtest-review, strategy-critique, risk-report)
Passe les trois audits sur le backtest. Écris docs/AUDIT.md avec chaque point de la checklist : OK / KO / non applicable, et corrige les KO avant de continuer. Ensuite seulement, exécute une fois sur l'OOS et compare aux critères de docs/HYPOTHESIS.md. Verdict écrit dans docs/AUDIT.md.

## Phase 4 — Rapport (skill tearsheet-generator)
outputs/tearsheet.html via QuantStats. Un README section "Lire les résultats" en français simple pour un trader.

## Phase 5 — Live paper (skills position-sizer, drawdown-circuit-breaker + skills Alpaca)
- live/feed.py : websocket Alpaca (données), reconstruction des bougies au timeframe de config.yaml. Signal évalué uniquement à la clôture d'une bougie.
- live/run.py : appelle generate_signals, logue chaque signal dans outputs/live/signals.csv, passe l'ordre paper via alpaca-py.
- Circuit-breaker : arrêt automatique si drawdown journalier > seuil de config.yaml.
- tests/test_parity.py : rejoue la même série de bougies dans backtest et live, signaux strictement identiques.
- tests/test_paper_only.py : l'URL Alpaca contient "paper-api", sinon le test échoue.

## Phase 6 — Livraison
- Dockerfile (python:3.12-slim), docker-compose.yml avec services backtest (one-shot) et live (long-running), volumes outputs/ et data/.
- README.md pour l'ami : prérequis (Docker, compte Alpaca paper gratuit), 3 commandes, où lire les résultats, ce que veulent dire win rate / drawdown / profit factor, et l'avertissement "paper trading uniquement, un backtest ne prédit pas le futur".
- GitHub Actions : make test à chaque push.
- Commit par phase, messages conventionnels.

Contraintes globales : respecte les invariants de CLAUDE.md sans exception. Si une règle de STRATEGY.md est ambiguë, arrête-toi et pose-moi la question au lieu d'interpréter.
```

---

## 6. Checklist d'exécution

1. `mkdir trading-backtest-live && cd trading-backtest-live && git init && claude`
2. Coller **Prompt 1**. Taper soi-même les commandes slash qu'il indique (`/plugin marketplace add anthropics/skills`, puis `/plugin install example-skills@anthropic-agent-skills`), puis `/reload-plugins` si demandé.
3. Vérifier dans le menu `/` que les skills apparaissent. Lire `.claude/skills/*/SKILL.md` soi-même une fois.
4. Remplir `docs/STRATEGY.md` avec les règles de l'ami. Aucune règle floue.
5. Nouvelle session, mode plan, coller **Prompt 2**. Valider le plan, puis phase par phase.
6. Pousser sur GitHub (repo privé), inviter l'ami, lui envoyer le README.

Point d'attention : le plan gratuit Alpaca donne le flux IEX (suffisant pour du paper sur QQQ/SPY). Pour les futures NQ/ES, Alpaca ne suffit pas — prévoir IBKR paper et adapter la Phase 5.
