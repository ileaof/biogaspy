"""Equação de Estado de Soave-Redlich-Kwong (SRK)."""
from __future__ import annotations

import numpy as np

from ..Core.constants import R_J_MOL_K
from .eos import CubicEOS


class SRK(CubicEOS):
    """EOS Soave-Redlich-Kwong.

    a_c = 0.42748 R² Tc² / Pc ;  b = 0.08664 R Tc / Pc
    α = [1 + m(1 - √Tr)]² ,  m = 0.480 + 1.574 ω - 0.176 ω²
    """

    def a_c(self, Tc: float, Pc: float) -> float:
        return 0.42748 * (R_J_MOL_K * Tc) ** 2 / Pc

    def b(self, Tc: float, Pc: float) -> float:
        return 0.08664 * R_J_MOL_K * Tc / Pc

    def alpha(self, T: float) -> np.ndarray:
        Tr = T / self.Tc
        m = 0.480 + 1.574 * self.omega - 0.176 * self.omega ** 2
        return (1.0 + m * (1.0 - np.sqrt(Tr))) ** 2

    def cubic_coeffs(self, A: float, B: float) -> np.ndarray:
        # Z³ - Z² + (A - B - B²) Z - A B = 0
        c2 = -1.0
        c1 = A - B - B * B
        c0 = -A * B
        return np.array([1.0, c2, c1, c0])

    def ln_phi(self, A, B, Z, z, ai, am, bm) -> np.ndarray:
        ln = np.zeros(self.n)
        for i in range(self.n):
            a_ij = np.array([np.sqrt(ai[i] * ai[j]) * (1.0 - self.kij[i, j])
                             for j in range(self.n)])
            term = 2.0 * np.sum(z * a_ij) / am - self.bi[i] / bm
            ln[i] = (self.bi[i] / bm * (Z - 1.0)
                     - np.log(Z - B)
                     - (A / B + 1e-30) * term * np.log((Z + B) / (Z + 1e-30)))
        return ln


__all__ = ["SRK"]