"""Solventes físicos: Selexol (dimetil éter de polietilenoglicol) e Rectisol (metanol).

Modelo via lei de Henry com constantes próprias (maior solubilidade de CO2 que
água). Valores de referência a 298 K; dependência T via van't Hoff. São stubs
calibrados -- validar contra dados de solubilidade antes de projeto.
"""
from __future__ import annotations

from typing import List

import numpy as np

from .base import Solvent
from ..Core.constants import R_J_MOL_K


class _PhysicalSolvent(Solvent):
    """Base para solventes físicos genéricos (Henry por componente)."""
    name = "physical"
    absorbed_species: List[str] = ["CO2", "CH4", "N2", "H2S"]

    # Href [Pa], dHsol [J/mol] por espécie; subclasses definem
    href: dict = {}
    dh: dict = {}
    mm_liquid: float = 0.0    # kg/mol
    rho_ref: float = 1000.0  # kg/m³
    mu_ref: float = 0.003    # Pa·s
    cp_ref: float = 2000.0   # J/(kg·K)

    def K_value(self, species, T, P, x, loading=0.0) -> float:
        if species not in self.absorbed_species:
            return 0.0
        Href = self.href.get(species, 1e9)
        dH = self.dh.get(species, 15000.0)
        # van't Hoff: ln H = ln Href - dH/R (1/T - 1/298); dH>0 exotérmico ->
        # T menor -> H menor -> mais solúvel (consistente com Thermodynamics.Henry)
        H = Href * np.exp(-dH / R_J_MOL_K * (1.0 / T - 1.0 / 298.15))
        return float(H / P)

    def heat_of_absorption(self, species: str) -> float:
        return {"CO2": 15000.0, "CH4": 12000.0, "H2S": 19000.0, "N2": 9000.0}.get(species, 12000.0)

    def density(self, T): return float(self.rho_ref * (1 - 7e-4 * (T - 298.15)))
    def viscosity(self, T): return float(self.mu_ref * np.exp(1500.0 * (1.0 / T - 1.0 / 298.15)))
    def cp_liquid(self, T): return float(self.cp_ref * self.mm_liquid)
    def molar_mass_liquid(self): return float(self.mm_liquid)


class SelexolSolvent(_PhysicalSolvent):
    """Selexol: solubilidade de CO2 ~6x maior que água a 25 °C."""
    name = "Selexol"
    href = {
        "CO2": 2.7e7,     # ~1/6 do H na água
        "CH4": 1.5e9,
        "H2S": 1.5e7,
        "N2": 4.0e9,
    }
    dh = {"CO2": 18000.0, "CH4": 14000.0, "H2S": 20000.0, "N2": 10000.0}
    mm_liquid = 0.280    # média PEG-DME
    rho_ref = 1030.0
    mu_ref = 0.005
    cp_ref = 2100.0


class RectisolSolvent(_PhysicalSolvent):
    """Rectisol: metanol a baixa T (-40 a -70 °C); alta seletividade."""
    name = "Methanol"
    href = {
        "CO2": 1.5e7,    # metanol dissolve mais CO2 que água
        "CH4": 8.0e8,
        "H2S": 7.0e6,
        "N2": 3.0e9,
    }
    dh = {"CO2": 16000.0, "CH4": 12000.0, "H2S": 19000.0, "N2": 9000.0}
    mm_liquid = 0.032
    rho_ref = 790.0
    mu_ref = 0.0008
    cp_ref = 2500.0


__all__ = ["SelexolSolvent", "RectisolSolvent"]