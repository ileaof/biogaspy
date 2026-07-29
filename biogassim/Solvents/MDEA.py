"""Solvente químico: MDEA (metildietanolamina) -- amina terciária.

Dois modelos de equilíbrio para o CO2, selecionáveis via ``method``:

- ``"kent-eisenberg"`` (padrão): especiação Kent-Eisenberg com ``log_beta2 = 0``
  (sem carbamato -- amina terciária não tem N-H). O CO2 é absorvido como
  bicarbonato/carbonato, via protonação da MDEA que catalisa a hidratação do
  CO2 (rota lenta, maior seletividade CO2/H2S). α_max ~1,0 (1:1).

  **Calibrado contra Huttenhuis et al. (2007)**, 35 wt% MDEA (m = 3,05 mol/L),
  a 298,15 K e 283,15 K: regressão 2-parâmetros (log β1, ΔH1) via Nelder-Mead
  em escala log. Resultado: log β1 = 8,634 (≈ pKa da MDEA, 8,65 -- fisicamente
  limpo, a protonação da amina é o equilíbrio dominante) e ΔH1 = -41,97 kJ/mol
  (protonação exotérmica). pCO2(α) do modelo concorda com os dados dentro de
  fator ~2,4 em todo o intervalo (α 0,05-0,32) nas duas temperaturas;
  monotônico em α e crescente em T. Ver ``tests/test_validation.py``
  (HUTTENHUIS_MDEA_*K).

  Espera-se pCO2(α) > MEA/DEA (amina mais fraca) no mesmo α.

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


class MDEASolvent(Solvent):
    name = "MDEA"
    amine_name = "MDEA"
    absorbed_species: list[str] = ["CO2", "CH4", "N2", "H2S"]

    def __init__(self, w_mdea: float = 0.40, alpha_max: float = 1.0,
                 enhancement: float = 40.0, H_phys: float = 1.6e8,
                 method: str = "kent-eisenberg"):
        self.w = w_mdea
        self.alpha_max = alpha_max
        self.A = enhancement
        self.H_phys = H_phys
        self.method = method
        # MDEA calibrado vs Huttenhuis et al. (2007), 35 wt%, 298 e 283 K:
        # log β1 = 8,634 (≈ pKa 8,65), ΔH1 = -41,97 kJ/mol; SEM carbamato (β2=0)
        self._ke = KentEisenberg(amine="MDEA", log_beta1=8.634, log_beta2=0.0,
                                 dH1=-41971.0, dH2=0.0)

    # ------------------------------------------------------------------ #
    def _molar_density_amine(self, T: float, x) -> float:
        """Concentração total de MDEA (mol/L) a partir da fração molar x_MDEA."""
        mm = self.molar_mass_liquid()
        rho = self.density(T)
        rho_molar = rho / mm / 1000.0
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
            return 0.0
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
        return heat_of_absorption("MDEA") if species == "CO2" else 15000.0

    def density(self, T): return amine_density("MDEA", T, self.w)
    def viscosity(self, T): return amine_viscosity("MDEA", T, self.w)
    def cp_liquid(self, T): return float(amine_cp("MDEA", T, self.w) * self.molar_mass_liquid())
    def molar_mass_liquid(self):
        mm = get("MDEA").MM
        mm_w = get("H2O").MM
        w = self.w
        return 1.0 / (w / mm + (1 - w) / mm_w)


__all__ = ["MDEASolvent"]
