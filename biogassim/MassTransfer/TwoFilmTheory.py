"""Teoria dos dois filmes: coeficiente global de transferência gás-líquido."""
from __future__ import annotations

import numpy as np


def overall_Ky(ky: float, kx: float, m: float) -> float:
    """Coeficiente global baseado na fase gás: 1/Ky = 1/ky + m/kx.

    ``m`` é a inclinação da curva de equilíbrio (y = m x), por ex. H/P.
    """
    return float(1.0 / (1.0 / ky + m / kx))


def overall_Kx(ky: float, kx: float, m: float) -> float:
    """Coeficiente global baseado na fase líquida: 1/Kx = 1/(m ky) + 1/kx."""
    return float(1.0 / (1.0 / (m * ky) + 1.0 / kx))


def interfacial_composition(y_bulk: float, x_bulk: float, ky: float, kx: float,
                             m: float) -> tuple:
    """Resolve composição na interface (y_i, x_i) com equilíbrio y = m x.

    Das condições de fluxo contínuo: ky(y_bulk - y_i) = kx(x_i - x_bulk),
    com y_i = m x_i.
    """
    x_i = (ky * y_bulk + kx * x_bulk) / (kx + m * ky)
    y_i = m * x_i
    return float(y_i), float(x_i)


__all__ = ["overall_Ky", "overall_Kx", "interfacial_composition"]