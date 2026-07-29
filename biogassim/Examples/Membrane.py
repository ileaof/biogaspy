"""Exemplo: Separação por membrana -- 1 estágio solução-difusão."""
from __future__ import annotations

import numpy as np

from ..Export import export_json
from ..Membranes import single_stage
from .common import BIOGAS

OUTDIR = "examples_output"


def run_case(material: str = "CelluloseAcetate", P_feed_bar: float = 10.0,
             P_perm_bar: float = 0.2, stage_cut: float = 0.5,
             flow: float = 100.0, save: bool = True) -> dict:
    species = ["CH4", "CO2"]
    z = np.array([BIOGAS["CH4"], BIOGAS["CO2"]])
    # modo design: dado o corte-alvo, resolve a área requerida (não mais fixa).
    r = single_stage(material, species, z, flow, 308.15,
                     P_feed_bar * 1e5, P_perm_bar * 1e5, stage_cut=stage_cut)
    metrics = {
        "technology": f"Membrane ({material})",
        "purity_CH4": round(r.purity_CH4 * 100, 2),
        "recovery_CH4": round(r.recovery_CH4 * 100, 2),
        "CO2_removal": round(r.CO2_removal * 100, 2),
        "stage_cut": round(r.stage_cut, 4),
        "area_m2": round(r.area, 1),
        "message": r.message,
    }
    if save:
        export_json(metrics, f"{OUTDIR}/membrane_results.json")
    return {"result": r, "metrics": metrics}


def main():
    m = run_case()["metrics"]
    print("=" * 60)
    print("MEMBRANA -- 1 estágio (solução-difusão)")
    print("=" * 60)
    print(f"Tecnologia: {m['technology']}")
    print(f"Pureza CH4 (retentado): {m['purity_CH4']} %")
    print(f"Recuperação CH4: {m['recovery_CH4']} %")
    print(f"Remoção CO2: {m['CO2_removal']} %")
    print(f"Corte de estágio: {m['stage_cut']} | Área: {m['area_m2']} m²")
    print(f"Obs: {m['message']}")


if __name__ == "__main__":
    main()
