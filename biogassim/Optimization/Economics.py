"""Análise econômica simplificada de upgrading (CAPEX/OPEX)."""
from __future__ import annotations

from dataclasses import dataclass

# Custos de referência (valores típicos, USD) -- ajustar para a região.
ELEC_PRICE = 0.10        # USD/kWh
THERMAL_PRICE = 0.04     # USD/kWh térmico
WATER_PRICE = 0.5        # USD/m³
MEA_PRICE = 1500.0       # USD/t
STEAM_PRICE = 0.02       # USD/kWh (vapor)


@dataclass
class Economics:
    capex_usd: float = 0.0
    opex_usd_yr: float = 0.0
    specific_cost_usd_per_nm3: float = 0.0
    co2_avoided_t_per_yr: float = 0.0
    notes: str = ""

    @classmethod
    def from_process(cls, total_kw: float, biometane_nm3h: float,
                     water_m3h: float = 0.0, solvent_kg_h: float = 0.0,
                     thermal_kw: float = 0.0, capex_usd: float = 0.0,
                     co2_avoided_kg_h: float = 0.0) -> "Economics":
        hours = 8000.0
        opex_elec = total_kw * hours * ELEC_PRICE
        opex_therm = thermal_kw * hours * THERMAL_PRICE
        opex_water = water_m3h * hours * WATER_PRICE
        opex_solvent = solvent_kg_h / 1000.0 * hours * MEA_PRICE
        opex = opex_elec + opex_therm + opex_water + opex_solvent
        nm3_yr = biometane_nm3h * hours
        spec = opex / nm3_yr if nm3_yr > 0 else 0.0
        co2_t = co2_avoided_kg_h * hours / 1000.0
        return cls(capex_usd=capex_usd, opex_usd_yr=opex,
                   specific_cost_usd_per_nm3=spec,
                   co2_avoided_t_per_yr=co2_t)


__all__ = ["Economics"]