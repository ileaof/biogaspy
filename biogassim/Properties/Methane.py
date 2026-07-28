"""Propriedades específicas do metano (gás/líquido) usadas nas perdas/recuperação."""
from __future__ import annotations

import numpy as np

from .components import get


def methane_viscosity(T: float, P: float) -> float:
    """Viscosidade do CH4 gasoso (Pa·s) -- Joss-Stiel/Thodos aproximado.

    Para baixa pressão usa-se método de Yoon-Thodos; aqui uma correlação
    simplificada de Sutherland calibrada em ~1.1e-5 Pa·s a 300 K.
    """
    T = float(T)
    mu0 = 1.1e-5 * (T / 300.0) ** 0.66
    # correção de pressão desprezada nas condições de upgrading típicas (<20 bar)
    return float(mu0)


def methane_solubility_water(T: float, P: float) -> float:
    """Constante de Henry do CH4 em água (mol/(L·atm)) -- usado para perdas.

    Valor ~1.4e-3 a 25°C (muito menor que CO2 -> seletividade).
    """
    # van't Hoff: ln H = ln Href - dHsol/R (1/T - 1/Tref)
    Href = 1.4e-3      # mol/(L·atm) a 298 K
    dH = -14000.0      # J/mol (solubilidade aumenta T-> baixa? mantém sinal de referência)
    R = 8.314
    H = Href * np.exp(-dH / R * (1.0 / T - 1.0 / 298.15))
    return float(H)


__all__ = ["methane_viscosity", "methane_solubility_water"]