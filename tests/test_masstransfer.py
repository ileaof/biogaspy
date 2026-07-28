"""Testes de transferência de massa (correlações adimensionais, difusão, filmes)."""
import numpy as np
import pytest

from biogassim.MassTransfer import (reynolds, schmidt, sherwood_packing,
                                     onda_rocha_kl, kg_bravo, HTU, NTU_absorber,
                                     HETP_from_HTU, stage_efficiency,
                                     fuller_gas, wilke_chang, gas_diffusion_volumes,
                                     film_flux, enhancement_factor,
                                     overall_Ky, overall_Kx, interfacial_composition)


def test_reynolds_schmidt_dimensionless():
    # ar: ρ=1.2, u=1, d=0.05, μ=1.8e-5 -> Re ~3333
    Re = reynolds(1.2, 1.0, 0.05, 1.8e-5)
    assert 3000 < Re < 3700
    Sc = schmidt(1.8e-5, 1.2, 2.0e-5)
    assert abs(Sc - 0.75) < 1e-6


def test_fuller_gas_co2_ch4_literature():
    """CO2-CH4 a 298 K, 1 atm: D ~1.6e-5 m²/s (literatura ~1.4-1.7e-5)."""
    v = gas_diffusion_volumes()
    D = fuller_gas(298.15, 101325.0, 44.01, 16.04, v["CO2"], v["CH4"])
    assert 1.2e-5 < D < 2.0e-5


def test_fuller_gas_higher_pressure_lower_diffusion():
    D1 = fuller_gas(298.15, 101325.0, 44.01, 16.04, 26.9, 24.42)
    D10 = fuller_gas(298.15, 10 * 101325.0, 44.01, 16.04, 26.9, 24.42)
    assert D10 == pytest.approx(D1 / 10.0, rel=1e-6)   # D ∝ 1/P


def test_fuller_gas_higher_temperature_higher_diffusion():
    D = [fuller_gas(T, 101325.0, 44.01, 16.04, 26.9, 24.42) for T in (298.15, 400.0)]
    assert D[1] > D[0]                                   # D ∝ T^1.75


def test_wilke_chang_co2_in_water_literature():
    """CO2 em água a 298 K: D ~1.9e-9 m²/s (literatura ~1.7-1.9e-9)."""
    D = wilke_chang(298.15, 1.0, 18.0, 34.0, phi_b=2.6)   # V_a(CO2)~34 cm³/mol
    assert 1.0e-9 < D < 3.0e-9


def test_wilke_chang_viscous_solvent_lower_diffusion():
    D_w = wilke_chang(298.15, 1.0, 18.0, 34.0, phi_b=2.6)   # água 1 cP
    D_g = wilke_chang(298.15, 10.0, 18.0, 34.0, phi_b=2.6)  # 10 cP
    assert D_g == pytest.approx(D_w / 10.0, rel=1e-6)       # D ∝ 1/μ


def test_onda_rocha_and_kg_positive():
    kL = onda_rocha_kl(1000.0, 1e-3, 0.072, 9.81, 1.9e-9, 215.0, 0.94, 0.01, 0.025)
    kg = kg_bravo(1.2, 1.8e-5, 1.6e-5, 215.0, 1.0, 0.025)
    assert kL > 0 and kg > 0


def test_NTU_absorber_log_driving_force():
    # equilíbrio nulo -> NTU = ln(y_in/y_out)
    NTU = NTU_absorber(0.5, 0.1, 0.0, 0.0)
    assert NTU == pytest.approx(np.log(5.0), rel=1e-6)
    # equilíbrio não nulo -> NTU finito e maior
    NTU2 = NTU_absorber(0.5, 0.1, 0.1, 0.02)
    assert np.isfinite(NTU2) and NTU2 > 0


def test_NTU_absorber_pinch_infinite():
    # força motriz cruza zero (pinch) -> NTU = inf
    assert NTU_absorber(0.5, 0.1, 0.4, 0.2) == float("inf")


def test_HTU_and_HETP():
    assert HTU(10.0, 5.0) == pytest.approx(2.0)
    assert HETP_from_HTU(2.0, 1.5) == pytest.approx(3.0)


def test_stage_efficiency_in_bounds_and_increases_with_Ky():
    e1 = stage_efficiency(0.5, 100.0, 100.0, 1.0, 100.0, 0.5)
    e2 = stage_efficiency(0.5, 100.0, 100.0, 5.0, 100.0, 0.5)
    assert 0.0 <= e1 <= 1.0 and 0.0 <= e2 <= 1.0
    assert e2 >= e1                                  # mais Ky -> mais eficiência


def test_enhancement_factor_limits():
    assert enhancement_factor(False, 0.0) == 1.0                       # sem reação
    assert enhancement_factor(True, 0.01) == pytest.approx(1.0, abs=2e-2)  # Ha→0: E→1
    assert enhancement_factor(True, 10.0) == pytest.approx(10.0, rel=1e-3)  # Ha→∞: E→Ha


def test_overall_Ky_Kx_resistances():
    # 1/Ky = 1/ky + m/kx
    Ky = overall_Ky(2.0, 3.0, 1.0)
    assert Ky == pytest.approx(1.0 / (0.5 + 1.0 / 3.0))
    # Ky < min(ky, kx) (soma de resistências)
    assert Ky < min(2.0, 3.0 / 1.0)


def test_interfacial_composition_equilibrium():
    y_i, x_i = interfacial_composition(0.5, 0.01, 2.0, 3.0, 1.0)
    assert y_i == pytest.approx(1.0 * x_i)               # equilíbrio y = m x
    # entre os bulk
    assert 0.01 <= x_i <= 0.5


def test_film_flux():
    assert film_flux(2.0, 0.5, 0.1) == pytest.approx(0.8)   # k(c_b - c_i)