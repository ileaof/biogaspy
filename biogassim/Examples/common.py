"""Utilitários comuns aos exemplos do BioGasSim.

Biogás de referência: 47% CH4 / 53% CO2 a 25 °C e 1 atm.
"""
from __future__ import annotations

import numpy as np

from ..UnitOperations import Stream

# Composição base do biogás (frações molares)
BIOGAS = {"CH4": 0.47, "CO2": 0.53}
BIOGAS_T = 298.15      # K (25 °C)
BIOGAS_P = 1.01325e5   # Pa (1 atm)


def biogas_stream(flow_mols: float = 100.0, species=None, T=BIOGAS_T, P=BIOGAS_P,
                  composition=None) -> Stream:
    """Corrente de biogás.

    ``composition`` (dict espécie->fração, ex.: ``{"CH4": 0.6, "CO2": 0.4}``)
    permite variar a composição da alimentação; se omitido, usa o biogás padrão
    47% CH4 / 53% CO2. ``Stream.make`` normaliza as frações automaticamente.
    """
    if species is None:
        species = ["CH4", "CO2", "H2O"]
    comp = BIOGAS if composition is None else composition
    z = np.zeros(len(species))
    for i, s in enumerate(species):
        z[i] = comp.get(s, 0.0)
    return Stream.make(species, z, flow=flow_mols, T=T, P=P, phase="vapor")


def metrics_from_absorber(name: str, result, gas_in: Stream) -> dict:
    """Extrai métricas padronizadas de um resultado de Absorbedor."""
    return {
        "technology": name,
        "purity_CH4": round(result.purity_CH4 * 100, 2),          # %
        "recovery_CH4": round(result.methane_recovery * 100, 2),  # %
        "CO2_removal": round(result.CO2_removal * 100, 2),        # %
        "residual_CO2": round(result.residual_CO2 * 100, 3),      # %
        "methane_loss": round(result.methane_loss * 100, 2),      # %
        "diameter_m": round(result.diameter, 3),
        "height_m": round(result.height, 2),
        "NTU": round(result.NTU, 1) if np.isfinite(result.NTU) else None,
        "HTU_m": round(result.HTU, 4) if np.isfinite(result.HTU) else None,
        "KLa": round(result.KLa, 2) if np.isfinite(result.KLa) else None,
        "stage_efficiency": round(result.stage_efficiency, 3),
        "pressure_drop_Pa": round(result.pressure_drop, 1),
        "flooding_pct": round(result.flooding_fraction * 100, 1),
        "converged": result.converged,
        "iterations": result.iterations,
        "mass_balance_error": float(result.mass_balance_error),
        "gpdc_extrapolated": bool(getattr(result, "gpdc_extrapolated", False)),
        "liquid_capacity_limited": bool(getattr(result, "liquid_capacity_limited", False)),
    }


__all__ = ["biogas_stream", "metrics_from_absorber", "BIOGAS", "BIOGAS_T", "BIOGAS_P"]
