"""Testes dos modelos de membrana (1 estágio e multi-estágio)."""
import numpy as np
import pytest

from biogassim.Membranes import (
    MEMBRANES,
    series_stages,
    single_stage,
    two_stage_recycle,
)

SP = ["CH4", "CO2"]
Z = np.array([0.47, 0.53])
F, T = 100.0, 308.15
PF, PP = 10e5, 0.2e5


# ------------------------------- permeância -------------------------------- #
def test_permeance_scales_inverse_thickness():
    m = MEMBRANES["Polyimide"]
    assert m.permeance_si("CO2", 0.5) == pytest.approx(2.0 * m.permeance_si("CO2", 1.0))
    assert m.permeance_si("CO2", 2.0) == pytest.approx(m.perm_si("CO2") / (2.0e-6))


# ----------------------------- estágio único ------------------------------- #
def test_single_stage_theta_monotonic_in_area():
    """Modo rating: mais área -> maior corte θ, maior pureza, menor recuperação."""
    thetas, purities, recoveries = [], [], []
    for A in [4000, 12000, 30000, 80000]:
        r = single_stage("CelluloseAcetate", SP, Z, F, T, PF, PP, area=A)
        thetas.append(r.stage_cut)
        purities.append(r.purity_CH4)
        recoveries.append(r.recovery_CH4)
    assert thetas == sorted(thetas)              # θ crescente
    assert purities == sorted(purities)          # pureza crescente
    assert recoveries == sorted(recoveries, reverse=True)  # recuperação decrescente


def test_single_stage_enriches_ch4_in_retentate():
    """CO2 é mais permeável -> retentado enriquece em CH4 (pureza > alimentação)."""
    r = single_stage("CelluloseAcetate", SP, Z, F, T, PF, PP, area=40000)
    assert r.purity_CH4 > Z[0]                   # > 0.47
    assert r.permeate["CO2"] > r.retentate["CO2"]  # permeado mais rico em CO2


def test_single_stage_component_mass_balance():
    r = single_stage("CelluloseAcetate", SP, Z, F, T, PF, PP, area=30000)
    assert r.permeate_flow + r.retentate_flow == pytest.approx(F)
    for i, s in enumerate(SP):
        lhs = Z[i] * F
        rhs = r.permeate[s] * r.permeate_flow + r.retentate[s] * r.retentate_flow
        assert rhs == pytest.approx(lhs, rel=1e-9, abs=1e-9)


def test_single_stage_design_rating_roundtrip():
    """Design (θ->área) e rating (área->θ) são inversos consistentes."""
    d = single_stage("Polyimide", SP, Z, F, T, PF, PP, stage_cut=0.5)
    assert d.stage_cut == pytest.approx(0.5, abs=1e-3)
    r = single_stage("Polyimide", SP, Z, F, T, PF, PP, area=d.area)
    assert r.stage_cut == pytest.approx(0.5, abs=1e-2)


def test_single_stage_no_driving_force():
    """Sem razão de pressão (P_feed <= P_perm) não há permeação."""
    r = single_stage("Polyimide", SP, Z, F, T, 1e5, 1e5, area=50000)
    assert r.stage_cut == pytest.approx(0.0)
    assert r.retentate["CH4"] == pytest.approx(Z[0])


# --------------------------- dois estágios (reciclo) ----------------------- #
def test_two_stage_recycle_boosts_recovery():
    """O reciclo do permeado recupera o CH4 perdido: recuperação sobe muito
    para pureza comparável à de um único estágio."""
    single = single_stage("Polyimide", SP, Z, F, T, 15e5, 1e5, stage_cut=0.65)
    two = two_stage_recycle("Polyimide", SP, Z, F, T, 15e5, 1e5, cut1=0.65, cut2=0.6)
    assert two.converged
    assert 0.0 < two.recovery_CH4 <= 1.0 + 1e-9
    assert two.purity_CH4 > Z[0]
    assert two.recycle_flow > 0.0
    assert two.recovery_CH4 > single.recovery_CH4 + 0.1   # ganho >10 pontos
    assert two.total_area == pytest.approx(sum(s.area for s in two.stages))


def test_two_stage_recycle_mass_balance():
    two = two_stage_recycle("Polyimide", SP, Z, F, T, 15e5, 1e5, cut1=0.6, cut2=0.5)
    assert two.mass_balance_error < 1e-6
    for i, s in enumerate(SP):
        lhs = Z[i] * F
        rhs = two.product[s] * two.product_flow + two.offgas[s] * two.offgas_flow
        assert rhs == pytest.approx(lhs, rel=1e-6, abs=1e-6)


# --------------------------- N estágios em série --------------------------- #
def test_series_increases_purity_each_stage():
    c = series_stages("Polyimide", SP, Z, F, T, PF, PP, cuts=[0.3, 0.3, 0.3])
    p = [s.purity_CH4 for s in c.stages]
    assert p == sorted(p)                         # pureza sobe a cada estágio
    single = single_stage("Polyimide", SP, Z, F, T, PF, PP, stage_cut=0.3)
    assert c.purity_CH4 > single.purity_CH4       # cascata supera 1 estágio
    assert c.mass_balance_error == pytest.approx(0.0, abs=1e-9)


def test_series_more_stages_higher_purity():
    c2 = series_stages("Polyimide", SP, Z, F, T, PF, PP, cuts=[0.3, 0.3])
    c3 = series_stages("Polyimide", SP, Z, F, T, PF, PP, cuts=[0.3, 0.3, 0.3])
    assert c3.purity_CH4 > c2.purity_CH4
