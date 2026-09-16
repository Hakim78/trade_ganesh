#!/usr/bin/env bash
# pre-commit-backtest-check.sh — garde-fou anti-biais et anti-fuite, exécuté avant chaque commit.
#
# Origine : le README de shakeebshaan/claude-code-quant-skills cite un hook de ce nom, mais le dépôt
# ne le contient pas. Celui-ci est écrit pour ce projet, à partir des invariants de CLAUDE.md.
#
# Bloque le commit si :
#   1. un secret ou une sortie est indexé : .env (sauf .env.example), data/, outputs/
#   2. une clé Alpaca en dur ou l'endpoint LIVE api.alpaca.markets (sans « paper- ») apparaît dans un fichier indexé
#   3. un motif de look-ahead apparaît dans du code applicatif : .shift(-n), rolling(center=True), iloc[i+1]
#   4. des coûts à zéro sont codés en dur : fees=0 / slippage=0 / commission=0
#   5. `make test` échoue (seulement si un .py est indexé et qu'un Makefile a une cible test)
#
# Contournements : SKIP_TESTS=1 saute l'étape 5. `git commit --no-verify` saute tout : à réserver
# aux commits de documentation, et à dire explicitement dans le message de commit.
set -euo pipefail

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
fail=0

staged="$(git diff --cached --name-only --diff-filter=ACMR)"
[ -z "$staged" ] && exit 0

# --- 1. Fichiers interdits -------------------------------------------------------------------
while IFS= read -r f; do
  [ -z "$f" ] && continue
  base="${f##*/}"
  case "$base" in
    .env|.env.*)
      if [ "$base" != ".env.example" ]; then red "BLOQUÉ : fichier secret indexé : $f"; fail=1; fi ;;
  esac
  case "$f" in
    data/*|outputs/*)
      case "$base" in .gitkeep) ;; *) red "BLOQUÉ : données brutes ou sorties indexées : $f"; fail=1 ;; esac ;;
  esac
done <<< "$staged"

# --- 2. Secrets et endpoint live (contenu indexé, fichiers texte) ------------------------------
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in *.png|*.jpg|*.jpeg|*.gif|*.pdf|*.parquet|*.pkl|*.zip|*.ico|*.woff|*.woff2) continue ;; esac
  content="$(git show ":$f" 2>/dev/null || true)"
  if printf '%s' "$content" | grep -Eq '(ALPACA|APCA)[A-Z_]*(KEY|SECRET)[A-Z_]*[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9]{16,}'; then
    red "BLOQUÉ : clé Alpaca en dur dans $f (utiliser .env, cf. invariant 5)"; fail=1
  fi
  if printf '%s' "$content" | grep -Eq '\bPK[A-Z0-9]{16,}\b|\bAK[A-Z0-9]{16,}\b'; then
    red "BLOQUÉ : identifiant de clé Alpaca (PK…/AK…) dans $f"; fail=1
  fi
  if printf '%s' "$content" | grep -Eq 'https?://api\.alpaca\.markets'; then
    red "BLOQUÉ : endpoint LIVE api.alpaca.markets dans $f — paper-api.alpaca.markets uniquement (invariant 6)"; fail=1
  fi
done <<< "$staged"

# --- 3. Look-ahead et 4. coûts nuls (code applicatif Python uniquement) ------------------------
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in *.py) ;; *) continue ;; esac
  case "$f" in tests/*|.claude/*|*/tests/*) continue ;; esac
  content="$(git show ":$f" 2>/dev/null || true)"
  hits="$(printf '%s' "$content" | grep -nE '\.shift\([[:space:]]*-[0-9]|center[[:space:]]*=[[:space:]]*True|\.iloc\[[^]]*\+[[:space:]]*1[[:space:]]*\]' || true)"
  if [ -n "$hits" ]; then
    red "BLOQUÉ : motif de look-ahead dans $f (invariant 1) :"; printf '%s\n' "$hits"; fail=1
  fi
  hits="$(printf '%s' "$content" | grep -nE '(fees|slippage|commission)[[:space:]]*=[[:space:]]*0(\.0+)?[[:space:]]*(,|\)|#|$)' || true)"
  if [ -n "$hits" ]; then
    red "BLOQUÉ : coûts à zéro codés en dur dans $f (invariant 2, lire config.yaml) :"; printf '%s\n' "$hits"; fail=1
  fi
done <<< "$staged"

# --- 5. Tests ---------------------------------------------------------------------------------
if [ "${SKIP_TESTS:-0}" != "1" ] && [ -f pyproject.toml ] && printf '%s\n' "$staged" | grep -Eq '\.py$'; then
  if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
  elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
  else PY=python; fi
  yellow "→ $PY -m pytest (SKIP_TESTS=1 pour sauter)"
  if ! "$PY" -m pytest -q; then red "BLOQUÉ : les tests échouent"; fail=1; fi
fi

if [ "$fail" -ne 0 ]; then
  red "Commit refusé par .claude/hooks/pre-commit-backtest-check.sh"
  exit 1
fi
exit 0
