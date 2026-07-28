"""Banco de componentes puros do BioGasSim.

Cada componente é um ``Component`` dataclass com propriedades críticas
(DIPPR/NIST) e correlação de Cp ideal (Shomate, válida em intervalos de T).
As fontes são citadas para validação contra literatura.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np

# Constante usada para Cp em J/(mol·K) quando armazenamos Cp/R (adimensional)
from ..Core.constants import R_J_MOL_K


@dataclass
class ShomateCp:
    """Cp(T) = a + b*T + c*T²/1e3 + d*T³/1e6 + e/T²·1e5  (Shomate, J/mol·K).

    Coeficientes conforme tabelas NIST Webbook (intervalos de T específicos).
    """
    a: float
    b: float
    c: float
    d: float
    e: float
    T_low: float
    T_high: float

    def cp(self, T: float) -> float:
        T = float(T)
        # extrapolacao suave se fora do intervalo (clamp implícito no uso)
        t = T / 1000.0
        return self.a + self.b * t + self.c * t**2 + self.d * t**3 + self.e / t**2

    def enthalpy(self, T: float, T_ref: float = 298.15) -> float:
        """ΔH(T) - ΔH(T_ref) em J/mol (gás ideal) via integração de Cp."""
        # integração analítica de Cp(T) entre T_ref e T
        def integ(TT: float) -> float:
            t = TT / 1000.0
            return (self.a * t + self.b * t**2 / 2 + self.c * t**3 / 3
                    + self.d * t**4 / 4 - self.e / t)
        return 1000.0 * (integ(T) - integ(T_ref))

    def entropy(self, T: float, T_ref: float = 298.15) -> float:
        def integ(TT: float) -> float:
            t = TT / 1000.0
            return (self.a * np.log(t) + self.b * t + self.c * t**2 / 2
                    + self.d * t**3 / 3 - self.e / (2 * t**2))
        return 1000.0 * (integ(T) - integ(T_ref))


@dataclass
class Component:
    name: str
    formula: str
    MM: float                              # kg/mol
    Tc: float                              # K
    Pc: float                              # Pa
    omega: float                           # fator acêntrico
    Tb: float                              # K (ponto de ebulição a 1 atm)
    Vc: Optional[float] = None             # m³/mol
    Zc: Optional[float] = None
    cp_ideal: Optional[ShomateCp] = None
    Hvap: Optional[float] = None           # J/mol em Tb
    comment: str = ""

    def cp(self, T: float) -> float:
        if self.cp_ideal is None:
            # fallback: Cp ideal ~ constante estimada por R*(n_atoms) -- grosseiro
            return 4.0 * R_J_MOL_K
        return self.cp_ideal.cp(T)

    def ideal_enthalpy(self, T: float, T_ref: float = 298.15) -> float:
        if self.cp_ideal is None:
            return self.cp(T) * (T - T_ref)
        return self.cp_ideal.enthalpy(T, T_ref)

    def ideal_entropy(self, T: float, T_ref: float = 298.15) -> float:
        if self.cp_ideal is None:
            return self.cp(T) * np.log(T / T_ref)
        return self.cp_ideal.entropy(T, T_ref)


# --------------------------------------------------------------------------- #
# Banco de componentes
# Fontes: NIST Webbook (Shomate), DIPPR (Tc/Pc/ω), Yaws.
# --------------------------------------------------------------------------- #
_COMPONENTS: Dict[str, Component] = {
    "CH4": Component(
        name="Methane", formula="CH4", MM=0.016043,
        Tc=190.564, Pc=4.599e6, omega=0.0115, Tb=111.66,
        Vc=9.86e-5, Zc=0.286,
        cp_ideal=ShomateCp(-0.703029, 108.4773, -42.52157, 5.862788, 0.678565,
                           298.0, 1300.0),
        comment="NIST Shomate (298-1300 K). Tc/Pc de DIPPR.",
    ),
    "CO2": Component(
        name="CarbonDioxide", formula="CO2", MM=0.044010,
        Tc=304.128, Pc=7.3773e6, omega=0.22394, Tb=194.67,  # sublimação ~194K; Tb a 5.18 bar
        Vc=9.4e-5, Zc=0.274,
        cp_ideal=ShomateCp(29.67806, -98.93171, 105.0, -7.330097, 0.018202,
                           298.0, 1200.0),
        comment="NIST Shomate. CO2 é supercrítico acima de 31 °C.",
    ),
    "H2O": Component(
        name="Water", formula="H2O", MM=0.018015,
        Tc=647.096, Pc=22.064e6, omega=0.344, Tb=373.15,
        Vc=5.6e-5, Zc=0.229,
        cp_ideal=ShomateCp(30.09200, 6.832514, 6.793435, -2.534480, 0.082139,
                           500.0, 1700.0),  # fase vapor
        Hvap=40660.0,
        comment="Vapor (NIST). Para líquido usar Cp_liq ~ 75.3 J/mol·K.",
    ),
    "N2": Component(
        name="Nitrogen", formula="N2", MM=0.028014,
        Tc=126.192, Pc=3.3958e6, omega=0.0372, Tb=77.36,
        Vc=9.0e-5, Zc=0.289,
        cp_ideal=ShomateCp(19.50583, 19.88705, -8.598535, 1.369784, 0.527601,
                           298.0, 6000.0),
    ),
    "O2": Component(
        name="Oxygen", formula="O2", MM=0.031999,
        Tc=154.581, Pc=5.043e6, omega=0.0222, Tb=90.19,
        cp_ideal=ShomateCp(30.03235, 8.772924, -3.988133, 0.788313, -0.741599,
                           298.0, 6000.0),
    ),
    "H2S": Component(
        name="HydrogenSulfide", formula="H2S", MM=0.034086,
        Tc=373.53, Pc=8.962e6, omega=0.0942, Tb=212.85,
        cp_ideal=ShomateCp(31.020, 5.012, -1.617, 0.321, -0.602, 298.0, 1500.0),
        comment="Coeficientes aproximados (Yaws). Validar para uso final.",
    ),
    "MEA": Component(
        name="Monoethanolamine", formula="C2H7NO", MM=0.061088,
        Tc=638.0, Pc=8.0e6, omega=0.469, Tb=443.0,
        Hvap=52000.0,
        comment="Tc/Pc estimados (Kohl & Nielsen / Yaws). Validar.",
    ),
    "DEA": Component(
        name="Diethanolamine", formula="C4H11NO2", MM=0.105140,
        Tc=738.0, Pc=6.5e6, omega=0.620, Tb=541.0,
        Hvap=62000.0,
        comment="Estimado. Validar.",
    ),
    "MDEA": Component(
        name="Methyldiethanolamine", formula="C5H13NO2", MM=0.119165,
        Tc=721.0, Pc=6.0e6, omega=0.580, Tb=516.0,
        Hvap=58000.0,
        comment="Estimado. Validar.",
    ),
}


def get(name: str) -> Component:
    """Recupera componente por fórmula (CH4, CO2, ...)."""
    if name not in _COMPONENTS:
        raise KeyError(f"Componente '{name}' não cadastrado.")
    return _COMPONENTS[name]


def all_components() -> Dict[str, Component]:
    return dict(_COMPONENTS)


__all__ = ["Component", "ShomateCp", "get", "all_components"]