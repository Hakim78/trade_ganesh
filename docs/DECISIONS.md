# Décisions d'architecture

Une ligne par décision, datée, ajoutée en bas. Règle de `CLAUDE.md` (section Conventions).

- 2026-09-11 — Skills tiers installés dans `.claude/skills/` (emplacement projet, commités) après revue de sécurité de chaque `SKILL.md` et de chaque script ; inventaire, rejets et résultats dans `.claude/skills/README.md`.
- 2026-09-11 — Chaque skill tiers reçoit en tête une note « Adaptation projet » (marché US, yfinance, `config.yaml`, QuantStats) plutôt qu'une réécriture : les mises à jour amont restent faciles à réappliquer.
- 2026-09-11 — Templates exécutables `vectorbt-expert/rules/assets/*.py` retirés (lecture de clés API dans l'environnement, appels OpenAlgo, marché indien) ; seules les fiches Markdown sont conservées.
- 2026-09-11 — Hook git `pre-commit` maison dans `.claude/hooks/` (celui de shakeebshaan/claude-code-quant-skills est cité dans son README mais absent du dépôt) ; activé par `git config core.hooksPath .claude/hooks`, à refaire à chaque clone.
- 2026-09-11 — Aucun skill Alpaca tiers retenu (les trois marqués Alpaca sont des outils discrétionnaires, deux lisent des secrets) : la boucle live paper (Phase 5) sera écrite avec `alpaca-py`, endpoint `paper-api.alpaca.markets` vérifié par `tests/test_paper_only.py`.
- 2026-09-11 — Tearsheet : QuantStats (`outputs/tearsheet.html`), pas OpenStatz ni le générateur privé du skill HyperFrequency.
- 2026-09-11 — Indicateurs implémentés en pandas/numpy dans `strategy/strategy.py` (ni `openalgo.ta`, ni TA-Lib) pour garder la stratégie pure et sans dépendance broker ou marché.
- 2026-09-11 — Sorties des scripts de skills dans `reports/` (gitignored) ; sorties du projet dans `outputs/` (gitignored) ; données brutes dans `data/` (gitignored).
- 2026-09-11 — Dépôt distant : https://github.com/Hakim78/trade_ganesh (branche `main`).
