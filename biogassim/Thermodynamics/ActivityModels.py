"""Modelos de coeficiente de atividade para a fase líquida.

NRTL implementado para sistemas CO2-amina-água (forma simplificada, dois
parâmetros por par). e-UNIQUAC fica como stub documentado para extensão.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class NRTL:
    """Modelo NRTL com parâmetros τ_ij e α_ij."""
    tau: np.ndarray          # (n,n) parâmetros τ_ij
    alpha: np.ndarray        # (n,n) não-aleatoriedade

    def gamma(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        n = len(x)
        tau = self.tau
        G = np.exp(-self.alpha * tau)
        ln_gamma = np.zeros(n)
        for i in range(n):
            Sj = 0.0
            for j in range(n):
                Sj += x[j] * G[i, j] * tau[i, j]
            S = 0.0
            for j in range(n):
                S += x[j] * G[i, j]
            term1 = Sj / (S + 1e-30)
            term2 = 0.0
            for j in range(n):
                Sj2 = x[j] * G[j, i] * tau[j, i]
                S2 = sum(x[k] * G[j, k] for k in range(n))
                term2 += (x[j] * G[j, i] / (S2 + 1e-30)) * (tau[j, i] - Sj2 / (S2 + 1e-30))
            ln_gamma[i] = term1 + term2
        return np.exp(ln_gamma)


def e_uniquac_stub(x: np.ndarray, **params) -> np.ndarray:
    """Stub do modelo e-UNIQUAC -- a ser implementado em versão futura."""
    raise NotImplementedError("e-UNIQUAC ainda não implementado (ver ROADMAP).")


__all__ = ["NRTL", "e_uniquac_stub"]
