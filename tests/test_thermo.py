"""Testes de termodinâmica: EOS (Peng-Robinson, SRK), Henry, flash."""
import numpy as np
import pytest

from biogassim.Properties.components import get
from biogassim.Thermodynamics.Flash import isothermal_flash
from biogassim.Thermodynamics.Henry import from_solubility_mol_per_L_atm, henry_water
from biogassim.Thermodynamics.PengRobinson import PengRobinson
from biogassim.Thermodynamics.SRK import SRK


def test_pr_Z_vapor_reasonable():
    """Z de vapor para CH4 puro a baixa pressão deve tender a 1 (gás ideal)."""
    comps = [get("CH4")]
    eos = PengRobinson(comps)
    r = eos.Z_and_phi(298.15, 1.0e5, np.array([1.0]), phase="vapor")
    assert 0.95 < r.Z < 1.05, f"Z={r.Z}"
    assert 0.9 < r.phi[0] < 1.1


def test_pr_binary_phi():
    comps = [get("CH4"), get("CO2")]
    eos = PengRobinson(comps)
    r = eos.Z_and_phi(298.15, 1.0e6, np.array([0.5, 0.5]), phase="vapor")
    assert np.all(r.phi > 0)
    assert np.all(np.isfinite(r.phi))


def test_srk_runs():
    comps = [get("CH4"), get("CO2")]
    eos = SRK(comps)
    r = eos.Z_and_phi(298.15, 1.0e6, np.array([0.5, 0.5]), phase="vapor")
    assert np.all(np.isfinite(r.phi))


def test_henry_CO2_water_25C():
    """Solubilidade de CO2 em água a 25 °C ~ 0.034 mol/(L·atm)."""
    hl = henry_water()
    H = hl.H("CO2", 298.15)
    Vm = 18.0e-6
    # converte H (Pa) de volta para mol/(L·atm)
    hcp = 1.0 / (H * Vm) * 101325.0 / 1000.0
    assert abs(hcp - 0.034) < 0.005, f"hcp={hcp:.4f}"


def test_henry_temperature_trend():
    """CO2 mais solúvel em água fria -> H menor em T menor."""
    hl = henry_water()
    H_hot = hl.H("CO2", 313.15)
    H_cold = hl.H("CO2", 283.15)
    assert H_cold < H_hot, "CO2 deve ser mais solúvel em água fria (H menor)"


def test_solubility_roundtrip():
    H = from_solubility_mol_per_L_atm(0.034)
    Vm = 18.0e-6
    back = 1.0 / (H * Vm) * 101325.0 / 1000.0
    assert abs(back - 0.034) < 1e-6


def test_flash_single_phase_vapor():
    """Mistura CO2/CH4 a 25 °C, 10 bar é totalmente vapor -> beta=1."""
    comps = [get("CO2"), get("CH4")]
    eos = PengRobinson(comps)
    fr = isothermal_flash(eos, np.array([0.5, 0.5]), 298.15, 1.0e6)
    assert fr.beta == pytest.approx(1.0)


def test_flash_two_phase_mass_balance():
    """CO2/água bifásico: V*y + L*x = feed."""
    comps = [get("CO2"), get("H2O")]
    eos = PengRobinson(comps)
    z = np.array([0.2, 0.8])
    fr = isothermal_flash(eos, z, 300.0, 5.0e5)
    mix = fr.beta * fr.y + (1 - fr.beta) * fr.x
    assert np.allclose(mix, z, atol=1e-6)
    # água deve se concentrar na fase líquida
    assert fr.x[1] > fr.y[1]
