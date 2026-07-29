"""Velocidade de flooding e diâmetro de coluna recheiada.

Modelo GPDC de Eckert / Sherwood-Lobo em unidades SI. O parâmetro de capacidade
(ordenada do gráfico GPDC)

    Y = (u² / g) · (ρ_g / (ρ_l - ρ_g)) · Fp · (μ_l / μ_w)^0.1

é levado ao ponto de flooding pela curva de flood ``Y_flood(X)``, função do
parâmetro de fluxo (abscissa)

    X = (L/G)_mass · √(ρ_g / ρ_l).

A curva de flood ``Y_flood = C_flood · exp(-k_flood · X)`` é uma aproximação
monotônica calibrada contra dados de flooding ar/água para anéis Pall (Kister,
*Distillation Design*; Eckert GPDC). Para ar/água a 1 atm, 20 °C:

    Pall 50 mm (Fp=66):  u_flood ≈ 2.2 m/s  (L/G_mass ≈ 10)
    Pall 25 mm (Fp=180): u_flood ≈ 1.4 m/s  (L/G_mass ≈ 10)

 dentro de ~20 % do gráfico GPDC. Maior ``Fp`` → menor ``u_f``; maior ``ρ_g`` →
 menor ``u_f``; maior ``L/G`` → menor ``u_f``; líquido viscoso → menor ``u_f``.
"""
from __future__ import annotations

import numpy as np

from ..Core.constants import G_STD
from .Packing import Packing

MU_WATER = 1.0e-3          # Pa·s, água a 20 °C (referência da correção de μ)

# curva de flood do GPDC: ordenada Y no ponto de flooding vs parâmetro de fluxo X
_C_FLOOD = 0.05            # Y_flood quando X → 0 (gás leve, baixa carga líquida)
_K_FLOOD = 0.5             # decaimento da ordenada com a carga líquida (X)


def _flow_parameter(L_over_G_mass: float, rho_g: float, rho_l: float) -> float:
    """Parâmetro de fluxo (abscissa) X = (L/G)_mass √(ρ_g/ρ_l)."""
    return float(L_over_G_mass) * np.sqrt(rho_g / max(rho_l, 1e-9))


def _flood_ordinate(X: float) -> float:
    """Ordenada do GPDC no ponto de flooding, função do parâmetro de fluxo X."""
    return _C_FLOOD * np.exp(-_K_FLOOD * X)


def flooding_velocity(rho_g: float, rho_l: float, mu_l: float,
                      packing: Packing, L_over_G_mass: float) -> float:
    """Velocidade superficial do gás no flooding (m/s) -- GPDC de Eckert (SI).

    Inverte Y = (u²/g)(ρ_g/(ρ_l-ρ_g)) Fp (μ_l/μ_w)^0.1  ⇒
        u_f = √[ Y_flood · g · (ρ_l - ρ_g) / (ρ_g · Fp · (μ_l/μ_w)^0.1) ].
    """
    Fp = packing.packing_factor
    X = _flow_parameter(L_over_G_mass, rho_g, rho_l)
    Y_f = _flood_ordinate(X)
    visc = (mu_l / MU_WATER) ** 0.1
    denom = rho_g * Fp * visc
    if denom <= 0.0:
        return 0.05
    u_f2 = Y_f * G_STD * (rho_l - rho_g) / denom
    return float(max(np.sqrt(max(u_f2, 0.0)), 0.05))


def operating_velocity(u_flood: float, fraction: float = 0.7) -> float:
    """Velocidade de operação (fração do flooding, tipicamente 0.6-0.8)."""
    return float(u_flood * fraction)


def column_diameter(G_mass: float, rho_g: float, u_op: float) -> float:
    """Diâmetro a partir de vazão mássica de gás e velocidade superficial."""
    area = G_mass / (rho_g * max(u_op, 1e-9))
    return float(np.sqrt(4.0 * area / np.pi))


__all__ = ["flooding_velocity", "operating_velocity", "column_diameter",
           "_flow_parameter", "_flood_ordinate"]
