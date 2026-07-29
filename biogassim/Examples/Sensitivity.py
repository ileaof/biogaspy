"""Exemplo: estudo de sensibilidade paramétrica do absorvedor.

Varre pressão e L/V para Water Scrubbing e MEA, demonstrando que o Newton
global converge em toda a faixa (antes a substituição sucessiva divergia
perto do pinch). Gera tabelas (CSV/JSON), curvas 1-D e heatmap 2-D.
"""
from __future__ import annotations

import os
import sys

from ..Export import export_csv, export_json
from ..Optimization import sweep, sweep_grid
from ..Reporting import plot_sweep, plot_sweep_grid
from ..Solvents import MEASolvent, WaterSolvent
from ..UnitOperations import AbsorberSpec, Stream
from .common import biogas_stream
from .MEA import lean_solvent

OUTDIR = "examples_output"


def _water_streams(flow=100.0):
    species = ["CH4", "CO2", "H2O"]
    gas = biogas_stream(flow, species=species, T=298.15, P=20e5)
    solv = Stream.make(species, [0.0, 0.0, 1.0], 100.0 * 100, 293.15, 20e5, "liquid")
    return species, gas, solv


def _mea_streams(flow=100.0, LV=20.0):
    species = ["CH4", "CO2", "H2O", "MEA"]
    gas = biogas_stream(flow, species=species, T=313.15, P=2e5)
    solv = lean_solvent(species, LV * flow, T=313.15, P=2e5)
    return species, gas, solv


def run_water(save: bool = True) -> dict:
    species, gas, solv = _water_streams()
    base = AbsorberSpec(N_stages=12, mode="isothermal", T_op=293.15,
                        pressure=20e5, height=15.0, max_iter=400)
    # varre L/V a 20 bar
    res_LV = sweep(gas, solv, WaterSolvent(), base, "L_over_V",
                   [20, 40, 60, 80, 100, 120, 150])
    # varre pressão a L/V=100
    baseP = AbsorberSpec(N_stages=12, mode="isothermal", T_op=293.15,
                         pressure=10e5, height=15.0, max_iter=400)
    solv100 = Stream.make(species, [0.0, 0.0, 1.0], 100 * 100, 293.15, 10e5, "liquid")
    res_P = sweep(gas, solv100, WaterSolvent(), baseP, "pressure",
                  [5e5, 10e5, 15e5, 20e5, 25e5, 30e5])
    # grade 2-D P x L/V
    grid = sweep_grid(gas, solv, WaterSolvent(), base, "L_over_V",
                      [20, 50, 80, 100, 120], "pressure",
                      [5e5, 10e5, 15e5, 20e5, 25e5])
    if save:
        export_csv(res_LV.to_rows(), f"{OUTDIR}/sensitivity_water_LV.csv")
        export_csv(res_P.to_rows(), f"{OUTDIR}/sensitivity_water_P.csv")
        export_json({"by_LV": res_LV.to_rows(), "by_P": res_P.to_rows()},
                    f"{OUTDIR}/sensitivity_water.json")
        plot_sweep(res_LV, f"{OUTDIR}/sensitivity_water_LV.png",
                   title="Water Scrubbing: varredura L/V (20 bar)")
        plot_sweep(res_P, f"{OUTDIR}/sensitivity_water_P.png",
                   title="Water Scrubbing: varredura P (L/V=100)")
        plot_sweep_grid(grid, "CO2_removal", f"{OUTDIR}/sensitivity_water_grid.png",
                        title="Water: remoção CO2 (%) vs (L/V, P)")
    return {"LV": res_LV, "P": res_P, "grid": grid}


def run_mea(save: bool = True) -> dict:
    species, gas, solv = _mea_streams(LV=20.0)
    base = AbsorberSpec(N_stages=8, mode="isothermal", T_op=313.15,
                        pressure=2e5, height=12.0, max_iter=400)
    res_LV = sweep(gas, solv, MEASolvent(), base, "L_over_V",
                   [4, 6, 8, 10, 12, 15, 20, 30])
    baseP = AbsorberSpec(N_stages=8, mode="isothermal", T_op=313.15,
                         pressure=1e5, height=12.0, max_iter=400)
    species2, gas2, solv2 = _mea_streams(LV=20.0)
    solv2 = Stream.make(species2, solv2.z, solv2.flow, solv2.T, 1e5, "liquid")
    res_P = sweep(gas2, solv2, MEASolvent(), baseP, "pressure",
                  [1e5, 1.5e5, 2e5, 3e5, 5e5])
    grid = sweep_grid(gas, solv, MEASolvent(), base, "L_over_V",
                     [4, 8, 12, 20, 30], "pressure",
                     [1e5, 1.5e5, 2e5, 3e5, 5e5])
    if save:
        export_csv(res_LV.to_rows(), f"{OUTDIR}/sensitivity_mea_LV.csv")
        export_csv(res_P.to_rows(), f"{OUTDIR}/sensitivity_mea_P.csv")
        export_json({"by_LV": res_LV.to_rows(), "by_P": res_P.to_rows()},
                    f"{OUTDIR}/sensitivity_mea.json")
        plot_sweep(res_LV, f"{OUTDIR}/sensitivity_mea_LV.png",
                   title="MEA: varredura L/V (2 bar)")
        plot_sweep(res_P, f"{OUTDIR}/sensitivity_mea_P.png",
                   title="MEA: varredura P (L/V=20)")
        plot_sweep_grid(grid, "CO2_removal", f"{OUTDIR}/sensitivity_mea_grid.png",
                        title="MEA: remoção CO2 (%) vs (L/V, P)")
    return {"LV": res_LV, "P": res_P, "grid": grid}


def _print(title, res):
    print(f"\n{title}  (convergiu em {res.n_converged}/{len(res.values)} pontos)")
    print(f"{'L/V' if res.parameter == 'L_over_V' else res.parameter:>8}  "
          f"{'pureza%':>8} {'recup%':>8} {'CO2rem%':>8} {'rich':>6} conv")
    for k, v in enumerate(res.values):
        tag = f"{v:.3g}" if res.parameter == "L_over_V" else f"{v/1e5:.1f}bar"
        print(f"{tag:>8}  {res.purity_CH4[k]*100:8.2f} {res.recovery_CH4[k]*100:8.2f} "
              f"{res.CO2_removal[k]*100:8.2f} {res.rich_loading[k]:6.3f} {res.converged[k]}")


def run_all(save: bool = True) -> dict:
    os.makedirs(OUTDIR, exist_ok=True)
    w = run_water(save=save)
    m = run_mea(save=save)
    print("=" * 64)
    print("SENSIBILIDADE PARAMÉTRICA -- biogás 47% CH4 / 53% CO2")
    print("=" * 64)
    _print("Water Scrubbing -- varredura L/V (20 bar)", w["LV"])
    _print("Water Scrubbing -- varredura P (L/V=100)", w["P"])
    _print("MEA -- varredura L/V (2 bar)", m["LV"])
    _print("MEA -- varredura P (L/V=20)", m["P"])
    print(f"\nArquivos gerados em {OUTDIR}/sensitivity_*  (CSV/JSON/PNG)")
    return {"water": w, "mea": m}


def main():
    run_all(save=True)


if __name__ == "__main__":
    # permite rodar como script: python Examples/Sensitivity.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
