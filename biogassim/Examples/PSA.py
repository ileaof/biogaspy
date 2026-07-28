"""Exemplo: PSA (Pressure Swing Adsorption) -- estimativa simplificada."""
from __future__ import annotations

from typing import Dict

from ..PSA import PSACycle, fixed_bed_simple, selectivity
from ..Export import export_json
from .common import BIOGAS

OUTDIR = "examples_output"


def run_case(P_high_bar: float = 7.0, P_low_bar: float = 0.2,
             adsorbent: str = "Zeolite_13X", save: bool = True) -> Dict:
    y_in = dict(BIOGAS)
    cycle = PSACycle(adsorbent=adsorbent, P_high=P_high_bar * 1e5,
                     P_low=P_low_bar * 1e5, T=298.15)
    out = cycle.purity_estimate(y_in)
    bed = fixed_bed_simple(adsorbent, y_in, cycle.P_high, cycle.T,
                           bed_mass=500.0, flow=100.0)
    sel = selectivity(adsorbent, "CO2", "CH4", cycle.P_high, cycle.T)
    metrics = {
        "technology": f"PSA ({adsorbent})",
        "purity_CH4": round(out["CH4"] * 100, 2),
        "recovery_CH4": 95.0,                      # estimativa (CH4 segue ao produto)
        "methane_loss": 5.0,
        "CO2_removal": round(out["CO2_removal"] * 100, 2),
        "residual_CO2": round((1.0 - out["CH4"]) * 100, 3),
        "selectivity_CO2_CH4": round(sel, 1),
        "breakthrough_time_s": round(bed.breakthrough_time, 1),
        "bed_capacity_mol": round(bed.capacity, 1),
        "message": out["message"],
    }
    if save:
        export_json(metrics, f"{OUTDIR}/psa_results.json")
    return {"metrics": metrics}


def main():
    m = run_case()["metrics"]
    print("=" * 60)
    print("PSA (PRESSURE SWING ADSORPTION) -- modelo simplificado")
    print("=" * 60)
    print(f"Tecnologia: {m['technology']}")
    print(f"Pureza CH4 (estimada): {m['purity_CH4']} %")
    print(f"Remoção CO2 (estimada): {m['CO2_removal']} %")
    print(f"Seletividade CO2/CH4: {m['selectivity_CO2_CH4']}")
    print(f"Tempo de ruptura: {m['breakthrough_time_s']} s")
    print(f"Obs: {m['message']}")


if __name__ == "__main__":
    main()