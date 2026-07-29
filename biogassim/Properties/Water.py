"""Propriedades específicas da água (líquido) para lavagem com água."""
from __future__ import annotations

from ..Core.constants import C_TO_K


def water_density(T: float) -> float:
    """Densidade da água líquida (kg/m³) -- correlação de Watson."""
    T = float(T)
    # Watson base: rho = rho_c * (1 - Tr)^n; aqui usamos aproximação polinomial 0-100°C
    Tc = 647.096
    if T >= Tc:
        return 322.0
    rho = 1000.0 * (1.0 - 0.001 * (T - 277.15))  # aproximação suave perto de 4°C
    # melhor ajuste: Kell eq.
    a = 999.83952
    b = 0.018224944
    c = -7.92221e-6
    d = 5.59448e-8
    e = -1.0e-10
    # em função de T (°C)
    Tc_c = T - C_TO_K
    rho = a + b * Tc_c + c * Tc_c**2 + d * Tc_c**3 + e * Tc_c**4
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
    """Tensão superficial água/ar (N/m)."""
    T = float(T)
    if T >= 647.0:
        return 0.0
    return float(0.2358 * (1.0 - (T - 273.15) / 370.0) ** 1.256)


__all__ = ["water_density", "water_viscosity", "water_cp", "water_surface_tension"]
