"""Gera tabela de desvios do modelo vs literatura.

Executa as validações termodinâmicas e de equilíbrio MEA, imprime uma
tabela de desvios e exporta em CSV/JSON em ``examples_output/``.

Uso:
    python tests/validation_table.py
    python -m pytest tests/validation_table.py::test_validation_table_runs
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import numpy as np

from biogassim.Properties.components import get
from biogassim.Solvents.KentEisenberg import KentEisenberg
from biogassim.Thermodynamics.Henry import henry_water
from biogassim.Thermodynamics.PengRobinson import PengRobinson

# Aronu et al. (2011) -- 30 wt% MEA, 40 C: (alpha, p_CO2 kPa)
ARONU_40C = [
    (0.102, 0.0016), (0.206, 0.0123), (0.250, 0.0246), (0.337, 0.0603),
    (0.353, 0.0851), (0.401, 0.1835), (0.417, 0.2928), (0.433, 0.3809),
    (0.447, 0.5702), (0.464, 1.0662), (0.476, 1.8326), (0.485, 2.3193),
    (0.489, 2.8577), (0.516, 8.5583), (0.524, 11.812),
]


def _rows() -> list[dict]:
    rows: list[dict] = []

    # --- Peng-Robinson Z ---
    cases = [
        ("CH4", 298.15, 101325.0, 0.9981),
        ("CO2", 298.15, 101325.0, 0.9933),
        ("CH4", 298.15, 1.0e6, 0.981),    # aprox (não-ideal moderado)
        ("CO2", 298.15, 1.0e6, 0.90),      # aprox
    ]
    for sp, T, P, Z_lit in cases:
        eos = PengRobinson([get(sp)])
        Z = eos.Z_and_phi(T, P, np.array([1.0]), phase="vapor").Z
        rows.append({
            "validacao": f"Z PR {sp}", "T_K": T, "P_Pa": P,
            "modelo": Z, "literatura": Z_lit,
            "desvio_pct": 100.0 * (Z - Z_lit) / Z_lit,
        })

    # --- Henry CO2 em agua 25 C ---
    hl = henry_water()
    H = hl.H("CO2", 298.15)
    Vm = 18.0e-6
    hcp = 1.0 / (H * Vm) * 101325.0 / 1000.0
    rows.append({
        "validacao": "HCP CO2/agua 25C", "T_K": 298.15, "P_Pa": "",
        "modelo": hcp, "literatura": 0.034,
        "desvio_pct": 100.0 * (hcp - 0.034) / 0.034,
    })

    # --- Kent-Eisenberg vs Aronu ---
    ke = KentEisenberg()
    T, m = 313.15, 4.9
    for alpha, p_lit in ARONU_40C:
        p_mod = ke.pCO2(alpha, T, m) / 1000.0
        rows.append({
            "validacao": f"pCO2 MEA a={alpha:.3f}", "T_K": T, "P_Pa": "",
            "modelo": p_mod, "literatura": p_lit,
            "desvio_pct": 100.0 * (p_mod - p_lit) / p_lit,
        })

    # --- Balanco de energia (adiabatico) MEA: ΔT observado vs estimado ---
    try:
        from biogassim.Properties.components import get as gcomp
        from biogassim.Solvents import MEASolvent
        from biogassim.UnitOperations import Absorber, AbsorberSpec, Stream
        species = ["CH4", "CO2", "H2O", "MEA"]
        gas = Stream.make(species, [0.47, 0.53, 0.0, 0.0], 100.0, 313.15, 2e5, "vapor")
        mm_mea, mm_w, w = gcomp("MEA").MM, gcomp("H2O").MM, 0.30
        x_mea = (w / mm_mea) / (w / mm_mea + (1 - w) / mm_w)
        solv = Stream.make(species, [0.0, 0.0, 1 - x_mea, x_mea], 2000.0, 313.15, 2e5, "liquid")
        spec = AbsorberSpec(N_stages=8, mode="adiabatic", T_op=313.15,
                           pressure=2e5, height=12.0, max_iter=400)
        r = Absorber(gas, solv, MEASolvent(), spec).solve()
        ic = species.index("CO2")
        co2_abs = gas.z[ic] * gas.flow - r.gas_out.z[ic] * r.gas_out.flow
        Habs = MEASolvent().heat_of_absorption("CO2")
        cp_l = MEASolvent().cp_liquid(313.15)
        dT_est = co2_abs * Habs / (solv.flow * cp_l)
        dT_obs = r.T_profile.max() - 313.15
        rows.append({
            "validacao": "dT adiabatico MEA", "T_K": 313.15, "P_Pa": "",
            "modelo": dT_obs, "literatura": dT_est,
            "desvio_pct": 100.0 * (dT_obs - dT_est) / dT_est,
        })
    except Exception as exc:  # pragma: no cover
        rows.append({"validacao": "dT adiabatico MEA", "T_K": "", "P_Pa": "",
                     "modelo": "erro", "literatura": "", "desvio_pct": str(exc)})

    return rows


def build(outdir: str | Path = "examples_output") -> list[dict]:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    rows = _rows()
    with open(out / "validation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["validacao", "T_K", "P_Pa",
                                          "modelo", "literatura", "desvio_pct"])
        w.writeheader()
        w.writerows(rows)
    with open(out / "validation.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    _print(rows)
    return rows


def _print(rows: list[dict]) -> None:
    print(f"\n{'validacao':22s} {'modelo':>12} {'literatura':>12} {'desvio%':>10}")
    print("-" * 60)
    for r in rows:
        mod = f"{r['modelo']:.4g}" if isinstance(r['modelo'], float) else r['modelo']
        lit = f"{r['literatura']:.4g}" if isinstance(r['literatura'], float) else r['literatura']
        dev = f"{r['desvio_pct']:+.1f}" if isinstance(r['desvio_pct'], float) else ""
        print(f"{r['validacao']:22s} {mod:>12} {lit:>12} {dev:>10}")


def main() -> None:
    build(os.environ.get("BIOGASSIM_OUT", "examples_output"))


def test_validation_table_runs(tmp_path):
    rows = build(tmp_path)
    assert rows
    assert (tmp_path / "validation.csv").exists()
    assert (tmp_path / "validation.json").exists()


if __name__ == "__main__":
    main()
