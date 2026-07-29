"""Teoria do filme: coeficiente de transferência de massa unidirecional."""
from __future__ import annotations

import numpy as np


def film_flux(k: float, c_bulk: float, c_interface: float) -> float:
    """Fluxo molar através do filme: N = k (c_bulk - c_interface) [mol/(m²·s)]."""
    return float(k * (c_bulk - c_interface))


def enhancement_factor(reactive: bool, Hatta: float = 0.0) -> float:
    """Fator de intensificação E para absorção reativa.

    E ~ 1 (sem reação) ou E ~ Hatta/tanh(Hatta) para reação pseudo-1ª ordem.
    """
    if not reactive or Hatta <= 0:
        return 1.0
    return float(Hatta / np.tanh(Hatta))


__all__ = ["film_flux", "enhancement_factor"]
