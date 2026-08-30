"""Modelos de coeficiente de atividade para a fase líquida.

NRTL implementado para sistemas CO2-amina-água (forma simplificada, dois
parâmetros por par). e-UNIQUAC fica como stub documentado para extensão.

Referência: Prausnitz et al., eq. 6-171 (Reid-Prausnitz-Poling eq. 8-5.15):

    ln γ_i = Σ_j (τ_ji G_ji x_j)/Σ_k (G_ki x_k)
             + Σ_j [G_ij x_j/Σ_k (G_kj x_k)]·(τ_ij - Σ_m τ_mj G_mj x_m / Σ_k G_kj x_k)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class NRTL:
    """Modelo NRTL com parâmetros τ_ij e α_ij (diagonais nulas -> G_ii = 1)."""
    tau: np.ndarray          # (n,n) parâmetros τ_ij
    alpha: np.ndarray        # (n,n) não-aleatoriedade

    def gamma(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        n = len(x)
        tau = self.tau
        G = np.exp(-self.alpha * tau)        # G_ij = exp(-α_ij·τ_ij)
        ln_gamma = np.zeros(n)
        for i in range(n):
            # termo 1: Σ_j τ_ji G_ji x_j / Σ_k G_ki x_k
            S_i = float(x @ G[:, i])                       # Σ_k x_k G_ki
            term1 = float(x @ (G[:, i] * tau[:, i])) / S_i
            # termo 2: Σ_j (G_ij x_j/Σ_k G_kj x_k)·(τ_ij - Σ_m τ_mj G_mj x_m/Σ_k G_kj x_k)
            term2 = 0.0
            for j in range(n):
                S_j = float(x @ G[:, j])                   # Σ_k x_k G_kj
                M_j = float(x @ (G[:, j] * tau[:, j]))     # Σ_m x_m τ_mj G_mj
                term2 += (x[j] * G[i, j] / (S_j + 1e-30)) * (tau[i, j] - M_j / (S_j + 1e-30))
            ln_gamma[i] = term1 + term2
        return np.exp(ln_gamma)


def e_uniquac_stub(x: np.ndarray, **params) -> np.ndarray:
    """Stub do modelo e-UNIQUAC -- a ser implementado em versão futura."""
    raise NotImplementedError("e-UNIQUAC ainda não implementado (ver ROADMAP).")


__all__ = ["NRTL", "e_uniquac_stub"]