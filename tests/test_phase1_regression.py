"""Regressão da Fase 1 da auditoria (2026-08-30).

Corrige e congela os valores das propriedades de água (Bigg/Kell, Vargaftik),
a regra de Wilke, o NRTL, o import circular Thermodynamics<->Properties e a
rastreabilidade de balanço de massa/convergência do absorvedor.
"""
from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest

from biogassim.Properties.Water import (
    water_density,
    water_surface_tension,
    water_viscosity,
)
from biogassim.Properties.Mixtures import wilke_viscosity
from biogassim.Thermodynamics.ActivityModels import NRTL


# ------------------------- água: densidade ------------------------- #
def test_water_density_reference_points():
    """Bigg/Kell: ρ(25 °C)=997,05; ρ(0 °C)=999,84 kg/m³."""
    assert water_density(298.15) == pytest.approx(997.05, abs=0.10)
    assert water_density(273.15) == pytest.approx(999.84, abs=0.10)


def test_water_density_maximum_near_4C():
    """Densidade tem máximo físico em ~4 °C (não pode crescer com T)."""
    rho4 = water_density(277.15)
    assert rho4 == pytest.approx(999.97, abs=0.05)
    assert water_density(278.15) < rho4          # acima do máximo: cai
    assert water_density(275.15) < rho4          # abaixo do máximo: cai


def test_water_density_90C():
    """Correlação coerente a 90 °C: ~965,5 kg/m³ (antes: 1001,4 -- errado)."""
    assert water_density(363.15) == pytest.approx(965.5, abs=1.5)


# ------------------------- tensão superficial ------------------------ #
def test_water_surface_tension_25C():
    """Vargaftik: σ(25 °C) = 0,0720 N/m (antes 0,216 -- ~3x alto)."""
    assert water_surface_tension(298.15) == pytest.approx(0.0720, abs=0.001)


def test_water_surface_tension_decreases_with_T():
    assert water_surface_tension(353.15) < water_surface_tension(293.15)


# ------------------------- viscosidade de água --------------------- #
def test_water_viscosity_20C():
    assert water_viscosity(293.15) == pytest.approx(1.006e-3, abs=0.02e-3)


# ------------------------- Wilke ----------------------------------- #
# μ a ~300 K (Pa·s) e M (kg/mol) de CH4 e CO2
_WILKE_V = [1.10e-5, 1.50e-5]
_WILKE_M = [0.016043, 0.044010]


def test_wilke_pure_component_reduces_to_self():
    assert wilke_viscosity(_WILKE_V, _WILKE_M, [1.0, 0.0]) == pytest.approx(1.10e-5, rel=1e-6)
    assert wilke_viscosity(_WILKE_V, _WILKE_M, [0.0, 1.0]) == pytest.approx(1.50e-5, rel=1e-6)


def test_wilke_90_10_CH4_CO2_reference():
    """Wilke 90/10 CH4/CO2: ~1,13e-5 Pa·s (era 2,1e-6 -- ~6x baixo)."""
    mu = wilke_viscosity(_WILKE_V, _WILKE_M, [0.9, 0.1])
    assert 1.08e-5 < mu < 1.21e-5


def test_wilke_between_component_values():
    """Mistura fica entre os valores dos componentes puros."""
    mu = wilke_viscosity(_WILKE_V, _WILKE_M, [0.5, 0.5])
    assert 1.10e-5 < mu < 1.50e-5


# ------------------------- NRTL ------------------------------------ #
# par assimétrico de referência usado nos testes abaixo
_TAU = np.array([[0.0, 1.2], [2.5, 0.0]])
_ALPHA = np.array([[0.0, 0.3], [0.3, 0.0]])


def test_nrtl_pure_component_unity_gamma():
    """Limite puro: ln γ_i = 0 quando x_i -> 1 para o PRÓPRIO componente
    (o outro vale γ^∞, diluição infinita, != 1)."""
    gam = NRTL(tau=_TAU, alpha=_ALPHA).gamma(np.array([1.0, 0.0]))
    assert gam[0] == pytest.approx(1.0, abs=1e-12)
    gam = NRTL(tau=_TAU, alpha=_ALPHA).gamma(np.array([0.0, 1.0]))
    assert gam[1] == pytest.approx(1.0, abs=1e-12)


def test_nrtl_hand_computed_binary_point():
    """Ponto binário calculado analiticamente (x=0.5/0.5, τ12=1.2, τ21=2.5,
    α=0.3 -> γ = [1.72945, 2.11151]): trava a implementação de Renon-Prausnitz."""
    gam = NRTL(tau=_TAU, alpha=_ALPHA).gamma(np.array([0.5, 0.5]))
    assert gam[0] == pytest.approx(1.72945, abs=1e-4)
    assert gam[1] == pytest.approx(2.11151, abs=1e-4)


def test_nrtl_gibbs_duhem_differential():
    """Consistência termodinâmica (Gibbs-Duhem diferencial): deve valer
    x1·dlnγ1/dx1 + x2·dlnγ2/dx1 = 0. Detecta transposição de índices."""
    d = 1.0e-6
    x1 = 0.5
    eps = 1.0e-6
    g_p = NRTL(tau=_TAU, alpha=_ALPHA).gamma(np.array([x1 + eps, 1.0 - x1 - eps]))
    g_m = NRTL(tau=_TAU, alpha=_ALPHA).gamma(np.array([x1 - eps, 1.0 - x1 + eps]))
    dln1 = np.log(g_p[0] / g_m[0]) / (2.0 * eps)
    dln2 = np.log(g_p[1] / g_m[1]) / (2.0 * eps)
    resid = x1 * dln1 + (1.0 - x1) * dln2
    assert abs(resid) < 1.0e-5, f"resid Gibbs-Duhem = {resid:.2e}"


def test_nrtl_asymmetric_tau_finite_positive():
    """γ finitos e positivos para par assimétrico (código antigo transpunha índices)."""
    tau = np.array([[0.0, 1.2], [2.5, 0.0]])
    alpha = np.array([[0.0, 0.3], [0.2, 0.0]])
    gam = NRTL(tau=tau, alpha=alpha).gamma(np.array([0.3, 0.7]))
    assert np.all(np.isfinite(gam)) and np.all(gam > 0)


def test_nrtl_bounded_over_grid():
    """Grade de composições: γ finitos, positivos e fisicamente plausíveis."""
    tau = np.array([[0.0, 0.8], [1.6, 0.0]])
    alpha = np.array([[0.0, 0.25], [0.25, 0.0]])
    for xi in np.linspace(0.01, 0.99, 25):
        gam = NRTL(tau=tau, alpha=alpha).gamma(np.array([xi, 1.0 - xi]))
        assert np.all(np.isfinite(gam)) and np.all(gam > 0.05) and np.all(gam < 20.0)


# ------------------------- import circular -------------------------- #
def test_import_thermodynamics_first():
    """`from biogassim.Thermodynamics import PengRobinson` isolado não pode
    falhar com imports circulares (regressão da auditoria)."""
    r = subprocess.run(
        [sys.executable, "-c", "from biogassim.Thermodynamics import PengRobinson"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


# ------------------------- absorvedor: rastreabilidade ------------- #
def _absorber_case():
    from biogassim.Solvents import WaterSolvent
    from biogassim.UnitOperations import Absorber, AbsorberSpec, Stream
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], flow=100.0, T=298.15,
                      P=2.0e6, phase="vapor")
    solv = Stream.make(species, [0.0, 0.0, 1.0], flow=10000.0, T=293.15,
                       P=2.0e6, phase="liquid")
    spec = AbsorberSpec(N_stages=10, packing="Pall_50", mode="isothermal",
                        T_op=293.15, pressure=2.0e6, height=15.0, max_iter=300)
    return Absorber(gas, solv, WaterSolvent(), spec).solve()


def test_absorber_mass_balance_error_available():
    r = _absorber_case()
    assert np.isfinite(r.mass_balance_error)
    assert r.mass_balance_error < 1e-9    # caso convergente: precisão de máquina


def test_absorber_metrics_carry_balance_and_flag():
    from biogassim.Examples.common import metrics_from_absorber
    from biogassim.UnitOperations import Stream
    gas = Stream.make(["CH4", "CO2", "H2O"], [0.47, 0.53, 0.0], 100.0, 298.15, 1.01325e5)
    m = metrics_from_absorber("t", _absorber_case(), gas)
    assert "converged" in m and m["converged"] is True
    assert m["mass_balance_error"] < 1e-9


# ------------------------- GPDC: extrapolação ------------------------ #
def test_is_gpdc_valid_range():
    """X <= 2 é válida; acima do gráfico GPDC a curva extrapola."""
    from biogassim.Hydraulics import is_gpdc_valid
    assert is_gpdc_valid(1.0, 15.0, 1000.0)          # X ~ 0.04
    assert is_gpdc_valid(10.0, 15.0, 1000.0)         # X ~ 0.39
    assert not is_gpdc_valid(100.0, 15.0, 1000.0)    # X ~ 3.9


def test_absorber_high_LV_flags_gpdc_extrapolation():
    """Water scrubbing com (L/V) molar=100: X >> 2, flag e mensagem de
    extrapolação do GPDC (regime de capacidade líquida, Fase 3)."""
    from biogassim.Solvents import WaterSolvent
    from biogassim.UnitOperations import Absorber, AbsorberSpec, Stream
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], flow=100.0, T=298.15,
                      P=2.0e6, phase="vapor")
    solv = Stream.make(species, [0.0, 0.0, 1.0], flow=10000.0, T=293.15,
                       P=2.0e6, phase="liquid")
    spec = AbsorberSpec(N_stages=12, packing="Pall_50", mode="isothermal",
                        T_op=293.15, pressure=2.0e6, height=15.0)
    r = Absorber(gas, solv, WaterSolvent(), spec).solve()
    assert r.gpdc_extrapolated is True
    assert r.flood_parameter_X > 2.0
    assert "GPDC extrapolado" in (r.message or "")


def test_absorber_moderate_LV_within_gpdc():
    """Carga líquida moderada (L/V molar = 5): dentro do gráfico GPDC."""
    from biogassim.Solvents import WaterSolvent
    from biogassim.UnitOperations import Absorber, AbsorberSpec, Stream
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], flow=100.0, T=298.15,
                      P=2.0e6, phase="vapor")
    solv = Stream.make(species, [0.0, 0.0, 1.0], flow=500.0, T=293.15,
                       P=2.0e6, phase="liquid")
    spec = AbsorberSpec(N_stages=12, packing="Pall_50", mode="isothermal",
                        T_op=293.15, pressure=2.0e6, height=15.0)
    r = Absorber(gas, solv, WaterSolvent(), spec).solve()
    assert r.gpdc_extrapolated is False


# ------------------------- bomba ------------------------------------ #
def test_pump_explicit_rho():
    from biogassim.UnitOperations import Stream
    from biogassim.UnitOperations.Auxiliaries import pump
    liq = Stream.make(["H2O", "CO2"], [0.99, 0.01], 10.0, 293.15, 1.0e5, phase="liquid")
    r = pump(liq, 2.0e6, eta=0.7, rho=997.0)
    assert r.work > 0
    mm = 0.99 * 0.018015 + 0.01 * 0.044010          # kg/mol da mistura
    vdot = 10.0 * mm / 997.0                        # m³/s
    assert r.work == pytest.approx(vdot * 1.9e6 / 0.7, rel=1e-3)