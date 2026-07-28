"""Tratamento leve de unidades para o BioGasSim.

Foco em conversão explícita para SI nos limites das APIs, sem a dependência de
uma biblioteca externa (pint). O design favorece clareza: uma ``Quantity``
carrega valor + unidade; ``to_si`` devolve o valor em unidades SI canônicas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .constants import (
    ATM_TO_PA, BAR_TO_PA, KPA_TO_PA, PSI_TO_PA, C_TO_K,
    KWH_TO_J, KCAL_TO_J, MMHG_TO_PA,
)

# Unidades de pressão -> Pascal
_PRESSURE: Dict[str, float] = {
    "Pa": 1.0, "kPa": KPA_TO_PA, "MPa": 1.0e6, "bar": BAR_TO_PA,
    "atm": ATM_TO_PA, "psi": PSI_TO_PA, "mmHg": MMHG_TO_PA,
}
# Unidades de temperatura -> Kelvin
_TEMPERATURE: Dict[str, float] = {
    "K": 0.0, "C": C_TO_K, "Celsius": C_TO_K,
}
# Unidades de energia -> Joule
_ENERGY: Dict[str, float] = {
    "J": 1.0, "kJ": 1.0e3, "MJ": 1.0e6, "kWh": KWH_TO_J, "kcal": KCAL_TO_J,
}
# Unidades de comprimento -> metro
_LENGTH: Dict[str, float] = {
    "m": 1.0, "cm": 1.0e-2, "mm": 1.0e-3, "in": 0.0254, "ft": 0.3048,
}
# Unidades de vazão mássica -> kg/s; mol/s já é SI-base para molar
_MASSFLOW: Dict[str, float] = {
    "kg/s": 1.0, "kg/h": 1.0 / 3600.0, "t/h": 1.0e3 / 3600.0,
}

_REGISTRY = {
    "pressure": _PRESSURE,
    "temperature": _TEMPERATURE,
    "energy": _ENERGY,
    "length": _LENGTH,
    "massflow": _MASSFLOW,
}


@dataclass(frozen=True)
class Quantity:
    """Um valor acompanhado de sua unidade (não dimensional por padrão)."""
    value: float
    unit: str = ""

    def to_si(self, kind: str) -> float:
        """Converte para a unidade SI canônica da categoria ``kind``.

        Para temperatura, ``kind='temperature'`` devolve Kelvin; pressão devolve
        Pascal; energia devolve Joule; comprimento devolve metro; massa devolve
        kg/s.
        """
        if self.unit == "":
            return self.value
        table = _REGISTRY.get(kind)
        if table is None:
            raise ValueError(f"Categoria de unidade desconhecida: {kind}")
        if self.unit not in table:
            raise ValueError(f"Unidade '{self.unit}' não suportada para {kind}")
        factor = table[self.unit]
        # temperatura tem offset (°C -> K) e não apenas fator
        if kind == "temperature":
            return self.value + factor
        return self.value * factor


def convert(value: float, unit_from: str, kind: str) -> float:
    """Atalho: converte ``value`` em ``unit_from`` para a unidade SI de ``kind``."""
    return Quantity(value, unit_from).to_si(kind)


__all__ = ["Quantity", "convert"]