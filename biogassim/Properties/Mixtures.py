"""Regras de mistura para propriedades de transporte e termodinâmicas."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .components import Component


def molar_weight(components: Sequence[Component], z: Sequence[float]) -> float:
    """Massa molar da mistura (kg/mol)."""
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    mm = np.array([c.MM for c in components])
    return float(np.sum(z * mm))


def cp_ideal_mixture(components: Sequence[Component], z: Sequence[float], T: float) -> float:
    """Cp ideal da mistura (J/mol·K) por média ponderada."""
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    return float(np.sum(z * np.array([c.cp(T) for c in components])))


def wilke_viscosity(visc: Sequence[float], mm: Sequence[float], z: Sequence[float]) -> float:
    """Viscosidade de mistura gasosa pela regra de Wilke (Pa·s)."""
    visc = np.asarray(visc, dtype=float)
    mm = np.asarray(mm, dtype=float)
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    n = len(z)
    num = 0.0
    for i in range(n):
        denom = 0.0
        for j in range(n):
            phi = (1.0 + (visc[i] / visc[j]) ** 0.5
                   * (mm[j] / mm[i]) ** 0.25) ** 2
            denom += z[j] * phi / np.sqrt(8.0 * (mm[i] + mm[j]))
        num += z[i] * visc[i] / denom
    return float(num * np.sqrt(8.0)) if n == 1 else float(num)


__all__ = ["molar_weight", "cp_ideal_mixture", "wilke_viscosity"]
