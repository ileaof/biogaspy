"""Exemplo: PSA (Pressure Swing Adsorption) -- estimativa simplificada."""
from __future__ import annotations

from ..Export import export_json
from ..Optimization import EnergySummary, compression_energy
from ..Properties import normalize_mixture
from ..PSA import PSACycle, fixed_bed_simple, selectivity
from ..UnitOperations.Compressor import compress
from .common import BIOGAS, biogas_stream

OUTDIR = "examples_output"


def _ch4_co2(composition):
    """Composição CH4/CO2 renormalizada (o modelo PSA é CH4-CO2)."""
    if composition is None:
        return dict(BIOGAS)
    c = {k: float(v) for k, v in composition.items()
         if k in ("CH4", "CO2") and float(v) > 0.0}
    if not c:
        return dict(BIOGAS)
    return normalize_mixture(c)


def run_case(P_high_bar: float = 7.0, P_low_bar: float = 0.2,
             adsorbent: str = "Zeolite_13X", composition=None,
             flow: float = 100.0, save: bool = True) -> dict:
    y_in = _ch4_co2(composition)
    cycle = PSACycle(adsorbent=adsorbent, P_high=P_high_bar * 1e5,
                     P_low=P_low_bar * 1e5, T=298.15)
    out = cycle.purity_estimate(y_in)
    bed = fixed_bed_simple(adsorbent, y_in, cycle.P_high, cycle.T,
                           bed_mass=500.0, flow=flow)
    sel = selectivity(adsorbent, "CO2", "CH4", cycle.P_high, cycle.T)
    # energia: compressão do biogás de 1 atm até P_high (estimativa, mesma base
    # que os demais métodos -- reusa o Compressor, não inventa termodinâmica).
    species = ["CH4", "CO2"]
    gas_in = biogas_stream(flow, species=species, T=298.15, P=1.01325e5,
                           composition=y_in)
    comp = compress(gas_in, cycle.P_high, eta=0.75)
    energy = EnergySummary(compression=compression_energy([comp]))
    recovery = 95.0
    bio_mols = flow * recovery / 100.0
    bio_nm3h = bio_mols * 0.0224 * 3600
    energy.finalize(bio_nm3h)
    metrics = {
        "technology": f"PSA ({adsorbent})",
        "purity_CH4": round(out["CH4"] * 100, 2),
        "recovery_CH4": recovery,                   # estimativa (CH4 segue ao produto)
        "methane_loss": round(100.0 - recovery, 2),
        "CO2_removal": round(out["CO2_removal"] * 100, 2),
        "residual_CO2": round((1.0 - out["CH4"]) * 100, 3),
        "selectivity_CO2_CH4": round(sel, 1),
        "breakthrough_time_s": round(bed.breakthrough_time, 1),
        "bed_capacity_mol": round(bed.capacity, 1),
        "feed_flow_mols": round(float(flow), 2),
        "product_flow_mols": round(bio_mols, 2),
        "operating_pressure_bar": round(P_high_bar, 2),
        "compression_kW": round(energy.compression, 2),
        "total_kW": round(energy.total_kw, 2),
        "specific_kWh_per_Nm3": round(energy.specific_kwh_per_nm3, 3),
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
