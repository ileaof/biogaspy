"""Correlações adimensionais e de coluna para transferência de massa."""
from __future__ import annotations

import numpy as np

from ..Core.constants import R_J_MOL_K


def reynolds(rho: float, u: float, d: float, mu: float) -> float:
    """Re = ρ u d / μ."""
    return float(rho * u * d / mu)


def schmidt(mu: float, rho: float, D: float) -> float:
    """Sc = μ / (ρ D)."""
    return float(mu / (rho * D))


def sherwood_packing(kl: float, d: float, D: float) -> float:
    """Sh = k_L d / D."""
    return float(kl * d / D)


def onda_rocha_kl(rho_l: float, mu_l: float, sigma: float, g: float, D: float,
                  a: float, eps: float, L: float, d_p: float) -> float:
    """Coeficiente de transferência lado líquido (Onda-Rocha).

    Sh = (5.23 ... ) ... Retorna k_L em m/s. Forma simplificada.
    """
    Re_l = rho_l * L / (a * mu_l)
    Sc_l = mu_l / (rho_l * D)
    Sh = 0.0051 * Re_l ** 0.89 * Sc_l ** 0.5 * (a * d_p) ** 0.4
    k_L = Sh * D / d_p
    return float(k_L)


def kg_bravo(rho_g: float, mu_g: float, D_g: float, a: float, G: float, d_p: float) -> float:
    """Coeficiente lado gás (Bravo-Fair) simplificado."""
    Re_g = rho_g * G / (a * mu_g)
    Sc_g = mu_g / (rho_g * D_g)
    Sh = 0.0338 * Re_g ** 0.8 * Sc_g ** 0.333
    k_g = Sh * D_g / d_p
    return float(k_g)


def HTU(H: float, NTU: float) -> float:
    """Altura de uma unidade de transferência: Z = HTU * NTU."""
    return float(H / NTU if NTU else float("inf"))


def NTU_absorber(y_in: float, y_out: float, y_eq_in: float, y_eq_out: float) -> float:
    """Número de unidades de transferência (log-mean driving force)."""
    dy1 = y_in - y_eq_in
    dy2 = y_out - y_eq_out
    if dy1 * dy2 <= 0:
        return float("inf")
    lm = (dy1 - dy2) / np.log(dy1 / dy2)
    return float((y_in - y_out) / lm)


def HETP_from_HTU(HTU_val: float, lam: float) -> float:
    """HETP = HTU * λ, com λ = m (L/G) (fator de absorção)."""
    return float(HTU_val * lam)


def stage_efficiency(m: float, L: float, G: float, Ky: float, a: float, Z_stage: float) -> float:
    """Eficiência de Murphree (vapor) para um estágio: EoV = 1 - exp(-Ng)."""
    Ng = Ky * a * Z_stage / G  # número de unidades de transferência no estágio
    lam = m * G / L
    EoV = (1.0 - np.exp(-Ng * (1.0 - lam))) / (1.0 - lam + 1e-12)
    return float(np.clip(EoV, 0.0, 1.0))


__all__ = [
    "reynolds", "schmidt", "sherwood_packing",
    "onda_rocha_kl", "kg_bravo",
    "HTU", "NTU_absorber", "HETP_from_HTU", "stage_efficiency",
]