"""Chargement de `config.yaml`, source unique des paramètres du projet."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Lit le YAML et renvoie un dictionnaire brut. Aucune valeur par défaut cachée dans le code."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with open(config_path, encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"{config_path} doit contenir un objet YAML")
    return config


def tp_sl_fractions(config: dict[str, Any]) -> tuple[float, float]:
    """Convertit TP/SL en points d'indice (script de l'ami) en fractions du prix.

    30 points sur un indice à 24 000 = 0,125 % du prix : la même distance relative sur QQQ.
    """
    exits = config["exits"]
    reference = float(exits["index_reference"])
    if reference <= 0:
        raise ValueError("exits.index_reference doit être positif")
    return float(exits["tp_points"]) / reference, float(exits["sl_points"]) / reference
