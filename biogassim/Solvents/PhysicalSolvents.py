"""Solventes físicos: Selexol (DEPG / dimetil éter de polietilenoglicol) e Rectisol (metanol).

Modelo via lei de Henry com constantes próprias: K = H/P, H(T) via van't Hoff
(``H = Href·exp(-dH/R·(1/T-1/298))``, dH>0 exotérmico -> T menor -> H menor ->
mais solúvel, convenção consistente com ``Thermodynamics.Henry``).

**Calibrado contra dados de solubilidade reais** (Href a 298,15 K):

- **Selexol (DEPG)** -- Henni, Tontiwachwuthikul & Chakma (2005), *Can. J. Chem.
  Eng.* 83(2), 358 (CO2 e CH4 em éteres de PEG); Burr & Lyddon (Bryan Research),
  "A Comparison of Physical Solvents for Acid Gas Removal" (seletividades
  relativas H2S/CO2 ~8,8 e CH4/CO2 ~0,066):
    * H(CO2) = 3,0 MPa  -> Href = 3,0e6 Pa
    * H(CH4) = 38 MPa   -> Href = 3,8e7 Pa
    * H(H2S) = 0,34 MPa (3,0/8,82) -> Href = 3,4e5 Pa
    * H(N2)  ~ 200 MPa  (relativo 0,015) -> Href = 2,0e8 Pa  [estimado]
  dH estimados a partir da tendência de T de Henni (25/40/60 °C): CO2 mais
  exotérmico que CH4; valores ~15-20 kJ/mol.

- **Rectisol (metanol)** -- Décultot et al. (2019), *J. Chem. Thermodyn.* 138,
  67 (CO2 em metanol, série 283-313 K); Leu & Robinson (1992), *Fluid Phase
  Equilib.* 72, 163 (H2S em metanol a 298 K); Brunner et al. (1987) para CH4:
    * H(CO2) = 142 MPa a 298 K -> Href = 1,42e8 Pa, **dH = 15 kJ/mol regressado
      da série de Décultot** (reproduz 103 MPa @283 K, 185 MPa @313 K, <4% desvio)
    * H(H2S) = 5 MPa a 298 K -> Href = 5,0e6 Pa, dH = 18 kJ/mol [estimado]
    * H(CH4) ~ 125 MPa a 298 K -> Href = 1,25e8 Pa, dH = 5 kJ/mol [estimado,
      a partir de Chen et al. 2023 (sim.) + Brunner]
    * H(N2)  ~ 300 MPa -> Href = 3,0e8 Pa, dH = 5 kJ/mol [estimado]

Valores marcados [estimado] carecem de regressão direta (dados de T indisponíveis
livremente); são fisicamente coerentes (ordem de solubilidade H2S > CO2 > CH4 >
N2) e validados nos testes de seletividade. Ver ``tests/test_solvents.py``
(seletividades) e ``tests/test_validation.py`` (Href absolutos vs Décultot/Henni).
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

    # Href [Pa] @ 298,15 K, dH [J/mol] (dH>0 exotérmico); subclasses definem
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

    def henry(self, species, T) -> float:
        """Constante de Henry H [Pa] (P·y = H·x) -- útil p/ validação direta."""
        Href = self.href.get(species, 1e9)
        dH = self.dh.get(species, 15000.0)
        return float(Href * np.exp(-dH / R_J_MOL_K * (1.0 / T - 1.0 / 298.15)))

    def heat_of_absorption(self, species: str) -> float:
        return {"CO2": 15000.0, "CH4": 12000.0, "H2S": 19000.0, "N2": 9000.0}.get(species, 12000.0)

    def density(self, T): return float(self.rho_ref * (1 - 7e-4 * (T - 298.15)))
    def viscosity(self, T): return float(self.mu_ref * np.exp(1500.0 * (1.0 / T - 1.0 / 298.15)))
    def cp_liquid(self, T): return float(self.cp_ref * self.mm_liquid)
    def molar_mass_liquid(self): return float(self.mm_liquid)


class SelexolSolvent(_PhysicalSolvent):
    """Selexol (DEPG): CO2 ~55x mais solúvel que em água a 25 °C; seletivo a H2S.

    Href calibrado vs Henni et al. (2005) e Burr & Lyddon (seletividades).
    """
    name = "Selexol"
    href = {
        "CO2": 3.0e6,      # Henni 2005: 3,0 MPa
        "CH4": 3.8e7,      # Henni 2005: 38 MPa
        "H2S": 3.4e5,      # Burr&Lyddon: H2S/CO2 = 8,82 -> 0,34 MPa
        "N2":  2.0e8,      # estimado (relativo ~0,015 -> ~200 MPa)
    }
    dh = {"CO2": 18000.0, "CH4": 14000.0, "H2S": 20000.0, "N2": 10000.0}
    mm_liquid = 0.280    # média PEG-DME
    rho_ref = 1030.0
    mu_ref = 0.005
    cp_ref = 2100.0


class RectisolSolvent(_PhysicalSolvent):
    """Rectisol: metanol a baixa T (-20 a -70 °C); alta seletividade H2S/CO2.

    Href calibrado vs Décultot (2019, CO2), Leu & Robinson (1992, H2S),
    Brunner (1987, CH4). dH(CO2)=15 kJ/mol regressado da série de Décultot.
    """
    name = "Methanol"
    href = {
        "CO2": 1.42e8,    # Décultot 2019: 142 MPa @298 K
        "CH4": 1.25e8,    # Brunner 1987 / estimado: ~125 MPa
        "H2S": 5.0e6,     # Leu & Robinson 1992: ~5 MPa @298 K
        "N2":  3.0e8,     # estimado: ~300 MPa (menos solúvel que CH4)
    }
    dh = {"CO2": 15000.0, "CH4": 5000.0, "H2S": 18000.0, "N2": 5000.0}
    mm_liquid = 0.032
    rho_ref = 790.0
    mu_ref = 0.0008
    cp_ref = 2500.0


__all__ = ["SelexolSolvent", "RectisolSolvent"]