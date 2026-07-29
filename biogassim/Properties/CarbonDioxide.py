"""Propriedades específicas do CO2 relevantes à solubilidade e captura."""
from __future__ import annotations


def co2_viscosity(T: float, P: float) -> float:
    """Viscosidade do CO2 gasoso (Pa·s) -- Sutherland simplificado."""
    T = float(T)
    return float(1.37e-5 * (T / 273.15) ** 0.79)


__all__ = ["co2_viscosity"]
