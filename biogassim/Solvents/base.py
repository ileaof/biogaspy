"""Interface base de solventes (Solvent ABC).

Um solvente fornece:
  - ``absorbed_species``: lista de espécies gasosas que ele absorve;
  - ``K_value(species, T, P, x, loading)``: constante de equilíbrio y = K·x;
  - ``heat_of_absorption(species)``: calor (J/mol);
  - propriedades da fase líquida (ρ, μ, Cp, MM).

Todas as espécies fora de ``absorbed_species`` são tratadas como não-voláteis
(K=0) pelo Absorbedor.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Solvent(ABC):
    name: str = "solvent"
    amine_name: str = ""            # espécie amina (para cálculo de loading); "" se física
    absorbed_species: list[str] = []

    @abstractmethod
    def K_value(self, species: str, T: float, P: float, x, loading: float = 0.0) -> float:
        ...

    @abstractmethod
    def heat_of_absorption(self, species: str) -> float:
        ...

    @abstractmethod
    def density(self, T: float) -> float:        # kg/m³
        ...

    @abstractmethod
    def viscosity(self, T: float) -> float:      # Pa·s
        ...

    @abstractmethod
    def cp_liquid(self, T: float) -> float:      # J/(mol·K)
        ...

    @abstractmethod
    def molar_mass_liquid(self) -> float:         # kg/mol (média fase líquida)
        ...

    def is_absorbed(self, species: str) -> bool:
        return species in self.absorbed_species


__all__ = ["Solvent"]
