"""Exemplo: Lavagem com água (Water Scrubbing) -- biogás 47/53.

Roda o absorvedor com água em alta pressão (água recirculada), calcula
biometano, recuperação de metano, dimensionamento, energia e gera gráficos.
"""
from __future__ import annotations

import numpy as np

from ..Export import export_csv, export_json, export_profile_csv
from ..Optimization import EnergySummary, compression_energy
from ..Reporting import plot_column_profiles, plot_equilibrium_curve
from ..Solvents import WaterSolvent
from ..UnitOperations import Absorber, AbsorberSpec, Stream
from ..UnitOperations.Compressor import compress
from .common import biogas_stream, metrics_from_absorber

OUTDIR = "examples_output"


def run_case(P_bar: float = 20.0, L_over_V: float = 100.0, N_stages: int = 12,
             height: float = 15.0, flow: float = 100.0, save: bool = True) -> dict:
    species = ["CH4", "CO2", "H2O"]
    P = P_bar * 1e5
    # compressão do biogás da pressão atmosférica até P
    gas_in = biogas_stream(flow, species=species, T=298.15, P=1.01325e5)
    comp = compress(gas_in, P, eta=0.75)
    gas_feed = comp.out
    # solvente: água a P
    solv = Stream.make(species, [0.0, 0.0, 1.0], flow=L_over_V * flow,
                      T=293.15, P=P, phase="liquid")
    spec = AbsorberSpec(N_stages=N_stages, packing="Pall_50",
                        mode="isothermal", T_op=293.15, pressure=P, height=height,
                        max_iter=400)
    r = Absorber(gas_feed, solv, WaterSolvent(), spec).solve()

    metrics = metrics_from_absorber("Water Scrubbing", r, gas_in)
    # energia
    energy = EnergySummary(compression=compression_energy([comp]),
                           pumping=L_over_V * flow * 0.018 / 1000 * P / 0.7 / 1000)
    # biometano em Nm³/h (~ gas_out.flow * 22.4e-3 * 3600)
    bio_nm3h = r.gas_out.flow * 0.0224 * 3600
    energy.finalize(bio_nm3h)
    metrics.update({"compression_kW": round(energy.compression, 2),
                    "pumping_kW": round(energy.pumping, 2),
                    "total_kW": round(energy.total_kw, 2),
                    "specific_kWh_per_Nm3": round(energy.specific_kwh_per_nm3, 3)})

    if save:
        export_json(metrics, f"{OUTDIR}/water_results.json")
        export_csv([metrics], f"{OUTDIR}/water_summary.csv")
        export_profile_csv(np.column_stack([r.x_profile.T, r.y_profile.T, r.T_profile]),
                           [f"x_{s}" for s in species] + [f"y_{s}" for s in species] + ["T_K"],
                           f"{OUTDIR}/water_profiles.csv")
        plot_column_profiles(r, species, f"{OUTDIR}/water_profiles.png")
        K_co2 = float(r.K_profile[species.index("CO2")].mean())
        plot_equilibrium_curve(K_co2, f"{OUTDIR}/water_equilibrium.png", label="CO2 (water)")
    return {"result": r, "metrics": metrics, "compressor": comp}


def main():
    data = run_case()
    m = data["metrics"]
    print("=" * 60)
    print("WATER SCRUBBING -- biogás 47% CH4 / 53% CO2")
    print("=" * 60)
    print(f"Convergiu: {m['converged']} em {m['iterations']} iterações")
    print(f"Pureza CH4:      {m['purity_CH4']} %")
    print(f"Recuperação CH4: {m['recovery_CH4']} %  (perda {m['methane_loss']} %)")
    print(f"Remoção CO2:     {m['CO2_removal']} %  (residual {m['residual_CO2']} %)")
    print(f"Diâmetro: {m['diameter_m']} m | Altura: {m['height_m']} m")
    print(f"NTU: {m['NTU']} | HTU: {m['HTU_m']} m | KLa: {m['KLa']}")
    print(f"Energia: compressão {m['compression_kW']} kW, total {m['total_kW']} kW")
    print(f"Consumo específico: {m['specific_kWh_per_Nm3']} kWh/Nm³ biometano")
    print(f"Arquivos gerados em {OUTDIR}/water_*")


if __name__ == "__main__":
    main()
