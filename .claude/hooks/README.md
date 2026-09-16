# Hooks git du projet

Ce dossier contient des **hooks git** (pas des hooks Claude Code : ceux-là se déclarent dans
`.claude/settings.json`). Ils sont versionnés pour que toute personne qui clone le repo ait les mêmes
garde-fous.

## `pre-commit` → `pre-commit-backtest-check.sh`

Exécuté avant chaque commit. Refuse le commit si :

| # | Vérification | Invariant `CLAUDE.md` |
|---|---|---|
| 1 | `.env` (sauf `.env.example`), `data/` ou `outputs/` indexés | 5, « Ne fais jamais » |
| 2 | Clé Alpaca en dur (`ALPACA_*KEY=…`, identifiant `PK…`/`AK…`) ou endpoint live `api.alpaca.markets` (hors `paper-api`) | 5, 6 |
| 3 | Motif de look-ahead dans un `.py` applicatif : `.shift(-n)`, `rolling(center=True)`, `iloc[i+1]` | 1 |
| 4 | Coûts à zéro codés en dur : `fees=0`, `slippage=0`, `commission=0` | 2 |
| 5 | `pytest` échoue (uniquement si un `.py` est indexé ; utilise `.venv` s'il existe, `make` n'est pas requis) | Commandes |

Les vérifications 3 et 4 ignorent `tests/` et `.claude/`. Elles portent sur le **contenu indexé**
(`git show :fichier`), pas sur le fichier de travail.

## Activation (une fois par clone)

```bash
git config core.hooksPath .claude/hooks
```

Sous Windows, git exécute les hooks avec le `sh` de Git for Windows : rien d'autre à installer.
Les fichiers sont marqués exécutables dans l'index (`git update-index --chmod=+x`), donc
utilisables tels quels sous Linux et macOS. Un `make hooks` fera cette commande en Phase 1.

## Contournements

- `SKIP_TESTS=1 git commit …` saute uniquement l'étape 5.
- `git commit --no-verify` saute tout. À réserver aux commits de documentation, en le disant dans
  le message de commit.

## Test rapide du hook

```bash
bash -n .claude/hooks/pre-commit-backtest-check.sh   # syntaxe
# fausse clé PK + 20 lettres, construite à l'exécution pour ne pas figurer dans ce README
printf 'ALPACA_API_KEY=PK%s\n' "$(printf 'A%.0s' $(seq 20))" > .env && git add -f .env && git commit -m test
# → doit être refusé ; puis : git reset .env && rm .env
```
