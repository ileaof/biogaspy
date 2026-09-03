"""Testes do leito fixo de Fe2O3 (iron sponge) -- projeto estequiométrico."""
from __future__ import annotations

import math
import os
import subprocess
import sys

import pytest

import biogassim.Examples  # noqa: F401  (resolve o ciclo comparison<->Examples)
from biogassim.Properties.GasProperties import MOL_PER_NM3, P_NORMAL
from biogassim.UnitOperations import IronSpongeSpec, solve

FEED_TERNARY = {"CH4": 0.63, "CO2": 0.36, "H2S": 0.01}
FEED_BINARY = {"CH4": 0.60, "CO2": 0.40}
FLOW = 120.0


def _solve(**kw):
    comp = kw.pop("composition", FEED_TERNARY)
    flow = kw.pop("flow", FLOW)
    spec = IronSpongeSpec(**kw)
    return solve(spec, comp, flow)


# --------------------------- estequiometria -------------------------------- #
def test_capacity_stoichiometry_none_vs_regen():
    """Capacidade once-through (0,20 g/g) vs acumulada (2,5 g/g): vida ~ x12,5."""
    none = _solve(regen_mode="none")
    regen = _solve(regen_mode="in_situ")
    assert none.life_days is not None and regen.life_days is not None
    ratio = regen.life_days / none.life_days
    assert ratio == pytest.approx(12.5, rel=0.05)   # 1 d.p. de arredondamento


def test_media_mass_and_fe2o3_fraction():
    r = _solve(fe2o3_wt=0.30)
    assert r.fe2o3_mass_kg == pytest.approx(0.30 * r.media_mass_kg, rel=1e-6)
    # sulfur ~ 0,941 do H2S retido (kg S/kg H2S)
    assert r.sulfur_kg_per_day == pytest.approx(
        r.h2s_load_kg_per_day * 0.032065 / 0.034086, rel=1e-6)


# --------------------------- dimensionamento ------------------------------- #
def test_bed_sizing_volume_and_diameter():
    spec = IronSpongeSpec(contact_time_s=100.0, H_over_D=1.5)
    r = solve(spec, FEED_TERNARY, FLOW, T_C=25.0, P_bar=1.10)
    T_K, P = 25.0 + 273.15, 1.10e5
    q = (FLOW / MOL_PER_NM3) * (T_K / 273.15) * (P_NORMAL / P)
    assert r.bed_volume_m3 == pytest.approx(q * 100.0, rel=1e-3)
    assert r.superficial_velocity_m_per_s <= spec.u_max_m_per_s
    assert r.height_m / r.diameter_m == pytest.approx(
        r.bed_volume_m3 / (math.pi * r.diameter_m ** 3 / 4.0), rel=1e-3)


def test_pressure_drop_ergun_order_of_magnitude():
    r = _solve()
    assert 10.0 < r.pressure_drop_Pa < 5000.0
    # partícula menor -> ΔP maior (termo viscoso ~ 1/d_p^2)
    small = solve(IronSpongeSpec(particle_diameter_m=0.003), FEED_TERNARY, FLOW)
    assert small.pressure_drop_Pa > r.pressure_drop_Pa
    # vazão maior -> ΔP maior (D cresce menos que proporcional, u_s cresce)
    big = _solve(flow=300.0)
    assert big.pressure_drop_Pa > r.pressure_drop_Pa


def test_tall_bed_warns_leitos_em_serie():
    r = _solve(flow=500.0)
    assert any("série" in w for w in r.warnings)


# --------------------------- remoção de H2S -------------------------------- #
def test_removal_high_and_monotonic_with_EBCT():
    r100 = _solve(contact_time_s=100.0)
    assert r100.H2S_removal_pct is not None and r100.H2S_removal_pct > 99.5
    ppms = []
    for t in (60.0, 100.0, 180.0):
        r = _solve(contact_time_s=t)
        ppms.append(r.treated_H2S_ppm)
    assert ppms == sorted(ppms, reverse=True)   # ppm decresce com EBCT


def test_life_independent_of_flow_but_falls_with_h2s():
    """EBCT fixo: o leito escala com a vazão => vida não depende da vazão."""
    base = _solve()
    assert base.life_days is not None
    assert _solve(flow=240.0).life_days == pytest.approx(base.life_days, rel=0.02)
    rich = _solve(composition={"CH4": 0.59, "CO2": 0.36, "H2S": 0.05})
    assert rich.life_days < base.life_days


def test_zero_h2s_feed_robust():
    """Feed binário (H2S = 0): sem exceção, sem remoção, dimensionamento ok."""
    r = _solve(composition=FEED_BINARY)
    assert r.converged
    assert r.H2S_removal_pct is None
    assert r.treated_H2S_ppm == 0.0
    assert r.life_days is None and r.media_kg_per_yr is None
    assert r.air_dose_nm3h == 0.0
    assert r.diameter_m > 0 and r.height_m > 0


def test_target_ppm_warning():
    """ppm acima do alvo -> aviso de aumentar EBCT."""
    r = _solve(contact_time_s=60.0, composition={"CH4": 0.63, "CO2": 0.36,
                                                 "H2S": 0.05})
    assert any("EBCT" in w for w in r.warnings)


# ---------------------- regeneração in-situ com ar -------------------------- #
def test_in_situ_air_dosing_and_o2_residual():
    base = _solve(air_excess=0.5)
    more = _solve(air_excess=2.0)
    assert base.air_dose_nm3h > 0.0
    assert more.air_dose_nm3h > base.air_dose_nm3h
    assert 0.0 < base.oxygen_residual_pct < more.oxygen_residual_pct
    # estequiometria: ar = 0,5*(1+excesso)*n_H2S / 0,2095
    n_h2s = FLOW * 0.01 * (1.0 - math.exp(-100.0 / 15.0))
    n_air = 0.5 * n_h2s * 1.5 / 0.2095
    assert base.air_dose_nm3h == pytest.approx(
        n_air * 3600.0 / MOL_PER_NM3, rel=1e-3)


def test_air_dilution_lowers_purity():
    """O N2 do ar dilui o gás tratado: pureza menor com regen in-situ."""
    none = _solve(regen_mode="none")
    insitu = _solve(regen_mode="in_situ")
    assert insitu.purity_CH4 < none.purity_CH4


def test_o2_residual_warning_above_limit():
    r = _solve(air_excess=2.0, composition={"CH4": 0.59, "CO2": 0.36,
                                            "H2S": 0.05})
    assert r.oxygen_residual_pct > 1.0
    assert any("O2 residual" in w for w in r.warnings)


# --------------------------- massa balanceada ------------------------------- #
def test_mass_balance_error_tiny():
    for mode in ("in_situ", "ex_situ", "none"):
        r = _solve(regen_mode=mode)
        assert r.mass_balance_error < 1e-9


def test_invalid_regen_mode_raises():
    with pytest.raises(ValueError):
        IronSpongeSpec(regen_mode="seco")


# ------------------------ integração comparison ----------------------------- #
def test_engine_comparison_iron_sponge_produces_required_metrics():
    from biogassim.comparison import COLUMNS, ComparisonConfig, ComparisonEngine
    cfg = ComparisonConfig(selected=["iron_sponge"])
    eng = ComparisonEngine(FEED_TERNARY, flow=FLOW, config=cfg, T_C=25.0)
    rows = eng.run()
    r = rows[0]
    assert r["converged"] is True
    for k in ("purity_CH4", "recovery_CH4", "total_kW",
              "specific_cost_usd_per_Nm3"):
        assert r[k] is not None
    assert r["H2S_removal"] > 99.0
    assert r["media_kg_per_yr"] is not None and r["media_kg_per_yr"] > 0
    assert "media_kg_per_yr" in {c[0] for c in COLUMNS}


def test_engine_binary_feed_media_null():
    """Feed binário: coluna de meio é None (não há carga de H2S)."""
    from biogassim.comparison import ComparisonConfig, ComparisonEngine
    cfg = ComparisonConfig(selected=["iron_sponge"])
    rows = ComparisonEngine(FEED_BINARY, flow=100.0, config=cfg).run()
    r = rows[0]
    assert r["converged"]
    assert r["media_kg_per_yr"] is None
    assert r["specific_cost_usd_per_Nm3"] is not None


def test_optimized_mode_iron_sponge():
    from biogassim.comparison import ComparisonConfig, ComparisonEngine
    cfg = ComparisonConfig(selected=["iron_sponge"], mode="optimized")
    eng = ComparisonEngine(FEED_TERNARY, flow=100.0, config=cfg, T_C=25.0)
    rows = eng.run()
    assert rows[0]["converged"]
    ebct = eng._resolved_params("iron_sponge")["contact_time_s"]
    assert ebct in (60.0, 100.0, 140.0, 180.0)


def test_media_cost_in_opex():
    """OPEX responde ao preço do meio (media_price_usd_per_t)."""
    from biogassim.comparison import ComparisonConfig, ComparisonEngine
    lo = ComparisonConfig(selected=["iron_sponge"],
                          economics={"media_price_usd_per_t": 100.0})
    hi = ComparisonConfig(selected=["iron_sponge"],
                          economics={"media_price_usd_per_t": 800.0})
    r_lo = ComparisonEngine(FEED_TERNARY, flow=100.0, config=lo, T_C=25.0).run()[0]
    r_hi = ComparisonEngine(FEED_TERNARY, flow=100.0, config=hi, T_C=25.0).run()[0]
    assert r_hi["opex_usd_yr"] > r_lo["opex_usd_yr"]


def test_roundtrip_config_with_iron_sponge():
    from biogassim.comparison import ComparisonConfig
    cfg = ComparisonConfig(
        selected=["iron_sponge"],
        params={"iron_sponge": {"contact_time_s": 120.0, "regen_mode": "ex_situ"}})
    d = cfg.to_dict()
    cfg2 = ComparisonConfig.from_dict(d)
    assert cfg2.params["iron_sponge"]["regen_mode"] == "ex_situ"
    assert cfg2.params_for("iron_sponge")["contact_time_s"] == 120.0


# ------------------------------- CLI ---------------------------------------- #
def _run_cli(args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "biogassim.cli", *args],
                          capture_output=True, text=True, timeout=180,
                          encoding="utf-8", env=env,
                          cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_cli_compare_alias_iron():
    r = _run_cli(["compare", "iron", "iron-sponge", "fe"])
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("Iron Sponge") >= 3


def test_cli_compare_optimized_iron():
    r = _run_cli(["compare", "iron", "--mode", "optimized"])
    assert r.returncode == 0, r.stderr
    assert "modo=optimized" in r.stdout
