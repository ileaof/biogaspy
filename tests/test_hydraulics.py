"""Testes de hidráulica de coluna recheiada (flooding, perda de carga, diâmetro)."""
import numpy as np
import pytest

from biogassim.Hydraulics import (PACKINGS, get_packing,
                                 flooding_velocity, operating_velocity,
                                 column_diameter, dry_pressure_drop, wet_pressure_drop)


# ar/água a 1 atm, 20 °C -- ancora de flooding para anéis Pall (Kister)
RHO_G_AIR, RHO_L_WATER, MU_L_WATER = 1.2, 1000.0, 1.0e-3


def test_flooding_pall_rings_matches_literature():
    """Pall 50 mm u_flood ~2.2 m/s; Pall 25 mm ~1.4 m/s (L/G_mass=10, ar/água)."""
    uf50 = flooding_velocity(RHO_G_AIR, RHO_L_WATER, MU_L_WATER, get_packing("Pall_50"), 10.0)
    uf25 = flooding_velocity(RHO_G_AIR, RHO_L_WATER, MU_L_WATER, get_packing("Pall_25"), 10.0)
    assert 1.8 < uf50 < 2.8
    assert 1.1 < uf25 < 1.7


def test_flooding_higher_Fp_lower_velocity():
    """Maior fator de recheio (Pall 25, Fp=180) -> menor u_flood que Pall 50 (Fp=66)."""
    uf50 = flooding_velocity(RHO_G_AIR, RHO_L_WATER, MU_L_WATER, get_packing("Pall_50"), 10.0)
    uf25 = flooding_velocity(RHO_G_AIR, RHO_L_WATER, MU_L_WATER, get_packing("Pall_25"), 10.0)
    assert uf25 < uf50


def test_flooding_higher_gas_density_lower_velocity():
    """Gás mais denso (alta pressão, ρ_g~19.8 a 20 bar) -> menor u_flood."""
    uf1 = flooding_velocity(1.2, 1000.0, MU_L_WATER, get_packing("Pall_50"), 10.0)
    uf20 = flooding_velocity(19.8, 1000.0, MU_L_WATER, get_packing("Pall_50"), 10.0)
    assert uf20 < uf1


def test_flooding_higher_liquid_load_lower_velocity():
    """Maior L/G (mais líquido) -> menor u_flood."""
    uf = [flooding_velocity(RHO_G_AIR, RHO_L_WATER, MU_L_WATER,
                            get_packing("Pall_50"), lg) for lg in (5, 50, 100)]
    assert uf[0] > uf[1] > uf[2]


def test_flooding_viscous_liquid_lower_velocity():
    """Líquido viscoso (óleo, μ=10 cP) -> menor u_flood que água."""
    uf_w = flooding_velocity(RHO_G_AIR, RHO_L_WATER, 1e-3, get_packing("Pall_50"), 10.0)
    uf_o = flooding_velocity(RHO_G_AIR, 900.0, 1e-2, get_packing("Pall_50"), 10.0)
    assert uf_o < uf_w


def test_operating_velocity_and_diameter():
    uf = flooding_velocity(RHO_G_AIR, RHO_L_WATER, MU_L_WATER, get_packing("Pall_50"), 10.0)
    uop = operating_velocity(uf, 0.7)
    assert abs(uop - 0.7 * uf) < 1e-9
    D = column_diameter(10.0, RHO_G_AIR, uop)        # 10 kg/s de gás
    assert D > 0
    # maior vazão mássica -> maior diâmetro
    D2 = column_diameter(20.0, RHO_G_AIR, uop)
    assert D2 > D


def test_dry_pressure_drop_grows_superlinearly_with_u():
    """ΔP ~ u² mas sub-quadrático: o fator de atrito Ψ0 decresce com Re."""
    p = get_packing("Pall_50")
    dp1 = dry_pressure_drop(RHO_G_AIR, 1.0, p)
    dp2 = dry_pressure_drop(RHO_G_AIR, 2.0, p)
    assert dp1 > 0
    ratio = dp2 / dp1
    assert 3.5 < ratio < 4.0            # ~3.9 (Ψ0 cai com Re -> sub-quadrático)


def test_dry_pressure_drop_higher_for_smaller_packing():
    """Pall 25 (mais área, menor d_p) -> maior perda de carga seca que Pall 50."""
    dp25 = dry_pressure_drop(RHO_G_AIR, 2.0, get_packing("Pall_25"))
    dp50 = dry_pressure_drop(RHO_G_AIR, 2.0, get_packing("Pall_50"))
    assert dp25 > dp50


def test_wet_pressure_drop_greater_than_dry():
    p = get_packing("Pall_50")
    dry = dry_pressure_drop(RHO_G_AIR, 1.5, p)
    wet = wet_pressure_drop(RHO_L_WATER, RHO_G_AIR, 1.5, 0.01, p)
    assert wet > dry


def test_wet_reduces_to_dry_when_no_liquid():
    """u_l = 0 -> holdup nulo -> perda molhada = perda seca."""
    p = get_packing("Pall_50")
    dry = dry_pressure_drop(RHO_G_AIR, 1.5, p)
    wet = wet_pressure_drop(RHO_L_WATER, RHO_G_AIR, 1.5, 0.0, p)
    assert wet == pytest.approx(dry, rel=1e-9)


def test_dry_pressure_drop_typical_magnitude():
    """Pall 50 a 2 m/s (ar, 1 atm): perda seca dezenas-hundreds Pa/m."""
    dp = dry_pressure_drop(RHO_G_AIR, 2.0, get_packing("Pall_50"))
    assert 5.0 < dp < 2000.0


def test_packing_database_has_entries():
    for nm in ["Pall_25", "Pall_50", "Mellapak_250Y", "Sulzer_BX"]:
        assert nm in PACKINGS
        p = get_packing(nm)
        assert p.specific_area > 0 and 0.5 < p.void_fraction < 0.999
        assert p.packing_factor > 0
        assert p.C1 > 0 and p.C3 > 0   # constantes de Stichlmair presentes