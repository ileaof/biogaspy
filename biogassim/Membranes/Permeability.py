"""Permeabilidades de membranas para CO2/CH4 (solução-difusão)."""
from __future__ import annotations

from dataclasses import dataclass

# Permeabilidades em Barrer (1 Barrer = 3.35e-16 mol/(m·s·Pa))
BARRER = 3.35e-16


@dataclass
class MembraneMaterial:
    name: str
    permeability: dict[str, float]   # Barrer
    selectivity_notes: str = ""

    def perm_si(self, species: str) -> float:
        """Permeabilidade em mol/(m·s·Pa)."""
        return float(self.permeability.get(species, 1.0) * BARRER)


MEMBRANES: dict[str, MembraneMaterial] = {
    "CelluloseAcetate": MembraneMaterial(
        "Cellulose Acetate", {"CO2": 6.0, "CH4": 0.2, "N2": 0.3},
        "α(CO2/CH4) ~ 30"),
    "Polyimide": MembraneMaterial(
        "Polyimide", {"CO2": 2.5, "CH4": 0.06, "N2": 0.15},
        "α(CO2/CH4) ~ 40"),
    "Polysulfone": MembraneMaterial(
        "Polysulfone", {"CO2": 4.0, "CH4": 0.12, "N2": 0.2},
        "α ~ 33"),
    "Silica": MembraneMaterial(
        "Microporous Silica", {"CO2": 200.0, "CH4": 8.0, "N2": 10.0},
        "α ~ 25 (alta permeabilidade)"),
}


def selectivity(material: str, a: str, b: str) -> float:
    m = MEMBRANES[material]
    return float(m.permeability[a] / m.permeability[b])


__all__ = ["MembraneMaterial", "MEMBRANES", "selectivity", "BARRER"]
