"""Testes do estudo de sensibilidade paramétrica."""
import numpy as np
import pytest

from biogassim.UnitOperations import Stream, AbsorberSpec
from biogassim.Solvents import WaterSolvent, MEASolvent
from biogassim.Optimization import sweep, sweep_grid, SweepResult, sweep_LG


def _water():
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], 100.0, 298.15, 20e5, "vapor")
    solv = Stream.make(species, [0.0, 0.0, 1.0], 10000.0, 293.15, 20e5, "liquid")
    base = AbsorberSpec(N_stages=12, mode="isothermal", T_op=293.15,
                        pressure=20e5, height=15.0, max_iter=400)
    return species, gas, solv, base


def test_sweep_LV_water_converges_and_monotonic():
    species, gas, solv, base = _water()
    res = sweep(gas, solv, WaterSolvent(), base, "L_over_V", [40, 60, 80, 100, 120])
    assert isinstance(res, SweepResult)
    assert all(res.converged)
    # mais solvente -> mais remoção de CO2 (monotonicidade física)
    rem = res.CO2_removal
    assert all(rem[i] <= rem[i + 1] + 1e-9 for i in range(len(rem) - 1))
    # mais solvente -> menos recuperação de CH4 (mais CH4 se perde na água)
    rec = res.recovery_CH4
    assert all(rec[i] >= rec[i + 1] - 1e-9 for i in range(len(rec) - 1))


def test_sweep_pressure_water_monotonic():
    species, gas, solv, base = _water()
    base = AbsorberSpec(N_stages=12, mode="isothermal", T_op=293.15,
                        pressure=5e5, height=15.0, max_iter=400)
    solv5 = Stream.make(species, [0.0, 0.0, 1.0], 10000.0, 293.15, 5e5, "liquid")
    res = sweep(gas, solv5, WaterSolvent(), base, "pressure",
                [5e5, 10e5, 15e5, 20e5, 25e5])
    assert all(res.converged)
    rem = res.CO2_removal
    assert all(rem[i] <= rem[i + 1] + 1e-9 for i in range(len(rem) - 1))


def test_sweep_to_rows():
    species, gas, solv, base = _water()
    res = sweep(gas, solv, WaterSolvent(), base, "L_over_V", [40, 80])
    rows = res.to_rows()
    assert len(rows) == 2
    assert "L_over_V" in rows[0]
    assert "purity_CH4_pct" in rows[0]


def test_sweep_grid_shape():
    species, gas, solv, base = _water()
    grid = sweep_grid(gas, solv, WaterSolvent(), base, "L_over_V",
                      [40, 80, 100], "pressure", [10e5, 20e5])
    assert grid["purity_CH4"].shape == (2, 3)
    assert grid["CO2_removal"].shape == (2, 3)
    # maior P e maior L/V devem dar maior remoção (canto superior-direito)
    rem = grid["CO2_removal"]
    assert rem[1, 2] >= rem[0, 0] - 1e-9   # (20bar, L/V=100) >= (10bar, L/V=40)


def test_mea_sweep_feasible_loading():
    """MEA: pontos convergidos têm rich loading < α_max (0.5); L/V muito
    baixo (solvente insuficiente) não converge -- regime inviável."""
    from biogassim.Properties.components import get
    species = ["CH4", "CO2", "H2O", "MEA"]
    gas = Stream.make(species, [0.47, 0.53, 0.0, 0.0], 100.0, 313.15, 2e5, "vapor")
    mm_mea, mm_w, w = get("MEA").MM, get("H2O").MM, 0.30
    x_mea = (w / mm_mea) / (w / mm_mea + (1 - w) / mm_w)
    solv = Stream.make(species, [0.0, 0.0, 1 - x_mea, x_mea], 2000.0, 313.15, 2e5, "liquid")
    base = AbsorberSpec(N_stages=8, mode="isothermal", T_op=313.15,
                        pressure=2e5, height=12.0, max_iter=400)
    res = sweep(gas, solv, MEASolvent(), base, "L_over_V", [10, 15, 20, 30])
    for k, conv in enumerate(res.converged):
        if conv:
            assert res.rich_loading[k] < 0.5 + 1e-6
            # pontos não-convergidos reportam NaN nas métricas
            assert np.isfinite(res.purity_CH4[k])
    # mais solvente -> rich loading menor
    feas = [(res.rich_loading[k]) for k in range(len(res.values)) if res.converged[k]]
    assert all(feas[i] >= feas[i + 1] - 1e-9 for i in range(len(feas) - 1))


def test_sweep_LG_legacy_compat():
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], 100.0, 298.15, 20e5, "vapor")

    def factory(L):
        return Stream.make(species, [0.0, 0.0, 1.0], L, 293.15, 20e5, "liquid")
    out = sweep_LG(gas, factory, WaterSolvent(),
                   pressures=[10e5, 20e5], L_over_V=[60, 100], N_stages=12, height=15.0)
    assert "by_LV" in out and "by_P" in out
    assert len(out["by_LV"]) == 2 and len(out["by_P"]) == 2