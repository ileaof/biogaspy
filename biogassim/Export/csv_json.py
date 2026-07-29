"""Exportação de resultados em CSV e JSON (implementação real)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np


def _to_serializable(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    return obj


def export_json(data: dict[str, Any], path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_to_serializable(data), f, indent=2, ensure_ascii=False)


def export_csv(table: list[dict[str, Any]], path) -> None:
    """``table``: lista de dicionários (linha = caso/estágio)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not table:
        path.write_text("", encoding="utf-8")
        return
    keys = list(table[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in table:
            w.writerow({k: _to_serializable(v) for k, v in row.items()})


def export_profile_csv(profile: np.ndarray, columns: list[str], path) -> None:
    """Salva um perfil (N estágios x n colunas) como CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.atleast_2d(profile)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stage"] + columns)
        for i, row in enumerate(arr, start=1):
            w.writerow([i] + list(np.ravel(row)))


__all__ = ["export_json", "export_csv", "export_profile_csv"]
