"""Cálculo de fugacidade e verificação de equilíbrio de fases."""
from __future__ import annotations

import numpy as np

from .eos import CubicEOS


def fugacity_coefficients(eos: CubicEOS, T: float, P: float,
                          z: np.ndarray, phase: str = "vapor") -> np.ndarray:
    """Atalho para φ_i via EOS."""
    return eos.Z_and_phi(T, P, z, phase=phase).phi


def equilibrium_residual(eos: CubicEOS, T: float, P: float,
                         x: np.ndarray, y: np.ndarray, K: np.ndarray) -> np.ndarray:
    """Resíduo de equilíbrio: ln(f_i^V) - ln(f_i^L) deve ser ~0.

    Usado como verificação de consistência termodinâmica.
    """
    fV = eos.fugacity(T, P, y, phase="vapor")
    fL = eos.fugacity(T, P, x, phase="liquid")
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log(np.where(fV > 0, fV, 1e-30)) - np.log(np.where(fL > 0, fL, 1e-30))


__all__ = ["fugacity_coefficients", "equilibrium_residual"]
