"""Balanço de energia do processo de upgrading."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..UnitOperations import CompressorResult, PumpResult


@dataclass
class EnergySummary:
    compression: float = 0.0      # kW
    pumping: float = 0.0         # kW
    regeneration: float = 0.0    # kW (reboiler do stripper, amina)
    cooling: float = 0.0         # kW
    total_kw: float = 0.0
    specific_kwh_per_nm3: float = 0.0   # kWh/Nm³ biometano
    notes: list[str] = field(default_factory=list)

    def finalize(self, biometane_nm3h: float = 1.0) -> EnergySummary:
        self.total_kw = self.compression + self.pumping + self.regeneration + self.cooling
        if biometane_nm3h > 0:
            self.specific_kwh_per_nm3 = self.total_kw / biometane_nm3h
        return self


def compression_energy(compressors: list[CompressorResult]) -> float:
    """Soma a potência de compressão (W -> kW)."""
    return float(sum(c.work for c in compressors) / 1000.0)


def pumping_energy(pumps: list[PumpResult]) -> float:
    return float(sum(p.work for p in pumps) / 1000.0)


def regeneration_energy(co2_absorbed_mols: float, specific_mj_per_kg: float = 4.0,
                        solvent_flow_mols: float = 0.0) -> float:
    """Estimativa do calor de regeneração de amina (kW).

    Baseado no calor específico de reboiler típico de MEA (~3.5-4.5 MJ/kg CO2),
    que já inclui calor de reação (reversão) + calor sensível líquido do reboiler
    (após recuperação no trocador rico-magro). ``co2_absorbed_mols`` em mol/s;
    ``specific_mj_per_kg`` em MJ/kg CO2.
    """
    co2_kg_s = co2_absorbed_mols * 0.04401
    # co2_kg_s [kg/s] * specific [MJ/kg] = MJ/s = MW; -> kW: *1000
    return float(co2_kg_s * specific_mj_per_kg * 1000.0)


__all__ = ["EnergySummary", "compression_energy", "pumping_energy",
           "regeneration_energy"]
