"""Perda de carga em coluna recheiada -- modelo de Stichlmair, Bravo & Fair (1989).

Modelo mecânico em unidades SI, válido do escoamento seco até a região de carga
/loading/ e flooding. Equações (Stichlmair et al., *Gas Sep. & Purif.* 3, 1989):

    diâmetro equivalente de partícula:  d_p = 6(1-ε)/a
    Reynolds (gás, seco):               Re = u_g d_p ρ_g / ((1-ε) μ_g)
    fator de atrito (partícula única):  Ψ0 = C1/Re + C2/√Re + C3
    perda de carga seca:               ΔP_d/Z = (3/4) Ψ0 (1-ε)/ε^4.65 · ρ_g u_g²/d_p
    holdup líquido (pré-carga):        h_L = 0.555 · Fr^(1/3),  Fr = u_l² a/(g ε^4.65)
    perda molhada:                     ΔP/Z = ΔP_d/Z · (ε/(ε-h_L))^4.65

A forma molhada reduz-se exatamente à seca quando h_L → 0 e diverge quando
h_L → ε (flooding), como no modelo original. O termo secundário
((1-ε+h_L)/(1-ε))^((2+c)/3) (c = constante do recheio) é omitido: vale ~1 para
holdups típicos e depende de ``c`` não tabulado para todos os recheios.
"""
from __future__ import annotations

import numpy as np

from ..Core.constants import G_STD
from .Packing import Packing

_MU_G_DEFAULT = 1.5e-5   # Pa·s, viscosidade de gás típica (se não informada)


def _equivalent_diameter(packing: Packing) -> float:
    """d_p = 6(1-ε)/a -- diâmetro equivalente de partícula do recheio."""
    eps = packing.void_fraction
    return 6.0 * (1.0 - eps) / max(packing.specific_area, 1e-9)


def _friction_factor(Re: float, packing: Packing) -> float:
    """Ψ0 = C1/Re + C2/√Re + C3 -- fator de atrito de partícula única."""
    Re = max(Re, 1e-6)
    return packing.C1 / Re + packing.C2 / np.sqrt(Re) + packing.C3


def dry_pressure_drop(rho_g: float, u_g: float, packing: Packing,
                      mu_g: float = _MU_G_DEFAULT) -> float:
    """Perda de carga seca por unidade de altura (Pa/m) -- Stichlmair (1989)."""
    eps = packing.void_fraction
    d_p = _equivalent_diameter(packing)
    Re = u_g * d_p * rho_g / ((1.0 - eps) * mu_g)
    psi = _friction_factor(Re, packing)
    return float(0.75 * psi * (1.0 - eps) / (eps ** 4.65) * rho_g * u_g * u_g / d_p)


def _liquid_holdup(rho_l: float, u_l: float, packing: Packing) -> float:
    """Holdup líquido (m³ líquido/m³ torre) abaixo do ponto de carga."""
    eps = packing.void_fraction
    Fr = u_l * u_l * packing.specific_area / (G_STD * (eps ** 4.65))
    h = 0.555 * Fr ** (1.0 / 3.0)
    return min(h, 0.95 * eps)          # limita perto do flooding


def wet_pressure_drop(rho_l: float, rho_g: float, u_g: float, u_l: float,
                      packing: Packing, mu_g: float = _MU_G_DEFAULT) -> float:
    """Perda de carga molhada por unidade de altura (Pa/m) -- Stichlmair (1989).

    ΔP_wet = ΔP_dry · (ε/(ε-h_L))^4.65,  h_L = 0.555·Fr^(1/3).
    Reduz-se à seca quando u_l → 0 e diverge quando h_L → ε (flooding).
    """
    dp_dry = dry_pressure_drop(rho_g, u_g, packing, mu_g)
    eps = packing.void_fraction
    h_L = _liquid_holdup(rho_l, u_l, packing) if u_l > 0.0 else 0.0
    eps_eff = eps - h_L
    if eps_eff <= 1e-4:
        return 1e6              # flooding: holdup saturou o vazio
    return float(dp_dry * (eps / eps_eff) ** 4.65)


__all__ = ["dry_pressure_drop", "wet_pressure_drop"]
