"""Propriedades específicas da água (líquido) para lavagem com água."""
from __future__ import annotations

import numpy as np

from ..Core.constants import C_TO_K

# constante do ajuste polinomial à tabulação de Kell (1975):
# ρ(t) [kg/m³], t em °C, validade 0-100 °C (erro máximo ~0,012 kg/m³).
# Coeficientes de t⁶ a t⁰ (np.polyfit de grau 6 sobre 17 pontos de referência).
_RHO_COEF = (-5.572729e-12, 2.835295e-09, -6.068943e-07, 7.638281e-05,
             -8.647072e-03, 6.501321e-02, 9.998431e+02)
_T_CRIT_WATER = 647.096   # K


def water_density(T: float) -> float:
    """Densidade da água líquida (kg/m³) -- ajuste à tabulação de Kell (1975).

    Polinômio em t = T - 273,15 °C com máximo físico em ~4 °C:
    ρ(0 °C) = 999,84; ρ(4 °C) = 999,97; ρ(25 °C) = 997,05;
    ρ(40 °C) = 992,21; ρ(90 °C) = 965,31; ρ(100 °C) = 958,35 kg/m³.
    """
    T = float(T)
    if T >= _T_CRIT_WATER:
        return 322.0                      # densidade crítica
    t = T - C_TO_K
    rho = np.polyval(_RHO_COEF, t)
    return float(rho)


def water_viscosity(T: float) -> float:
    """Viscosidade dinâmica da água líquida (Pa·s) -- Vogel."""
    T = float(T)
    if T <= 273.15:
        T = 273.15
    # Vogel: mu(Pa·s) = 2.414e-5 * 10^(247.8/(T-140))
    return float(2.414e-5 * 10.0 ** (247.8 / (T - 140.0)))


def water_cp(T: float) -> float:
    """Cp da água líquida (J/mol·K) ~ 75.3 constante até ~100°C."""
    return 75.29


def water_surface_tension(T: float) -> float:
    """Tensão superficial água/vapor (N/m) -- forma de Vargaftik (ex.: σ(25 °C) = 0,0720).

    σ = B·(1 - Tr)^1.256 · [1 - 0.625(1 - Tr)], Tr = T/Tc, B = 235,8 mN/m.
    """
    T = float(T)
    Tr = T / _T_CRIT_WATER
    if Tr >= 1.0:
        return 0.0
    one_m = 1.0 - Tr
    return float(0.2358 * one_m ** 1.256 * (1.0 - 0.625 * one_m))


__all__ = ["water_density", "water_viscosity", "water_cp", "water_surface_tension"]