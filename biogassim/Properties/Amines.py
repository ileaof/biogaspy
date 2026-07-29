"""Propriedades de soluções de aminas (MEA, DEA, MDEA) -- correlações de Weiland."""
from __future__ import annotations


def amine_density(name: str, T: float, w_amine: float) -> float:
    """Densidade de solução aquosa de amina (kg/m³).

    ``w_amine`` é fração mássica da amina na solução. Correlação aproximada.
    """
    T = float(T)
    rho_water = 1000.0 - 0.5 * (T - 298.15)
    rho_amine = {
        "MEA": 1012.0 - 0.6 * (T - 298.15),
        "DEA": 1060.0 - 0.6 * (T - 298.15),
        "MDEA": 1040.0 - 0.6 * (T - 298.15),
    }.get(name, 1020.0)
    return float(rho_water * (1 - w_amine) + rho_amine * w_amine)


def amine_viscosity(name: str, T: float, w_amine: float, loading: float = 0.0) -> float:
    """Viscosidade de solução de amina (Pa·s).

    ``loading`` = mol CO2 / mol amina. Correlação simplificada de Weiland-like.
    """
    T = float(T)
    mu_w = 2.414e-5 * 10.0 ** (247.8 / (T - 140.0))
    base = {"MEA": 0.0025, "DEA": 0.006, "MDEA": 0.005}.get(name, 0.004)
    mu = mu_w * (1 - w_amine) + base * w_amine
    mu *= 1.0 + 1.5 * loading   # carregamento aumenta viscosidade
    return float(mu)


def amine_cp(name: str, T: float, w_amine: float) -> float:
    """Cp da solução (J/(kg·K)) -- média mássica simples."""
    cp_w = 4180.0
    cp_a = {"MEA": 2600.0, "DEA": 2400.0, "MDEA": 2400.0}.get(name, 2500.0)
    return float(cp_w * (1 - w_amine) + cp_a * w_amine)


def heat_of_absorption(name: str) -> float:
    """Calor de reação CO2 + amina (J/mol CO2). Valores típicos de literatura."""
    return {"MEA": 85000.0, "DEA": 70000.0, "MDEA": 55000.0}.get(name, 70000.0)


__all__ = [
    "amine_density", "amine_viscosity", "amine_cp", "heat_of_absorption",
]
