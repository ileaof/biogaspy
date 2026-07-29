"""Solvente químico: DEA (dietanolamina) -- amina secundária.

Dois modelos de equilíbrio para o CO2, selecionáveis via ``method``:

- ``"kent-eisenberg"`` (padrão): modelo rigoroso de especiação Kent-Eisenberg
  (protonação + carbamato + bicarbonato/carbonato). DEA é amina secundária e
  forma carbamato (como MEA), com pKa ~8,9 e α_max ~0,5 (estequiometria 2:1).
  Constantes aparentes de literatura (Jou-Mather-Otto, 1995); pCO2(α) absoluto
  ainda não calibrado contra VLE de DEA -- validar antes de projeto.

- ``"effective"``: K efetivo dependente do carregamento (legado).

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


class DEASolvent(Solvent):
    name = "DEA"
    amine_name = "DEA"
    absorbed_species: list[str] = ["CO2", "CH4", "N2", "H2S"]

    def __init__(self, w_dea: float = 0.30, alpha_max: float = 0.50,
                 enhancement: float = 60.0, H_phys: float = 1.6e8,
                 method: str = "kent-eisenberg"):
        self.w = w_dea
        self.alpha_max = alpha_max
        self.A = enhancement
        self.H_phys = H_phys
        self.method = method
        # DEA: pKa~8,9 -> log β1~9,9 (aparente); carbamato um pouco menos estável que MEA
        self._ke = KentEisenberg(amine="DEA", log_beta1=9.9, log_beta2=4.70,
                                 dH1=-35000.0, dH2=-55000.0)

    # ------------------------------------------------------------------ #
    def _molar_density_amine(self, T: float, x) -> float:
        """Concentração total de DEA (mol/L) a partir da fração molar x_DEA."""
        mm = self.molar_mass_liquid()                  # kg/mol
        rho = self.density(T)                           # kg/m3
        rho_molar = rho / mm / 1000.0                   # mol/L
        return float(x[self._i_amine] * rho_molar)

    def K_value(self, species, T, P, x, loading=0.0) -> float:
        if species not in self.absorbed_species:
            return 0.0
        if species == "CO2":
            return self._K_CO2(T, P, x, loading)
        H_gas = {"CH4": 4.0e9, "N2": 9.0e9, "H2S": 5.6e7}.get(species, 1e9)
        return float(H_gas / P)

    def _K_CO2(self, T, P, x, loading) -> float:
        if self.method != "kent-eisenberg":
            H = self.H_phys * np.exp(-20000.0 / 8.314 * (1.0 / T - 1.0 / 298.15))
            alpha = loading if loading else 0.0
            cap = 1.0 + self.A * max(0.0, 1.0 - alpha / self.alpha_max)
            return float((H / P) / cap)
        alpha = float(loading) if loading else 0.0
        if alpha <= 0.0:
            return 0.0                        # solvente magro: forte absorção
        x_co2 = float(x[self._i_co2])
        m = self._molar_density_amine(T, x)
        pCO2 = self._ke.pCO2(alpha, T, m)
        return float(pCO2 / (P * max(x_co2, 1e-15)))

    # ------------------------------------------------------------------ #
    def set_species_context(self, species: list[str]) -> None:
        self._species = list(species)
        self._i_co2 = species.index("CO2") if "CO2" in species else 0
        self._i_amine = (species.index(self.amine_name)
                        if self.amine_name in species else 0)

    def heat_of_absorption(self, species: str) -> float:
        return heat_of_absorption("DEA") if species == "CO2" else 15000.0

    def density(self, T): return amine_density("DEA", T, self.w)
    def viscosity(self, T): return amine_viscosity("DEA", T, self.w)
    def cp_liquid(self, T): return float(amine_cp("DEA", T, self.w) * self.molar_mass_liquid())
    def molar_mass_liquid(self):
        mm_dea = get("DEA").MM
        mm_w = get("H2O").MM
        w = self.w
        return 1.0 / (w / mm_dea + (1 - w) / mm_w)


__all__ = ["DEASolvent"]
