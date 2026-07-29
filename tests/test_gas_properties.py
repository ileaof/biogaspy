"""Testes do motor de composição e propriedades de gás CH4-CO2 (Milestone 1)."""
import pytest

from biogassim.Properties import (
    mixture_properties,
    normalize_composition,
)


# ------------------------------ normalização ------------------------------- #
def test_normalization_enforces_sum_to_one():
    x, y = normalize_composition(0.9, 0.9)          # não normalizado
    assert x == pytest.approx(0.5)
    assert y == pytest.approx(0.5)
    assert x + y == pytest.approx(1.0)


def test_normalization_accepts_percentages():
    assert normalize_composition(47, 53) == pytest.approx((0.47, 0.53))


def test_complementary_fraction_is_filled():
    assert normalize_composition(ch4=0.6) == pytest.approx((0.6, 0.4))
    assert normalize_composition(co2=0.4) == pytest.approx((0.6, 0.4))


@pytest.mark.parametrize("ch4,co2", [(-0.1, 0.5), (0.0, 0.0)])
def test_invalid_compositions_rejected(ch4, co2):
    with pytest.raises(ValueError):
        normalize_composition(ch4, co2)


# --------------------------- propriedades vs lit --------------------------- #
def test_pure_methane_matches_literature():
    p = mixture_properties(ch4=1.0, T=298.15, P=101325.0)
    assert p.HHV_MJ_per_Nm3 == pytest.approx(39.8, abs=0.3)   # ~39.8 MJ/Nm³
    assert p.LHV_MJ_per_Nm3 == pytest.approx(35.8, abs=0.3)   # ~35.8 MJ/Nm³
    assert p.LHV_MJ_per_kg == pytest.approx(50.0, abs=0.3)    # ~50 MJ/kg
    assert p.wobbe_index_MJ_per_Nm3 == pytest.approx(53.5, abs=0.5)
    assert p.specific_gravity == pytest.approx(0.554, abs=0.005)
    assert p.Z == pytest.approx(1.0, abs=0.01)                # quase ideal a 1 atm


def test_pure_co2_is_inert_and_denser():
    p = mixture_properties(ch4=0.0, co2=1.0)
    assert p.LHV_MJ_per_Nm3 == pytest.approx(0.0)             # CO2 não queima
    assert p.HHV_MJ_per_Nm3 == pytest.approx(0.0)
    assert p.specific_gravity > 1.0                           # mais denso que o ar


def test_heating_value_scales_with_methane_fraction():
    lo = mixture_properties(ch4=0.30).LHV_MJ_per_Nm3
    mid = mixture_properties(ch4=0.60).LHV_MJ_per_Nm3
    hi = mixture_properties(ch4=0.95).LHV_MJ_per_Nm3
    assert lo < mid < hi
    # LHV por Nm³ é linear na fração de CH4 (CO2 inerte)
    assert mid == pytest.approx(2.0 * lo, rel=1e-6)


def test_real_gas_compressibility_drops_with_pressure():
    z1 = mixture_properties(ch4=0.6, co2=0.4, T=298.15, P=1e5).Z
    z20 = mixture_properties(ch4=0.6, co2=0.4, T=298.15, P=20e5).Z
    assert z1 == pytest.approx(1.0, abs=0.02)
    assert z20 < z1                                           # desvio real a alta P


def test_density_uses_real_Z():
    p = mixture_properties(ch4=0.5, co2=0.5, T=298.15, P=20e5)
    ideal = p.P * p.molar_mass / (8.314 * p.T)
    assert p.density > ideal                                  # Z<1 -> mais denso que ideal
