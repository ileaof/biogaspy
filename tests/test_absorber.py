"""Testes do Absorvedor e balanceamento de massa."""
import numpy as np

from biogassim.Solvents import MEASolvent, WaterSolvent
from biogassim.UnitOperations import Absorber, AbsorberSpec, Stream


def _global_mass_balance(r, gas_in, solv_in):
    """Verifica balanço global de massa por componente."""
    feed = gas_in.z * gas_in.flow + solv_in.z * solv_in.flow
    out = r.gas_out.z * r.gas_out.flow + r.liquid_out.z * r.liquid_out.flow
    return feed, out


def test_water_scrubbing_runs_and_balances():
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], 100.0, 298.15, 20e5, "vapor")
    solv = Stream.make(species, [0.0, 0.0, 1.0], 10000.0, 293.15, 20e5, "liquid")
    spec = AbsorberSpec(N_stages=12, packing="Pall_50", mode="isothermal",
                        T_op=293.15, pressure=20e5, height=15.0, max_iter=400)
    r = Absorber(gas, solv, WaterSolvent(), spec).solve()
    assert r.converged
    # balanço de massa global fecha
    feed, out = _global_mass_balance(r, gas, solv)
    assert np.allclose(feed, out, atol=1e-3), f"feed={feed}, out={out}"
    # CO2 é absorvido -> pureza de CH4 sobe
    assert r.purity_CH4 > 0.90
    assert r.CO2_removal > 0.90
    # recuperação de metano (alguma perda para a água)
    assert 0.85 < r.methane_recovery < 1.0


def test_mea_runs_and_balances():
    species = ["CH4", "CO2", "H2O", "MEA"]
    gas = Stream.make(species, [0.47, 0.53, 0.0, 0.0], 100.0, 313.15, 2e5, "vapor")
    from biogassim.Properties.components import get
    mm_mea = get("MEA").MM
    mm_w = get("H2O").MM
    w = 0.30
    x_mea = (w / mm_mea) / (w / mm_mea + (1 - w) / mm_w)
    solv = Stream.make(species, [0.0, 0.0, 1.0 - x_mea, x_mea], 2000.0, 313.15, 2e5, "liquid")
    spec = AbsorberSpec(N_stages=8, packing="Pall_50", mode="isothermal",
                        T_op=313.15, pressure=2e5, height=12.0, max_iter=400)
    r = Absorber(gas, solv, MEASolvent(), spec).solve()
    assert r.converged
    feed, out = _global_mass_balance(r, gas, solv)
    assert np.allclose(feed, out, atol=1e-2), f"feed={feed}, out={out}"
    assert r.purity_CH4 > 0.95
    assert r.CO2_removal > 0.95
    # amina é seletiva -> pouca perda de CH4
    assert r.methane_recovery > 0.95
    # carregamento rico fisicamente plausível (< alpha_max)
    i = species.index("CO2"); j = species.index("MEA")
    rich_loading = r.liquid_out.z[i] / max(r.liquid_out.z[j], 1e-12)
    assert 0.05 < rich_loading < 0.5


def test_ch4_more_volatile_than_co2_in_water():
    """K_CH4 >> K_CO2 em água -> CH4 fica no gás (seletividade)."""
    from biogassim.Thermodynamics.Henry import henry_water
    hl = henry_water()
    K_co2 = hl.K_value("CO2", 298.15, 1e6)
    K_ch4 = hl.K_value("CH4", 298.15, 1e6)
    assert K_ch4 > K_co2 * 10


def test_mea_pinch_regime_converges():
    """Regime de pinch (MEA L/V baixo) que divergia com substituição sucessiva
    deve convergir com o Newton global e fechar balanço de massa."""
    from biogassim.Properties.components import get
    species = ["CH4", "CO2", "H2O", "MEA"]
    gas = Stream.make(species, [0.47, 0.53, 0.0, 0.0], 100.0, 313.15, 2e5, "vapor")
    mm_mea = get("MEA").MM
    mm_w = get("H2O").MM
    w = 0.30
    x_mea = (w / mm_mea) / (w / mm_mea + (1 - w) / mm_w)
    # L/V = 12 -> fator de absorção próximo de 1 (pinch), antes divergia
    solv = Stream.make(species, [0.0, 0.0, 1.0 - x_mea, x_mea], 1200.0, 313.15, 2e5, "liquid")
    spec = AbsorberSpec(N_stages=8, mode="isothermal", T_op=313.15,
                        pressure=2e5, height=12.0, max_iter=400, method="newton")
    r = Absorber(gas, solv, MEASolvent(), spec).solve()
    assert r.converged
    feed, out = _global_mass_balance(r, gas, solv)
    assert np.allclose(feed, out, atol=1e-6), f"feed={feed}, out={out}"
    # monotonicidade física: mais solvente (L/V=30) -> carregamento rico menor
    # (mesmo CO2 absorvido distribuído em mais MEA) e recuperação de CH4 <=
    solv2 = Stream.make(species, [0.0, 0.0, 1.0 - x_mea, x_mea], 3000.0, 313.15, 2e5, "liquid")
    r2 = Absorber(gas, solv2, MEASolvent(), spec).solve()
    assert r2.converged
    i, j = species.index("CO2"), species.index("MEA")
    rich = r.liquid_out.z[i] / max(r.liquid_out.z[j], 1e-12)
    rich2 = r2.liquid_out.z[i] / max(r2.liquid_out.z[j], 1e-12)
    assert rich2 < rich
    assert r2.CO2_removal >= r.CO2_removal - 1e-9


def test_ss_method_still_works():
    """O método 'ss' (substituição sucessiva) permanece disponível."""
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], 100.0, 298.15, 20e5, "vapor")
    solv = Stream.make(species, [0.0, 0.0, 1.0], 10000.0, 293.15, 20e5, "liquid")
    spec = AbsorberSpec(N_stages=12, mode="isothermal", T_op=293.15,
                        pressure=20e5, height=15.0, max_iter=400, method="ss")
    r = Absorber(gas, solv, WaterSolvent(), spec).solve()
    assert r.converged
    feed, out = _global_mass_balance(r, gas, solv)
    assert np.allclose(feed, out, atol=1e-3)
    assert r.purity_CH4 > 0.90
