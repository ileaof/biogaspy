"""Fases 2 e 3 da auditoria de prontidão: validação científica e regressões.

Fase 2:
  * Correção de Poynting na fuga líquida (VLE de alta pressão);
  * Tendência de H(T) vs van't Hoff / Sander 2015 (multi-temperatura);
  * Estrutura two-film (limites de K_y/K_x, consistência interfacial,
    controle de filme, recuperação monótona do absorvedor).

Fase 3:
  * Loop de regeneração (balanço de massa, purge/makeup, reciclo de CH4);
  * Secador TSA + ponto de orvalho (Moisture);
  * Dimensionamento por capacidade líquida (X >> 2, Kister);
  * Economia: circulação x consumo de água.
"""
import numpy as np
import pytest

from biogassim.Examples import WaterScrubbing
from biogassim.MassTransfer import interfacial_composition, overall_Kx, overall_Ky
from biogassim.Properties.Moisture import (
    dew_point_H2O,
    water_content_mg_per_nm3,
    water_p_sat,
    y_from_water_content,
)
from biogassim.Solvents import WaterSolvent
from biogassim.Thermodynamics.Henry import HENRY_WATER, HenryLaw, HenryParams, henry_water
from biogassim.UnitOperations import Absorber, AbsorberSpec, Stream, dry_gas, regen_water
from biogassim.UnitOperations.Dryer import DryerResult


# ============================ Fase 2: Poynting ============================== #
def test_poynting_factor_magnitude_20bar():
    """Pi ~ exp(v·(P-Psat)/RT): CO2 a 20 bar, 298 K -> ~2.8%."""
    hw = henry_water()
    f = hw.poynting_factor("CO2", 298.15, 20e5)
    assert 1.01 < f < 1.05


def test_poynting_scales_with_pressure_and_small_at_1atm():
    hw = henry_water()
    f1 = hw.poynting_factor("CO2", 298.15, 1.01325e5)
    f20 = hw.poynting_factor("CO2", 298.15, 20e5)
    f40 = hw.poynting_factor("CO2", 298.15, 40e5)
    assert f1 < 1.005                        # desprezível a 1 atm
    assert f20 < f40                         # cresce com P
    assert f40 > 1.03


def test_poynting_noop_without_v_liq():
    lw = HenryLaw({"Xenon": HenryParams(1.0e8, 298.15, 20000.0)})   # v_liq=0
    assert lw.poynting_factor("Xenon", 298.15, 20e5) == 1.0


def test_K_value_with_poynting():
    hw = henry_water()
    K0 = hw.K_value("CO2", 298.15, 20e5)
    K1 = hw.K_value("CO2", 298.15, 20e5, poynting=True)
    f = hw.poynting_factor("CO2", 298.15, 20e5)
    assert K1 > K0
    assert K1 == pytest.approx(K0 * f, rel=1e-9)


# ==================== Fase 2: H(T) multi-T vs Sander 2015 ================== #
# d(ln kH)/d(1/T) = dHsol/R de Sander (2015), tabla 1 [K]: CO2 ~ 2400,
# CH4 ~ 1900, H2S ~ 2100. O modelo usa dHsol (J/mol): CO2 20000 (2405 K),
# CH4 14000 (1684 K), H2S 21000 (2526 K) -- consistente na faixa de processo
# (30-50 °C); CH4/H2S têm desvio maior nas extremidades.
_SANDER_DH_OVER_R = {"CO2": 2400.0, "CH4": 1900.0, "H2S": 2100.0}
_SANDER_TOL = {"CO2": 0.05, "CH4": 0.20, "H2S": 0.25}


@pytest.mark.parametrize("species", ["CO2", "CH4", "H2S"])
def test_henry_vant_hoff_series_vs_sander(species):
    p = HENRY_WATER[species]
    dh_r_model = p.dHsol / 8.314462618
    for T in (313.15, 323.15):
        # razão de SOLUBILIDADE kH(T)/kH(298): modelo = exp(dH/R·(1/T-1/Tref)),
        # Sander = exp(dH/R_Sander·(1/T-1/298.15))
        model = float(np.exp(dh_r_model * (1.0 / T - 1.0 / p.Tref)))
        sander = float(np.exp(_SANDER_DH_OVER_R[species] * (1.0 / T - 1.0 / 298.15)))
        assert model == pytest.approx(sander, rel=_SANDER_TOL[species]), \
            f"{species} a {T} K: modelo={model:.4f} vs Sander={sander:.4f}"


def test_solubility_decreases_monotonically_with_T():
    """kH cai com T (dissolução exotérmica) para os gases de biogás."""
    for sp in ("CO2", "CH4", "H2S", "N2", "O2"):
        p = HENRY_WATER[sp]
        assert p.H(323.15) > p.H(313.15) > p.H(298.15)     # H cresce -> kH cai


# ======================= Fase 2: estrutural two-film ======================= #
_KY, _KX, _M = 1.0e-3, 1.0e-4, 82.0      # CO2/água a 20 bar: m = H/P ~ 82


def test_overall_Ky_limits():
    assert overall_Ky(_KY, _KX, 0.0) == pytest.approx(_KY)          # m -> 0: gás
    assert overall_Ky(_KY, _KX, 1.0e12) == pytest.approx(_KX / 1e12)  # m -> inf


def test_overall_Kx_limits():
    # m -> 0: Kx -> m·ky -> 0 (com m=0 exato a fórmula é singular; usamos 1e-12)
    assert overall_Kx(_KY, _KX, 1e-12) == pytest.approx(1e-12 * _KY, rel=1e-6)
    assert overall_Kx(_KY, _KX, 1.0e12) == pytest.approx(_KX)       # m -> inf: líquido


def test_interfacial_flux_consistency():
    """Mesmo fluxo dos dois lados da interface + equilíbrio y_i = m·x_i."""
    y, x = 0.53, 1.0e-4
    y_i, x_i = interfacial_composition(y, x, _KY, _KX, _M)
    assert _KY * (y - y_i) == pytest.approx(_KX * (x_i - x))
    assert y_i == pytest.approx(_M * x_i)
    assert x < x_i < y_i / _M < y < 1.0     # direção gás -> líquido (absorção)


def test_liquid_film_controls_co2_in_water():
    """CO2 em água (m >> 1): a resistência controlante é o filme líquido -> Kx ~ kx."""
    Kx = overall_Kx(_KY, _KX, _M)
    assert Kx == pytest.approx(_KX, rel=0.02)


def test_absorber_monotone_in_stages_and_LV():
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], 100.0, 298.15, 20e5, "vapor")

    def run(n_stages, l_over_v):
        solv = Stream.make(species, [0.0, 0.0, 1.0], l_over_v * 100.0,
                           293.15, 20e5, "liquid")
        spec = AbsorberSpec(N_stages=n_stages, packing="Pall_50", mode="isothermal",
                            T_op=293.15, pressure=20e5, height=15.0, max_iter=400)
        r = Absorber(gas, solv, WaterSolvent(), spec).solve()
        assert r.converged
        return r

    r6, r12 = run(6, 100), run(12, 100)
    assert r12.methane_recovery > r6.methane_recovery   # mais estágios retém mais CH4
    assert r12.CO2_removal > r6.CO2_removal             # ... e remove mais CO2
    r60, r100 = run(6, 60), run(6, 100)
    assert r100.CO2_removal > r60.CO2_removal           # mais solvente remove mais CO2
    # ... mas dissolve mais CH4: a recuperação de CH4 CAI com L/V
    assert r100.methane_recovery < r60.methane_recovery


# ===================== Fase 3: loop de regeneração ========================= #
def _rich_water():
    """Água rica típica do fundo do absorvedor (CH4+CO2 dissolvidos)."""
    sp = ["CH4", "CO2", "H2O"]
    z = np.array([1.0e-3, 1.4e-2, 0.985])
    return Stream.make(sp, z, 10000.0, 293.15, 20e5, "liquid")


def test_regen_water_overall_mass_balance():
    rich = _rich_water()
    rg = regen_water(rich, 20e5, P_flash1=10e5, P_flash2=1e5, purge_frac=0.02)
    assert rg.converged
    # identidade da unidade: sai (flash1 + vent + purge + lean) = entra (rich).
    # O makeup é uma corrente equivalente do laço fechado, não insumo da unidade.
    out = (rg.flash1_gas.z * rg.flash1_gas.flow + rg.vent.z * rg.vent.flow
           + rg.purge.z * rg.purge.flow + rg.lean_out.z * rg.lean_out.flow)
    assert np.allclose(out, rich.z * rich.flow, atol=1e-6), \
        f"out={out}, in={rich.z * rich.flow}"


def test_regen_purge_and_makeup_close_water_balance():
    rich = _rich_water()
    rg = regen_water(rich, 20e5, P_flash1=10e5, P_flash2=1e5, purge_frac=0.02)
    i_h2o = rich.species.index("H2O")
    purge_w = rg.purge.flow * rg.purge.z[i_h2o]
    lean_w = rg.lean_out.flow * rg.lean_out.z[i_h2o]
    # purge ~ 2% da água; makeup repõe purge + evaporação -> makeup >= purge
    assert purge_w == pytest.approx(0.02 / 0.98 * lean_w, rel=0.02)
    assert rg.makeup_mols >= purge_w
    # makeup <= purge + água evaporada (evap ~ poucas % do gás liberado)
    evap = rg.flash_details["water_evaporated_mols"]
    assert rg.makeup_mols <= purge_w + evap + 1e-9


def test_regen_lean_is_clean_with_air_strip():
    """Com dessorção por ar o lean sai praticamente sem gás dissolvido."""
    rg = regen_water(_rich_water(), 20e5, P_flash1=10e5, P_flash2=1e5)
    i_h2o = rg.lean_out.species.index("H2O")
    assert rg.lean_out.z[i_h2o] > 0.9999
    assert rg.lean_out.z[rg.lean_out.species.index("CO2")] < 1e-6


def test_regen_flash1_gas_enriched_in_ch4():
    rich = _rich_water()
    rg = regen_water(rich, 20e5, P_flash1=10e5, P_flash2=1e5)
    pct_rich = 100.0 * rich.z[0] / (rich.z[0] + rich.z[1])
    pct_flash1 = rg.flash_details["flash1_gas_CH4_pct"]
    assert pct_flash1 > pct_rich > 0          # K_CH4/K_CO2 >> 1 enriquece o gás
    # crédito de CH4 = CH4 no gás do flash 1
    assert rg.ch4_recovered_mols == pytest.approx(
        rg.flash1_gas.flow * rg.flash1_gas.z[0])


def test_regen_ch4_lost_in_vent_is_small():
    rg = regen_water(_rich_water(), 20e5, P_flash1=10e5, P_flash2=1e5)
    assert 0.0 <= rg.flash_details["ch4_lost_in_vent_mols"] < 0.1 * rg.ch4_recovered_mols


# ===================== Fase 3: secador + ponto de orvalho =================== #
def test_water_psat_literature_points():
    # Magnus (Buck 1996): 2339 Pa (20 °C), 1228 Pa (10 °C), 7384 Pa (40 °C)
    assert water_p_sat(293.15) == pytest.approx(2339.0, rel=0.005)
    assert water_p_sat(283.15) == pytest.approx(1228.0, rel=0.005)
    assert water_p_sat(313.15) == pytest.approx(7384.0, rel=0.005)


def test_dew_point_inversion_roundtrip():
    P = 20e5
    y = water_p_sat(283.15) / P
    assert dew_point_H2O(y, P) == pytest.approx(283.15, abs=0.5)


def test_water_content_roundtrip_mg_per_nm3():
    y0 = 5.0e-4
    mg = water_content_mg_per_nm3(y0)
    assert mg > 0
    assert y_from_water_content(mg) == pytest.approx(y0, rel=1e-9)


def test_dryer_reaches_spec_and_duty_positive():
    sp = ["CH4", "CO2", "H2O"]
    wet = Stream.make(sp, [0.94, 0.03, 0.03], 100.0, 298.15, 20e5, "vapor")
    d = dry_gas(wet, target_mg_per_nm3=60.0)
    assert isinstance(d, DryerResult)
    out_mg = water_content_mg_per_nm3(d.out.z[sp.index("H2O")])
    assert out_mg == pytest.approx(60.0, rel=0.01)
    assert d.water_removed_kg_h > 0
    assert d.regen_duty_kW > 0
    # ponto de orvalho do gás seco é bem mais baixo
    assert d.dew_point_out_K < dew_point_H2O(0.03, 20e5)


def test_dryer_noop_below_spec():
    sp = ["CH4", "CO2", "H2O"]
    dryish = Stream.make(sp, [0.97, 0.03, 1.0e-6], 100.0, 298.15, 20e5, "vapor")
    d = dry_gas(dryish, target_mg_per_nm3=60.0)
    assert d.regen_duty_kW == 0.0
    assert d.water_removed_kg_h == 0.0
    assert d.out.z == pytest.approx(dryish.z)


def test_run_case_dryer_metrics():
    d = WaterScrubbing.run_case(save=False, regen=True, dryer_mg_nm3=60.0)
    m = d["metrics"]
    # feed seco no modelo -> secador é no-op; métricas presentes e coerentes
    assert "dryer_regen_kW" in m
    assert m["dryer_regen_kW"] == 0.0


# ============ Fase 3: dimensionamento por capacidade líquida =============== #
def test_high_LV_sized_by_liquid_capacity():
    """L/V = 200: GPDC estoura (X >> 2) e o diâmetro passa a ser ditado por
    j_L,máx (Kister): D >= sqrt(4·(q_L/j_L,máx)/pi), e flag marca o regime."""
    from biogassim.Hydraulics.Packing import PACKINGS
    j_max = PACKINGS["Pall_50"].max_liquid_flux
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], 100.0, 298.15, 20e5, "vapor")
    lv = 200.0
    solv = Stream.make(species, [0.0, 0.0, 1.0], lv * 100.0, 293.15, 20e5, "liquid")
    spec = AbsorberSpec(N_stages=12, packing="Pall_50", mode="isothermal",
                        T_op=293.15, pressure=20e5, height=15.0, max_iter=400)
    r = Absorber(gas, solv, WaterSolvent(), spec).solve()
    assert r.liquid_capacity_limited
    q_l = (lv * 100.0 * 0.018) / 1000.0               # m³/s (rho_l ~ 1000)
    d_min = float(np.sqrt(4.0 * (q_l / j_max) / np.pi))
    assert r.diameter == pytest.approx(d_min, rel=0.05)
    # e a operação continua física (flooding% baixo no gás, ΔP pequeno)
    assert r.flooding_fraction < 0.75
    assert r.converged


def test_moderate_LV_not_liquid_capacity_limited():
    species = ["CH4", "CO2", "H2O"]
    gas = Stream.make(species, [0.47, 0.53, 0.0], 100.0, 298.15, 20e5, "vapor")
    solv = Stream.make(species, [0.0, 0.0, 1.0], 5.0 * 100.0, 293.15, 20e5, "liquid")
    spec = AbsorberSpec(N_stages=12, packing="Pall_50", mode="isothermal",
                        T_op=293.15, pressure=20e5, height=15.0, max_iter=400)
    r = Absorber(gas, solv, WaterSolvent(), spec).solve()
    assert not r.liquid_capacity_limited


# ================ Fase 3: economia circulação x consumo de água ============= #
def test_water_consumption_is_makeup_not_circulation():
    m = WaterScrubbing.run_case(save=False, regen=True)["metrics"]
    assert m["water_m3_per_h"] < 0.05 * m["water_circulation_m3_per_h"]
    assert m["water_circulation_m3_per_h"] > 500.0          # L/V=100 a 20 bar
    assert 1.0 < m["water_m3_per_h"] < 50.0                 # makeup ~ purge+evap


def test_once_through_water_consumption_equals_circulation():
    m = WaterScrubbing.run_case(save=False, regen=False)["metrics"]
    assert m["water_m3_per_h"] == pytest.approx(m["water_circulation_m3_per_h"])


__all__ = []
