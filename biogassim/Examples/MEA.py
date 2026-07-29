"""Exemplo: Lavagem química com MEA -- biogás 47/53.

MEA absorve CO2 por reação (carbamato), permitindo operação em baixa pressão.
Inclui regeneração (stripper) e balanço energético (calor de reboiler).
"""
from __future__ import annotations

import numpy as np

from ..Export import export_csv, export_json, export_profile_csv
from ..Optimization import EnergySummary, compression_energy, regeneration_energy
from ..Reporting import plot_column_profiles
from ..Solvents import MEASolvent
from ..UnitOperations import Absorber, AbsorberSpec, Stream
from ..UnitOperations.Compressor import compress
from .common import biogas_stream, metrics_from_absorber

OUTDIR = "examples_output"


def lean_solvent(species, flow: float, T=313.15, P=2e5, w_mea=0.30):
    """Solvente magro: 30% mássico MEA em água -> frações molares."""
    from ..Properties.components import get
    mm_mea = get("MEA").MM
    mm_w = get("H2O").MM
    x_mea = (w_mea / mm_mea) / (w_mea / mm_mea + (1 - w_mea) / mm_w)
    x_w = 1.0 - x_mea
    z = np.zeros(len(species))
    z[species.index("MEA")] = x_mea
    z[species.index("H2O")] = x_w
    return Stream.make(species, z, flow=flow, T=T, P=P, phase="liquid")


def run_case(P_bar: float = 2.0, L_over_V: float = 20.0, N_stages: int = 8,
             height: float = 12.0, flow: float = 100.0, save: bool = True) -> dict:
    species = ["CH4", "CO2", "H2O", "MEA"]
    P = P_bar * 1e5
    gas_in = biogas_stream(flow, species=species, T=313.15, P=1.01325e5)
    comp = compress(gas_in, P, eta=0.75)
    gas_feed = comp.out
    # garantir MEA/H2O zerados no gás
    gas_feed = Stream.make(species, gas_feed.z, gas_feed.flow, gas_feed.T, gas_feed.P, "vapor")
    solv = lean_solvent(species, L_over_V * flow, T=313.15, P=P)
    spec = AbsorberSpec(N_stages=N_stages, packing="Pall_50",
                        mode="isothermal", T_op=313.15, pressure=P, height=height,
                        max_iter=400)
    r = Absorber(gas_feed, solv, MEASolvent(), spec).solve()

    metrics = metrics_from_absorber("MEA (chemical)", r, gas_in)
    # CO2 absorvido (mol/s) = entra - sai no gás
    i_co2 = species.index("CO2")
    co2_absorbed = gas_in.flow * gas_in.z[i_co2] - r.gas_out.flow * r.gas_out.z[i_co2]
    # energia: compressão + regeneração (reboiler, ~4 MJ/kg CO2)
    regen = regeneration_energy(max(co2_absorbed, 0.0), specific_mj_per_kg=4.0)
    energy = EnergySummary(compression=compression_energy([comp]),
                           regeneration=regen)
    bio_nm3h = r.gas_out.flow * 0.0224 * 3600
    energy.finalize(bio_nm3h)
    metrics.update({"compression_kW": round(energy.compression, 2),
                    "regeneration_kW": round(energy.regeneration, 2),
                    "total_kW": round(energy.total_kw, 2),
                    "specific_kWh_per_Nm3": round(energy.specific_kwh_per_nm3, 3)})
    # carregamento rico (rich loading)
    i = species.index("CO2"); j = species.index("MEA")
    x_rich = r.liquid_out.z
    rich_loading = float(x_rich[i] / max(x_rich[j], 1e-12))
    metrics["rich_loading"] = round(rich_loading, 3)

    if save:
        export_json(metrics, f"{OUTDIR}/mea_results.json")
        export_csv([metrics], f"{OUTDIR}/mea_summary.csv")
        export_profile_csv(np.column_stack([r.x_profile.T, r.y_profile.T, r.T_profile]),
                           [f"x_{s}" for s in species] + [f"y_{s}" for s in species] + ["T_K"],
                           f"{OUTDIR}/mea_profiles.csv")
        plot_column_profiles(r, species, f"{OUTDIR}/mea_profiles.png")
    return {"result": r, "metrics": metrics}


def main():
    data = run_case()
    m = data["metrics"]
    print("=" * 60)
    print("MEA (AMINA QUÍMICA) -- biogás 47% CH4 / 53% CO2")
    print("=" * 60)
    print(f"Convergiu: {m['converged']} em {m['iterations']} iterações")
    print(f"Pureza CH4:      {m['purity_CH4']} %")
    print(f"Recuperação CH4: {m['recovery_CH4']} %  (perda {m['methane_loss']} %)")
    print(f"Remoção CO2:     {m['CO2_removal']} %  (residual {m['residual_CO2']} %)")
    print(f"Carregamento rico (α): {m['rich_loading']} mol CO2/mol MEA")
    print(f"Diâmetro: {m['diameter_m']} m | Altura: {m['height_m']} m")
    print(f"Energia: compressão {m['compression_kW']} kW, reboiler {m['regeneration_kW']} kW")
    print(f"Consumo específico: {m['specific_kWh_per_Nm3']} kWh/Nm³ biometano")
    print(f"Arquivos gerados em {OUTDIR}/mea_*")


if __name__ == "__main__":
    main()
