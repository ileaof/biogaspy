"""Equação de Estado de Peng-Robinson (1978)."""
from __future__ import annotations

import numpy as np

from ..Core.constants import R_J_MOL_K
from .eos import CubicEOS, EOSResult  # noqa: F401

# Parâmetros da forma de atrito: u = 1 + sqrt(2), w = 1 - sqrt(2)
_SQRT2 = np.sqrt(2.0)


class PengRobinson(CubicEOS):
    """EOS de Peng-Robinson com α(T,ω) de Mathias-Copeman simplificada (PR78).

    a_c = 0.45724 R² Tc² / Pc ;  b = 0.07780 R Tc / Pc
    α = [1 + κ(1 - √Tr)]² ,  κ = 0.37464 + 1.54226 ω - 0.26992 ω²
    """

    def a_c(self, Tc: float, Pc: float) -> float:
        return 0.45724 * (R_J_MOL_K * Tc) ** 2 / Pc

    def b(self, Tc: float, Pc: float) -> float:
        return 0.07780 * R_J_MOL_K * Tc / Pc

    def alpha(self, T: float) -> np.ndarray:
        Tr = T / self.Tc
        kappa = 0.37464 + 1.54226 * self.omega - 0.26992 * self.omega ** 2
        return (1.0 + kappa * (1.0 - np.sqrt(Tr))) ** 2

    def cubic_coeffs(self, A: float, B: float) -> np.ndarray:
        # Z³ - (1-B) Z² + (A - 3B² - 2B) Z - (AB - B² - B³) = 0
        c2 = B - 1.0
        c1 = A - 3.0 * B * B - 2.0 * B
        c0 = -(A * B - B * B - B ** 3)
        return np.array([1.0, c2, c1, c0])

    def ln_phi(self, A, B, Z, z, ai, am, bm) -> np.ndarray:
        coeff = 2.0 * np.sqrt(2.0) * B
        ln = np.zeros(self.n)
        for i in range(self.n):
            a_ij = np.array([np.sqrt(ai[i] * ai[j]) * (1.0 - self.kij[i, j])
                             for j in range(self.n)])
            term = 2.0 * np.sum(z * a_ij) / am - self.bi[i] / bm
            ln[i] = (self.bi[i] / bm * (Z - 1.0)
                     - np.log(Z - B)
                     - (A / coeff) * term
                     * np.log((Z + (1.0 + _SQRT2) * B) / (Z + (1.0 - _SQRT2) * B + 1e-30)))
        return ln


__all__ = ["PengRobinson"]
