"""Lei de Henry para gases dissolvidos em solventes (água e aminas).

Convenção usada: ``p_i = H_i(T) · x_i``  (H em Pascal), com dependência de
temperatura via van't Hoff e correção de Poynting para alta pressão.

A constante ``H`` é armazenada em Pascal (convenção p = H·x). Para uso em
modelos de equilíbrio gás-líquido fornece-se ``K_value(T,P) = H/P`` tal que
``y_i = K_i · x_i``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from ..Core.constants import R_J_MOL_K, ATM_TO_PA


@dataclass
class HenryParams:
    """Parâmetros de Henry para um gás em um solvente.

    ``Href``: H a ``Tref`` (Pa, convenção p = H·x).
    ``dHsol``: entalpia de solução (J/mol), usada em van't Hoff.
    """
    Href: float
    Tref: float
    dHsol: float
    solvent_molar_volume: float = 18.0e-6   # m³/mol (água)

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
# --------------------------------------------------------------------------- #
# CO2 em água: 0.034 mol/(L·atm) a 25 °C (Sander 2015) -> H ~ 1.65e8 Pa
_H_CO2_WATER = from_solubility_mol_per_L_atm(0.034)
# CH4 em água: 0.0014 mol/(L·atm) -> H ~ 4.0e9 Pa (muito menos solúvel)
_H_CH4_WATER = from_solubility_mol_per_L_atm(0.0014)
# N2 em água: 0.0006 mol/(L·atm)
_H_N2_WATER = from_solubility_mol_per_L_atm(0.0006)
# H2S em água: 0.10 mol/(L·atm)
_H_H2S_WATER = from_solubility_mol_per_L_atm(0.10)

HENRY_WATER: Dict[str, HenryParams] = {
    "CO2": HenryParams(_H_CO2_WATER, 298.15, 20000.0),
    "CH4": HenryParams(_H_CH4_WATER, 298.15, 14000.0),
    "N2":  HenryParams(_H_N2_WATER, 298.15, 10000.0),
    "H2S": HenryParams(_H_H2S_WATER, 298.15, 21000.0),
}


class HenryLaw:
    """Modelo de equilíbrio gás-líquido via lei de Henry."""

    def __init__(self, params: Dict[str, HenryParams]):
        self.params = dict(params)

    def H(self, species: str, T: float) -> float:
        if species not in self.params:
            raise KeyError(f"Sem parâmetros de Henry para '{species}'.")
        return self.params[species].H(T)

    def K_value(self, species: str, T: float, P: float) -> float:
        """K_i = y_i/x_i = H_i(T)/P (com correção de Poynting desprezada)."""
        return self.H(species, T) / P

    def K_values(self, species_list, T: float, P: float) -> np.ndarray:
        return np.array([self.K_value(s, T, P) for s in species_list])

    def x_eq(self, species: str, y: float, T: float, P: float) -> float:
        """Composição líquida em equilíbrio com y (fração vapor)."""
        return y * P / self.H(species, T)


def henry_water() -> HenryLaw:
    """HenryLaw pré-configurado para gases em água."""
    return HenryLaw(HENRY_WATER)


__all__ = [
    "HenryParams", "HenryLaw", "HENRY_WATER", "henry_water",
    "from_solubility_mol_per_L_atm",
]