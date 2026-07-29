"""Testes de solventes químicos (DEA, MDEA -- Kent-Eisenberg) e físicos (Selexol, Rectisol)."""
import numpy as np
import pytest

from biogassim.Properties.components import get
from biogassim.Solvents import (
    DEASolvent,
    KentEisenberg,
    MDEASolvent,
    RectisolSolvent,
    SelexolSolvent,
)
from biogassim.UnitOperations import Absorber, AbsorberSpec, Stream


def _lean_amine(species, amine, w, flow, T, P):
    """Corrente de solvente magro (amina + água) a partir da fração mássica w."""
    mm_a = get(amine).MM
    mm_w = get("H2O").MM
    x_a = (w / mm_a) / (w / mm_a + (1.0 - w) / mm_w)
    z = [0.0] * len(species)
    z[species.index("H2O")] = 1.0 - x_a
    z[species.index(amine)] = x_a
    return Stream.make(species, z, flow, T, P, "liquid")


# ============================ Kent-Eisenberg (DEA/MDEA) ============================
MEA = KentEisenberg()  # defaults
DEA = KentEisenberg(amine="DEA", log_beta1=9.9, log_beta2=4.70, dH1=-35000, dH2=-55000)
MDEA = KentEisenberg(amine="MDEA", log_beta1=8.634, log_beta2=0.0, dH1=-41971.0, dH2=0.0)


def test_ke_mdea_no_carbamate_reaches_high_loading():
    """MDEA (sem carbamato) alcança α=1,0; MEA/DEA (com carbamato) não divergem antes."""
    s = MDEA.solve_speciation(1.0, 313.15, 5.0)
    assert s["converged"]
    assert s["Carbamate"] == 0.0                    # amina terciária: sem carbamato
    assert s["HCO3"] > 0.0                           # CO2 absorvido como bicarbonato


def test_ke_pCO2_monotonic_in_alpha():
    T, m = 313.15, 5.0
    for ke, amax in [(MEA, 0.49), (DEA, 0.49), (MDEA, 1.0)]:
        alphas = np.linspace(0.05, amax, 6)
        p = [ke.pCO2(a, T, m) for a in alphas]
        assert all(p[i] < p[i + 1] for i in range(len(p) - 1)), ke.amine


def test_ke_weaker_amine_higher_pCO2():
    """No mesmo α, pCO2: MEA < DEA < MDEA (aminas mais fracas absorvem menos)."""
    T, m, a = 313.15, 5.0, 0.30
    p = {ke.amine: ke.pCO2(a, T, m) for ke in (MEA, DEA, MDEA)}
    assert p["MEA"] < p["DEA"] < p["MDEA"]


def test_ke_pCO2_increases_with_temperature():
    for ke in (MEA, DEA, MDEA):
        a = 0.30 if ke.amine != "MDEA" else 0.50
        assert ke.pCO2(a, 313.15, 5.0) < ke.pCO2(a, 353.15, 5.0)


def test_ke_dea_carbamate_pinch_mdea_smooth():
    """DEA (carbamato) tem aumento íngreme perto de α~0,5; MDEA (sem carbamato) é suave."""
    # razão pCO2(0,49)/pCO2(0,40): DEA pula muito (>5x), MDEA suave (<5x)
    r_dea = DEA.pCO2(0.49, 313.15, 5.0) / DEA.pCO2(0.40, 313.15, 5.0)
    r_mdea = MDEA.pCO2(0.49, 313.15, 5.0) / MDEA.pCO2(0.40, 313.15, 5.0)
    assert r_dea > 5.0 and r_mdea < 5.0


# ============================ DEA / MDEA column ============================
def _biogas(species, flow, T, P):
    z = [0.0] * len(species)
    z[species.index("CH4")] = 0.47
    z[species.index("CO2")] = 0.53
    return Stream.make(species, z, flow, T, P, "vapor")


def test_dea_column_absorbs_and_balance_closes():
    species = ["CH4", "CO2", "H2O", "DEA"]
    gas = _biogas(species, 100.0, 313.15, 5e5)
    solv = _lean_amine(species, "DEA", 0.30, 20 * 100, 313.15, 5e5)
    spec = AbsorberSpec(N_stages=8, mode="isothermal", T_op=313.15,
                        pressure=5e5, height=12.0, max_iter=400)
    r = Absorber(gas, solv, DEASolvent(), spec).solve()
    assert r.converged
    assert r.CO2_removal > 0.90
    # carregamento rico respeita o limite do carbamato (~0,5)
    i, j = species.index("CO2"), species.index("DEA")
    rich = r.liquid_out.z[i] / max(r.liquid_out.z[j], 1e-12)
    assert rich < 0.55
    # balanço de massa global fecha
    tot_in = gas.flow + solv.flow
    tot_out = r.gas_out.flow + r.liquid_out.flow
    assert abs(tot_in - tot_out) / tot_in < 1e-6


def test_mdea_column_absorbs_weaker_than_mea():
    """MDEA é amina mais fraca: no mesmo L/V e P, remove menos CO2 que MEA."""
    P = 10e5
    # MDEA
    gas_m = _biogas(["CH4", "CO2", "H2O", "MDEA"], 100.0, 313.15, P)
    solv_m = _lean_amine(["CH4", "CO2", "H2O", "MDEA"], "MDEA", 0.40, 25 * 100, 313.15, P)
    spec_m = AbsorberSpec(N_stages=10, mode="isothermal", T_op=313.15,
                          pressure=P, height=14.0, max_iter=400)
    r_m = Absorber(gas_m, solv_m, MDEASolvent(), spec_m).solve()
    assert r_m.converged
    assert r_m.CO2_removal > 0.5                     # absorve, mas menos que MEA
    i, j = ["CH4", "CO2", "H2O", "MDEA"].index("CO2"), ["CH4", "CO2", "H2O", "MDEA"].index("MDEA")
    rich_m = r_m.liquid_out.z[i] / max(r_m.liquid_out.z[j], 1e-12)
    assert rich_m < 1.1                              # α_max ~1,0 (sem carbamato)


# ============================ physical solvents (Selexol/Rectisol) ============================
def test_selexol_K_value_henry_and_pressure():
    s = SelexolSolvent()
    K1 = s.K_value("CO2", 298.15, 10e5, [0, 1, 0, 0])
    K2 = s.K_value("CO2", 298.15, 20e5, [0, 1, 0, 0])
    assert K1 == pytest.approx(2.0 * K2)            # K = H/P -> dobra se P cai pela metade


def test_selexol_co2_more_soluble_than_ch4():
    s = SelexolSolvent()
    P = 20e5
    K_co2 = s.K_value("CO2", 298.15, P, [0, 1, 0, 0])
    K_ch4 = s.K_value("CH4", 298.15, P, [1, 0, 0, 0])
    assert K_co2 < K_ch4                            # CO2 mais solúvel -> K menor


def test_selexol_h2s_more_soluble_than_co2():
    """Selexol é seletivo a H2S: K_H2S < K_CO2 (H2S mais solúvel)."""
    s = SelexolSolvent()
    P = 20e5
    assert s.K_value("H2S", 298.15, P, [0, 0, 0, 1]) < s.K_value("CO2", 298.15, P, [0, 1, 0, 0])


def test_selexol_lower_temperature_more_soluble():
    """T menor -> K menor (mais solúvel); solubilidade exotérmica (dH<0)."""
    s = SelexolSolvent()
    P = 20e5
    assert s.K_value("CO2", 253.15, P, [0, 1, 0, 0]) < s.K_value("CO2", 313.15, P, [0, 1, 0, 0])


def test_selexol_column_absorbs_and_balance():
    species = ["CH4", "CO2", "H2O", "N2"]
    z = [0.0] * 4
    z[species.index("CH4")] = 0.47
    z[species.index("CO2")] = 0.53
    gas = Stream.make(species, z, 100.0, 298.15, 20e5, "vapor")
    sz = [0.0] * 4
    sz[species.index("H2O")] = 1.0                   # placeholder inerte (Selexol não é espécie)
    solv = Stream.make(species, sz, 50 * 100, 298.15, 20e5, "liquid")
    spec = AbsorberSpec(N_stages=8, mode="isothermal", T_op=298.15,
                        pressure=20e5, height=12.0, max_iter=400)
    r = Absorber(gas, solv, SelexolSolvent(), spec).solve()
    assert r.converged
    assert r.CO2_removal > 0.0
    tot_in = gas.flow + solv.flow
    tot_out = r.gas_out.flow + r.liquid_out.flow
    assert abs(tot_in - tot_out) / tot_in < 1e-6


def test_rectisol_K_value_and_cold_selectivity():
    s = RectisolSolvent()
    P = 30e5
    # CO2 mais solúvel que CH4
    assert s.K_value("CO2", 253.15, P, [0, 1, 0, 0]) < s.K_value("CH4", 253.15, P, [1, 0, 0, 0])
    # H2S mais solúvel que CO2 (Rectisol seletivo a H2S em baixa T)
    assert s.K_value("H2S", 253.15, P, [0, 0, 0, 1]) < s.K_value("CO2", 253.15, P, [0, 1, 0, 0])
    # K = H/P
    assert s.K_value("CO2", 253.15, 30e5, [0, 1, 0, 0]) == pytest.approx(
        s.K_value("CO2", 253.15, 10e5, [0, 1, 0, 0]) / 3.0)
