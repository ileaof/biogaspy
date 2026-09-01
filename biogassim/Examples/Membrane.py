"""Exemplo: Separação por membrana -- 1 estágio solução-difusão."""
from __future__ import annotations

import numpy as np

from ..Export import export_json
from ..Membranes import single_stage
from ..Optimization import EnergySummary, compression_energy
from ..Properties import normalize_mixture
from ..UnitOperations.Compressor import compress
from .common import BIOGAS, biogas_stream

OUTDIR = "examples_output"


def _ch4_co2_z(composition):
    """Vetor z CH4/CO2 renormalizado (o modelo de membrana é CH4-CO2)."""
    if composition is None:
        return np.array([BIOGAS["CH4"], BIOGAS["CO2"]])
    c = {k: float(v) for k, v in composition.items()
         if k in ("CH4", "CO2") and float(v) > 0.0}
    if not c:
        return np.array([BIOGAS["CH4"], BIOGAS["CO2"]])
    c = normalize_mixture(c)
    return np.array([c.get("CH4", 0.0), c.get("CO2", 0.0)])


def run_case(material: str = "CelluloseAcetate", P_feed_bar: float = 10.0,
             P_perm_bar: float = 0.2, stage_cut: float = 0.5,
             flow: float = 100.0, composition=None, save: bool = True,
             T_C: float = 35.0) -> dict:
    species = ["CH4", "CO2"]
    z = _ch4_co2_z(composition)
    Tk = float(T_C) + 273.15
    # modo design: dado o corte-alvo, resolve a área requerida (não mais fixa).
    r = single_stage(material, species, z, flow, Tk,
                     P_feed_bar * 1e5, P_perm_bar * 1e5, stage_cut=stage_cut)
    # energia: compressão do feed até P_feed + vácuo no permeado (P_perm).
    gas_in = biogas_stream(flow, species=species, T=Tk, P=1.01325e5,
                           composition={"CH4": float(z[0]), "CO2": float(z[1])})
    comp = compress(gas_in, P_feed_bar * 1e5, eta=0.75)
    # vácuo: potência ~ compressão do permeado de P_perm até 1 atm (estimativa)
    perm_flow = flow * r.stage_cut
    gas_perm = biogas_stream(perm_flow, species=species, T=Tk,
                             P=P_perm_bar * 1e5,
                             composition={"CH4": float(z[0]), "CO2": float(z[1])})
    vacuum = compress(gas_perm, 1.01325e5, eta=0.6)
    energy = EnergySummary(compression=compression_energy([comp, vacuum]))
    bio_mols = flow * r.recovery_CH4
    bio_nm3h = bio_mols * 0.0224 * 3600
    energy.finalize(bio_nm3h)
    metrics = {
        "technology": f"Membrane ({material})",
        "purity_CH4": round(r.purity_CH4 * 100, 2),
        "recovery_CH4": round(r.recovery_CH4 * 100, 2),
        "CO2_removal": round(r.CO2_removal * 100, 2),
        "methane_loss": round((1.0 - r.recovery_CH4) * 100, 2),
        "stage_cut": round(r.stage_cut, 4),
        "area_m2": round(r.area, 1),
        "feed_flow_mols": round(float(flow), 2),
        "product_flow_mols": round(bio_mols, 2),
        "operating_pressure_bar": round(P_feed_bar, 2),
        "compression_kW": round(energy.compression, 2),
        "total_kW": round(energy.total_kw, 2),
        "specific_kWh_per_Nm3": round(energy.specific_kwh_per_nm3, 3),
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
