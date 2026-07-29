"""Solvente físico: água (lavagem com água / Water Scrubbing)."""
from __future__ import annotations

from ..Properties.Water import water_cp, water_density, water_viscosity
from ..Thermodynamics.Henry import henry_water
from .base import Solvent


class WaterSolvent(Solvent):
    """Água como solvente físico. Equilíbrio via lei de Henry."""

    name = "H2O"
    absorbed_species: list[str] = ["CO2", "CH4", "N2", "H2S"]

    def __init__(self):
        self.henry = henry_water()

    def K_value(self, species, T, P, x, loading=0.0) -> float:
        if species not in self.absorbed_species:
            return 0.0
        try:
            return self.henry.K_value(species, T, P)
        except KeyError:
            return 0.0

    def heat_of_absorption(self, species: str) -> float:
        # calor de solução aproximado (exotérmico -> negativo na dissolução,
        # usamos magnitude como calor liberado)
        return {"CO2": 20000.0, "CH4": 14000.0, "H2S": 21000.0, "N2": 10000.0}.get(species, 15000.0)

    def density(self, T: float) -> float:
        return water_density(T)

    def viscosity(self, T: float) -> float:
        return water_viscosity(T)

    def cp_liquid(self, T: float) -> float:
        return water_cp(T)

    def molar_mass_liquid(self) -> float:
        return 0.018015


__all__ = ["WaterSolvent"]
