"""Constantes físicas e de engenharia usadas em todo o BioGasSim.

Todas as unidades são SI, salvo anotação explícita. Quando um valor for obtido
de uma referência tabular, a fonte é citada em comentário para validação.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# Constantes universais
# --------------------------------------------------------------------------- #
R_J_MOL_K: float = 8.314462618            # J/(mol·K)  -- constante universal dos gases
R_KPA_M3_MOL_K: float = 8.314462618e-3    # kPa·m³/(mol·K) -- conveniente para volumes
R_L_BAR_MOL_K: float = 8.314462618e-2     # L·bar/(mol·K)
R_CAL_MOL_K: float = 1.987204258          # cal/(mol·K)

T_STD_K: float = 273.15                   # 0 °C em Kelvin
P_STD_PA: float = 101325.0                # 1 atm em Pascal
G_STD: float = 9.80665                     # m/s²

# --------------------------------------------------------------------------- #
# Conversões de unidades comuns (fator multiplicativo -> SI)
# --------------------------------------------------------------------------- #
ATM_TO_PA: float = 101325.0
BAR_TO_PA: float = 1.0e5
PSI_TO_PA: float = 6894.757293168
KPA_TO_PA: float = 1.0e3
MMHG_TO_PA: float = 133.322387415

C_TO_K: float = 273.15
KCAL_TO_J: float = 4184.0
KWH_TO_J: float = 3.6e6
KWH_TO_KJ: float = 3600.0

# --------------------------------------------------------------------------- #
# Massas molares (kg/mol) -- NIST / DIPPR
# --------------------------------------------------------------------------- #
MM = {
    "CH4": 0.016043,
    "CO2": 0.044010,
    "H2O": 0.018015,
    "N2": 0.028014,
    "O2": 0.031999,
    "H2S": 0.034086,
    "MEA": 0.061088,    # monoetanolamina
    "DEA": 0.105140,    # dietanolamina
    "MDEA": 0.119165,   # metildietanolamina
    # sólidos usados na estequiometria do iron sponge (NIST)
    "S": 0.032065,      # enxofre elemental (depositado no leito)
    "Fe2O3": 0.159687,  # óxido de ferro (III) -- base do meio hidratado
}

# --------------------------------------------------------------------------- #
# Constantes de validação (valores de referência da literatura)
# --------------------------------------------------------------------------- #
# Solubilidade de CO2 em água a 25 °C: ~0.034 mol/(L·atm) (Sander 2015 -> Hcp).
# Usada como sanity check nos testes de Henry.
REF_CO2_HENRY_WATER_25C_MOL_LATM: float = 0.034  # mol/(L·atm)

__all__ = [
    "R_J_MOL_K", "R_KPA_M3_MOL_K", "R_L_BAR_MOL_K", "R_CAL_MOL_K",
    "T_STD_K", "P_STD_PA", "G_STD",
    "ATM_TO_PA", "BAR_TO_PA", "PSI_TO_PA", "KPA_TO_PA", "MMHG_TO_PA",
    "C_TO_K", "KCAL_TO_J", "KWH_TO_J", "KWH_TO_KJ",
    "MM", "REF_CO2_HENRY_WATER_25C_MOL_LATM",
]
