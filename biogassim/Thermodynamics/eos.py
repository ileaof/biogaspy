"""Base de equações de estado cúbicas (van der Waals generalizada).

As subclasses Peng-Robinson e SRK fornecem:
  - ``a_c(Tc,Pc)`` e ``b(Tc,Pc)`` dos componentes puros;
  - ``alpha(T, omega)`` dependente da temperatura;
  - ``cubic_coeffs(A, B)`` -> coeficientes [1, c2, c1, c0] da cúbica em Z;
  - ``ln_phi_term(A, B, Z, ...)`` -> termo logarítmico de ln φ_i.

A base resolve a cúbica, escolhe Z (líquido/vapor) e calcula φ_i.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ..Core.constants import R_J_MOL_K
from ..Properties.components import Component


@dataclass
class EOSResult:
    Z: float
    phi: np.ndarray            # coef. de fugacidade por componente
    phase: str                 # "liquid" | "vapor"


class CubicEOS(ABC):
    """Equação de estado cúbica genérica com regras de mistura quadráticas."""

    def __init__(self, components: Sequence[Component], kij: np.ndarray | None = None):
        self.components = list(components)
        self.n = len(components)
        if kij is None:
            kij = np.zeros((self.n, self.n))
        self.kij = np.asarray(kij, dtype=float)
        self.Tc = np.array([c.Tc for c in components])
        self.Pc = np.array([c.Pc for c in components])
        self.omega = np.array([c.omega for c in components])
        # parâmetros puros de atração (sem alpha) e covolume
        self.ac = np.array([self.a_c(c.Tc, c.Pc) for c in components])
        self.bi = np.array([self.b(c.Tc, c.Pc) for c in components])

    # ---- parâmetros puros (override nas subclasses) ----------------------- #
    @abstractmethod
    def a_c(self, Tc: float, Pc: float) -> float:
        """Coeficiente de atração crítico a_c."""

    @abstractmethod
    def b(self, Tc: float, Pc: float) -> float:
        """Covolume puro b."""

    @abstractmethod
    def alpha(self, T: float) -> np.ndarray:
        """α_i(T) para cada componente (vetor)."""

    @abstractmethod
    def cubic_coeffs(self, A: float, B: float) -> np.ndarray:
        """Coeficientes [1, c2, c1, c0] da cúbica em Z."""

    @abstractmethod
    def ln_phi(self, A: float, B: float, Z: float, z: np.ndarray,
               ai: np.ndarray, am: float, bm: float) -> np.ndarray:
        """ln φ_i para todos os componentes."""

    # ---- regras de mistura ------------------------------------------------ #
    def ai_vector(self, T: float) -> np.ndarray:
        return self.ac * self.alpha(T)

    def amix(self, T: float, z: np.ndarray) -> float:
        ai = self.ai_vector(T)
        am = 0.0
        for i in range(self.n):
            for j in range(self.n):
                am += z[i] * z[j] * np.sqrt(ai[i] * ai[j]) * (1.0 - self.kij[i, j])
        return float(am)

    def bmix(self, z: np.ndarray) -> float:
        return float(np.sum(z * self.bi))

    # ---- núcleo ----------------------------------------------------------- #
    def real_roots(self, A: float, B: float) -> np.ndarray:
        poly = self.cubic_coeffs(A, B)
        roots = np.roots(poly)
        return np.real(roots[np.isreal(roots)])

    def phase_state(self, T: float, P: float, z: np.ndarray) -> str:
        """Classifica a mistura: 'vapor', 'liquid' ou 'two-phase'.

        Baseado no número de raízes reais da cúbica. Uma única raiz -> fase
        única (vapor se Z grande, líquido se Z pequeno). Três raízes ->
        bifásico.
        """
        z = np.asarray(z, dtype=float)
        am = self.amix(T, z)
        bm = self.bmix(z)
        A = am * P / (R_J_MOL_K * T) ** 2
        B = bm * P / (R_J_MOL_K * T)
        real = self.real_roots(A, B)
        if real.size < 3:
            Z = float(real[0]) if real.size == 1 else float(np.max(real))
            return "vapor" if Z > 0.4 else "liquid"
        return "two-phase"

    def solve_Z(self, A: float, B: float, phase: str) -> float:
        real = self.real_roots(A, B)
        if real.size == 0:
            return B
        if real.size == 1:
            return float(real[0])
        Zv, Zl = float(np.max(real)), float(np.min(real))
        # validação termodinâmica: vapor e líquido devem satisfazer Z > B
        if Zl <= B:
            return Zv
        return Zv if phase == "vapor" else Zl

    def Z_and_phi(self, T: float, P: float, z: np.ndarray, phase: str = "vapor") -> EOSResult:
        z = np.asarray(z, dtype=float)
        am = self.amix(T, z)
        bm = self.bmix(z)
        A = am * P / (R_J_MOL_K * T) ** 2
        B = bm * P / (R_J_MOL_K * T)
        Z = self.solve_Z(A, B, phase)
        ai = self.ai_vector(T)
        phi = np.exp(self.ln_phi(A, B, Z, z, ai, am, bm))
        return EOSResult(Z=Z, phi=phi, phase=phase)

    def fugacity(self, T: float, P: float, z: np.ndarray, phase: str = "vapor") -> np.ndarray:
        r = self.Z_and_phi(T, P, z, phase=phase)
        return z * r.phi * P

    def K_values(self, T: float, P: float, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """K_i = φ_i^L / φ_i^V (equilíbrio de fases)."""
        phil = self.Z_and_phi(T, P, x, phase="liquid").phi
        phiv = self.Z_and_phi(T, P, y, phase="vapor").phi
        return phil / np.where(phiv == 0, 1e-12, phiv)


__all__ = ["CubicEOS", "EOSResult"]
