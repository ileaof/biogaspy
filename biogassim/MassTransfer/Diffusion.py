"""Coeficientes de difusão molecular (gases e líquidos)."""
from __future__ import annotations

import numpy as np


def fuller_gas(T: float, P: float, M_a: float, M_b: float,
               sigma_a: float, sigma_b: float) -> float:
    """Difusão binária gás-gás (Fuller-Schettler-Giddings), m²/s.

    Forma padrão: D[cm²/s] = 1e-3 T^1.75 / (P_atm (Σv_a^(1/3)+Σv_b^(1/3))²) ·
    √(1/M_a + 1/M_b); convertida para m²/s (×1e-4). ``M`` em g/mol, ``sigma`` =
    volume de difusão de Fuller (soma atômica), ``P`` em Pa.
    """
    P_atm = P / 101325.0
    denom = (sigma_a ** (1.0 / 3.0) + sigma_b ** (1.0 / 3.0)) ** 2
    return 1.0e-7 * T ** 1.75 * np.sqrt(1.0 / M_a + 1.0 / M_b) / P_atm / denom


def wilke_chang(T: float, mu_b: float, M_b: float, V_a: float, phi_b: float = 1.0) -> float:
    """Difusão de A (soluto) em B (solvente líquido), Wilke-Chang, m²/s.

    Forma padrão: D[cm²/s] = 7.4e-8 √(φ M_b) T / (μ_b V_a^0.6); convertida para
    m²/s (×1e-4). ``mu_b`` viscosidade do solvente (cP); ``M_b`` massa molar do
    solvente (g/mol); ``V_a`` volume molar de A no ponto de ebulição (cm³/mol);
    ``phi_b`` fator de associação (água=2.6, outros=1).
    """
    T = float(T)
    return 7.4e-8 * np.sqrt(phi_b * M_b) * T / (mu_b * V_a ** 0.6) * 1.0e-4


def gas_diffusion_volumes() -> dict:
    """Volumes de difusão de Fuller (soma atômica) por componente."""
    return {
        "CO2": 26.9,
        "CH4": 24.42,
        "N2": 17.9,
        "O2": 16.3,
        "H2O": 13.1,
        "H2S": 20.0,   # aproximado
    }


__all__ = ["fuller_gas", "wilke_chang", "gas_diffusion_volumes"]
