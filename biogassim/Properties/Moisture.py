"""Água no gás: pressão de vapor, ponto de orvalho e conteúdo de umidade.

Funções usadas em três lugares:
  * correção de Poynting no equilíbrio de Henry (``Thermodynamics.Henry``);
  * ponto de orvalho da água e conteúdo mg/Nm³ no gás tratado
    (``cases._treated_gas_quality``, ``comparison``);
  * especificação e dimensionamento energético do secador
    (``UnitOperations.Dryer``).

Referências:
  * pressão de vapor: Buck (1996), válida --45..+60 °C com ~0,2 % de desvio,
    extendida a 100 °C com <1 % (tabela de Psat: 1403/2339/4246/101325 Pa a
    12/20/30/100 °C).
  * conteúdo mg/Nm³: volume normal 22.414 Nm³/kmol (0 °C, 101325 Pa).
"""
from __future__ import annotations

import numpy as np

from ..Core.constants import ATM_TO_PA

_P0 = ATM_TO_PA          # Pa, pressão normal
_T0 = 273.15             # K, temperatura normal (ISO usa 0 °C)
_MM_H2O = 0.018015       # kg/mol


def water_p_sat(T: float) -> float:
    """Pressão de vapor da água (Pa) -- Magnus-Tetens (Buck 1996, fase líquida).

    ``T`` em Kelvin. Válida ~233..373 K. Ex.: psat(285.15)=1403,
    psat(293.15)=2339, psat(303.15)=4246, psat(373.15)~1.04e5 Pa.
    """
    t = float(np.clip(T, 233.0, 373.15)) - 273.15
    return float(611.2 * np.exp(17.625 * t / (t + 243.04)))


def dew_point_H2O(y_H2O: float, P: float) -> float:
    """Ponto de orvalho da água (K) para fração molar ``y_H2O`` e pressão ``P``.

    Resolve y_H2O · P = psat(T): inverte a equação de Magnus. Se y_H2O·P ≥
    psat(100 °C), retorna 373.15 (gás saturado acima de 1 atm -- a condensação
    começaria acima do intervalo de validade da correlação).
    """
    if not (0.0 < y_H2O < 1.0) or P <= 0.0:
        return float("nan")
    p = min(y_H2O * P, water_p_sat(373.15))
    r = np.log(p / 611.2)
    return float(243.12 * r / (17.62 - r) + 273.15)


def water_content_mg_per_nm3(y_H2O: float, basis: str = "wet") -> float:
    """Conteúdo de água (mg/Nm³) para fração molar ``y_H2O`` no gás úmido.

    ``basis="wet"``: volume normal do gás ÚMIDO (default -- é o que medidores
    de umidade reportam). ``basis="dry"``: por Nm³ do gás SECO
    (y_H2O/(1-y_H2O) na base úmida).
    """
    if not (0.0 <= y_H2O < 1.0):
        return float("nan")
    if basis == "dry":
        y_H2O = y_H2O / max(1.0 - y_H2O, 1e-12)
    mol_per_nm3 = _P0 / (8.314462618 * _T0)           # 44.615 mol/Nm³
    n_h2o = y_H2O * mol_per_nm3                       # mol H2O per Nm³ (wet)
    return float(n_h2o * _MM_H2O * 1.0e6)             # kg -> mg


def y_from_water_content(mg_per_nm3: float) -> float:
    """Fração molar de H2O correspondente a um conteúdo mg/Nm³ (base úmida)."""
    mol_per_nm3 = _P0 / (8.314462618 * _T0)
    return float(mg_per_nm3 * 1.0e-6 / _MM_H2O / mol_per_nm3)


__all__ = ["water_p_sat", "dew_point_H2O", "water_content_mg_per_nm3",
           "y_from_water_content"]
