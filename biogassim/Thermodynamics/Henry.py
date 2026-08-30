"""Lei de Henry para gases dissolvidos em solventes (água e aminas).

Convenção usada: ``p_i = H_i(T) · x_i``  (H em Pascal), com dependência de
temperatura via van't Hoff e correção de Poynting para alta pressão.

A constante ``H`` é armazenada em Pascal (convenção p = H·x). Para uso em
modelos de equilíbrio gás-líquido fornece-se ``K_value(T,P) = H/P`` tal que
``y_i = K_i · x_i``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..Core.constants import ATM_TO_PA, R_J_MOL_K


@dataclass
class HenryParams:
    """Parâmetros de Henry para um gás em um solvente.

    ``Href``: H a ``Tref`` (Pa, convenção p = H·x).
    ``dHsol``: entalpia de solução (J/mol), usada em van't Hoff.
    ``v_liq``: volume molar parcial do gás dissolvido no solvente (m³/mol),
    usado na correção de Poynting (0 desativa -- default nos cálculos).
    """
    Href: float
    Tref: float
    dHsol: float
    solvent_molar_volume: float = 18.0e-6   # m³/mol (água)
    v_liq: float = 0.0                       # m³/mol (Poynting; 0 = ignora)

    def H(self, T: float) -> float:
        """H(T) [Pa] via van't Hoff: ln(H) = ln(Href) - dHsol/R (1/T - 1/Tref).

        Convenção: dHsol > 0 para dissolução exotérmica (CO2 em água), de modo
        que T menor -> H menor -> mais solúvel (comportamento observado).
        """
        return float(self.Href * np.exp(-self.dHsol / R_J_MOL_K * (1.0 / T - 1.0 / self.Tref)))


# --------------------------------------------------------------------------- #
# Conversão auxiliar: a partir da solubilidade c = Hcp·p (mol/(L·atm))
# --------------------------------------------------------------------------- #
def from_solubility_mol_per_L_atm(hcp: float, Vm: float = 18.0e-6) -> float:
    """Converte solubilidade (mol/(L·atm)) em H [Pa] (p = H·x)."""
    hcp_si = hcp / ATM_TO_PA * 1000.0   # -> mol/(m³·Pa)
    # x = hcp_si * Vm * p  =>  H = p/x = 1/(hcp_si * Vm)
    return float(1.0 / (hcp_si * Vm))


# --------------------------------------------------------------------------- #
# Banco de parâmetros de Henry (valores de referência a 298 K).
# H obtida da solubilidade tabulada e convertida via from_solubility_mol_per_L_atm.
# v_liq = volume molar parcial a diluição infinita em água, 25 °C (cm³/mol ->
# m³/mol; Moore et al. 1972 / Battino 1984 / Handa & Benson) para Poynting.
# --------------------------------------------------------------------------- #
# CO2 em água: 0.034 mol/(L·atm) a 25 °C (Sander 2015) -> H ~ 1.65e8 Pa
_H_CO2_WATER = from_solubility_mol_per_L_atm(0.034)
# CH4 em água: 0.0014 mol/(L·atm) -> H ~ 4.0e9 Pa (muito menos solúvel)
_H_CH4_WATER = from_solubility_mol_per_L_atm(0.0014)
# N2 em água: 0.0006 mol/(L·atm)
_H_N2_WATER = from_solubility_mol_per_L_atm(0.0006)
# H2S em água: 0.10 mol/(L·atm)
_H_H2S_WATER = from_solubility_mol_per_L_atm(0.10)
# Solubilidades adicionais (Sander 2015, mol/(L·atm) a 25 °C):
_H_O2_WATER = from_solubility_mol_per_L_atm(0.0013)     # O2 (pouco solúvel)
_H_H2_WATER = from_solubility_mol_per_L_atm(0.00078)    # H2 (pouco solúvel)
_H_AR_WATER = from_solubility_mol_per_L_atm(0.0014)     # Ar (inerte)
_H_CO_WATER = from_solubility_mol_per_L_atm(0.00095)    # CO
_H_NH3_WATER = from_solubility_mol_per_L_atm(60.0)      # NH3 (muito solúvel)

HENRY_WATER: dict[str, HenryParams] = {
    "CO2": HenryParams(_H_CO2_WATER, 298.15, 20000.0, v_liq=34.0e-6),
    "CH4": HenryParams(_H_CH4_WATER, 298.15, 14000.0, v_liq=37.5e-6),
    "N2":  HenryParams(_H_N2_WATER, 298.15, 10000.0, v_liq=40.5e-6),
    "H2S": HenryParams(_H_H2S_WATER, 298.15, 21000.0, v_liq=32.0e-6),
    "O2":  HenryParams(_H_O2_WATER, 298.15, 12000.0, v_liq=31.0e-6),
    "H2":  HenryParams(_H_H2_WATER, 298.15, 4000.0, v_liq=26.2e-6),
    "Ar":  HenryParams(_H_AR_WATER, 298.15, 12000.0, v_liq=32.0e-6),
    "CO":  HenryParams(_H_CO_WATER, 298.15, 12000.0, v_liq=33.0e-6),
    "NH3": HenryParams(_H_NH3_WATER, 298.15, 34000.0, v_liq=24.0e-6),   # muito exotérmica
}


class HenryLaw:
    """Modelo de equilíbrio gás-líquido via lei de Henry."""

    def __init__(self, params: dict[str, HenryParams]):
        self.params = dict(params)

    def H(self, species: str, T: float) -> float:
        if species not in self.params:
            raise KeyError(f"Sem parâmetros de Henry para '{species}'.")
        return self.params[species].H(T)

    def poynting_factor(self, species: str, T: float, P: float,
                        solvent: str = "H2O") -> float:
        """Correção de Poynting na fuga do líquido: exp(v̄_i·(P - P_sat,slv)/(RT)).

        Corrige a fuga do gás dissolvido a P total ≠ P_sat do solvente
        (Prausnitz et al., *Molecular Thermodynamics* §10; padrão para
        equilíbrio de gases pouco solúveis em alta pressão). Com ``v_liq = 0``
        (ou espécie sem parâmetro) retorna 1.0 -- equilíbrio H·x puro.
        Import de ``Properties.Moisture`` é lazy para evitar ciclo.
        """
        p_par = self.params.get(species)
        if p_par is None or p_par.v_liq <= 0.0:
            return 1.0
        from ..Properties.Moisture import water_p_sat
        psat = water_p_sat(T) if solvent == "H2O" else 0.0
        dp = max(P - psat, 0.0)
        return float(np.exp(p_par.v_liq * dp / (R_J_MOL_K * T)))

    def K_value(self, species: str, T: float, P: float,
                poynting: bool = False) -> float:
        """K_i = y_i/x_i = H_i(T)·Π_Poynt/P.

        ``poynting=True`` aplica a correção de Poynting na fuga líquida
        (efeito ~2-3 % em water scrubbing a 20 bar; mais relevante >50 bar).
        """
        K = self.H(species, T) / P
        if poynting:
            K *= self.poynting_factor(species, T, P)
        return float(K)

    def K_values(self, species_list, T: float, P: float,
                 poynting: bool = False) -> np.ndarray:
        return np.array([self.K_value(s, T, P, poynting) for s in species_list])

    def x_eq(self, species: str, y: float, T: float, P: float,
             poynting: bool = False) -> float:
        """Composição líquida em equilíbrio com y (fração vapor)."""
        return y / self.K_value(species, T, P, poynting)


def henry_water() -> HenryLaw:
    """HenryLaw pré-configurado para gases em água."""
    return HenryLaw(HENRY_WATER)


__all__ = [
    "HenryParams", "HenryLaw", "HENRY_WATER", "henry_water",
    "from_solubility_mol_per_L_atm",
]
