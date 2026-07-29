"""Solvente químico: monoetanolamina (MEA) -- absorção reativa de CO2.

Dois modelos de equilíbrio para o CO2, selecionáveis via ``method``:

- ``"kent-eisenberg"`` (padrão): modelo rigoroso de especiação de
  Kent-Eisenberg (carbamato/bicarbonato/carbonato), resolve p_CO2(α,T) e
  devolve K = p_CO2/(P·x_CO2). Calibrado contra Jou, Mather & Otto (1995) /
  Aronu et al. (2011) para MEA 30% mássico.

- ``"effective"``: K efetivo dependente do carregamento
  K_eff(α) = (H/P)·(1 + A·(1 − α/α_max)), calibrado para biogás 47/53.

CH4, N2 e H2S usam solubilidade física (Henry) em ambos os modelos.
"""
from __future__ import annotations

import numpy as np

from ..Properties.Amines import (
    amine_cp,
    amine_density,
    amine_viscosity,
    heat_of_absorption,
)
from ..Properties.components import get
from .base import Solvent
from .KentEisenberg import KentEisenberg


class MEASolvent(Solvent):
    name = "MEA"
    amine_name = "MEA"
    absorbed_species: list[str] = ["CO2", "CH4", "N2", "H2S"]

    def __init__(self, w_mea: float = 0.30, alpha_max: float = 0.50,
                 enhancement: float = 120.0, H_phys: float = 1.6e8,
                 method: str = "kent-eisenberg"):
        self.w_mea = w_mea
        self.alpha_max = alpha_max
        self.A = enhancement
        self.H_phys = H_phys      # Pa (Henry físico CO2 em solução MEA, aprox.)
        self.method = method
        self._ke = KentEisenberg()

    # ------------------------------------------------------------------ #
    def _molar_density_MEA(self, T: float, x) -> float:
        """Concentração total de MEA (mol/L) a partir da fração molar x_MEA
        e da densidade molar da solução."""
        mm = self.molar_mass_liquid()                 # kg/mol
        rho = self.density(T)                         # kg/m3
        rho_molar = rho / mm / 1000.0                  # mol/L
        return float(x[self._i_mea] * rho_molar)

    def K_value(self, species, T, P, x, loading=0.0) -> float:
        if species not in self.absorbed_species:
            return 0.0
        if species == "CO2":
            return self._K_CO2(T, P, x, loading)
        # CH4, N2, H2S: solubilidade física (solubilidade baixa -> alta K)
        H_gas = {"CH4": 4.0e9, "N2": 9.0e9, "H2S": 5.6e7}.get(species, 1e9)
        return float(H_gas / P)

    def _K_CO2(self, T, P, x, loading) -> float:
        if self.method != "kent-eisenberg":
            # modelo efetivo (legado)
            H = self.H_phys * np.exp(-20000.0 / 8.314 * (1.0 / T - 1.0 / 298.15))
            alpha = loading if loading else 0.0
            cap = 1.0 + self.A * max(0.0, 1.0 - alpha / self.alpha_max)
            return float((H / P) / cap)
        # Kent-Eisenberg: p_CO2(α,T) -> K = p_CO2/(P·x_CO2)
        alpha = float(loading) if loading else 0.0
        if alpha <= 0.0:
            # solvente magro: CO2 fortemente absorvido (K -> 0)
            return 0.0
        x_co2 = float(x[self._i_co2])
        m = self._molar_density_MEA(T, x)
        pCO2 = self._ke.pCO2(alpha, T, m)
        return float(pCO2 / (P * max(x_co2, 1e-15)))

    # ------------------------------------------------------------------ #
    def set_species_context(self, species: list[str]) -> None:
        """Resolve índices de CO2 e MEA a partir da lista de espécies do
        Absorbedor. Deve ser chamado antes de K_value no modo Kent-Eisenberg.
        """
        self._species = list(species)
        self._i_co2 = species.index("CO2") if "CO2" in species else 0
        self._i_mea = (species.index(self.amine_name)
                       if self.amine_name in species else 0)

    def heat_of_absorption(self, species: str) -> float:
        if species == "CO2":
            return heat_of_absorption("MEA")     # ~85 kJ/mol
        return 15000.0

    def density(self, T: float) -> float:
        return amine_density("MEA", T, self.w_mea)

    def viscosity(self, T: float) -> float:
        return amine_viscosity("MEA", T, self.w_mea)

    def cp_liquid(self, T: float) -> float:
        # Cp molar da solução (J/(mol·K)) via Cp mássico * MM médio
        cp_mass = amine_cp("MEA", T, self.w_mea)          # J/(kg·K)
        mm = self.molar_mass_liquid()                     # kg/mol
        return float(cp_mass * mm)

    def molar_mass_liquid(self) -> float:
        # média ponderada simples (30% mássico MEA)
        mm_mea = get("MEA").MM
        mm_w = get("H2O").MM
        w = self.w_mea
        # fração mássica -> média molar
        return 1.0 / (w / mm_mea + (1 - w) / mm_w)


# contexto de espécies: preenchido pelo Absorbedor (ver set_species_context)
__all__ = ["MEASolvent"]
