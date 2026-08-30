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
    """Viscosidade de mistura gasosa pela regra de Wilke (Pa·s).

    Wilke (1950) / Reid-Prausnitz-Poling eq. 9-5.12:

        φ_ij = [1 + (μ_i/μ_j)^(1/2)·(M_i/M_j)^(1/4)]² / √(8·(1 + M_i/M_j))
        μ_mix = Σ_i [ x_i·μ_i / Σ_j x_j·φ_ij ]   (denominador somado em j para cada i)

    Reduz-se a μ_i puro quando a composição é de um componente único (φ_ii = 1).
    """
    visc = np.asarray(visc, dtype=float)
    mm = np.asarray(mm, dtype=float)
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    n = len(z)
    mu = 0.0
    for i in range(n):
        denom_i = 0.0
        for j in range(n):
            phi_ij = ((1.0 + (visc[i] / visc[j]) ** 0.5
                       * (mm[i] / mm[j]) ** 0.25) ** 2
                      / np.sqrt(8.0 * (1.0 + mm[i] / mm[j])))
            denom_i += z[j] * phi_ij
        mu += z[i] * visc[i] / denom_i
    return float(mu)


__all__ = ["molar_weight", "cp_ideal_mixture", "wilke_viscosity"]