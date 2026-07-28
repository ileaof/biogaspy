"""Classes base de unidades: Stream (corrente) e Result."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

import numpy as np


@dataclass
class Stream:
    """Corrente de processo multicomponente."""
    species: List[str]
    flow: float                       # vazão total (mol/s)
    z: np.ndarray                     # frações molares (mesma ordem de species)
    T: float                          # K
    P: float                          # Pa
    phase: str = "vapor"              # "vapor" | "liquid" | "mixed"

    def __post_init__(self) -> None:
        self.z = np.asarray(self.z, dtype=float)
        s = self.z.sum()
        if s > 0:
            self.z = self.z / s
        else:
            self.z = np.zeros_like(self.z)

    @classmethod
    def make(cls, species: Sequence[str], z: Sequence[float], flow: float,
             T: float, P: float, phase: str = "vapor") -> "Stream":
        return cls(list(species), float(flow), np.asarray(z, dtype=float), T, P, phase)

    def component_flow(self, i: int) -> float:
        return float(self.flow * self.z[i])

    def copy(self) -> "Stream":
        return Stream(list(self.species), self.flow, self.z.copy(), self.T, self.P, self.phase)


@dataclass
class UnitResult:
    """Resultado genérico de uma unidade."""
    converged: bool
    iterations: int
    message: str = ""
    extra: dict = field(default_factory=dict)


__all__ = ["Stream", "UnitResult"]