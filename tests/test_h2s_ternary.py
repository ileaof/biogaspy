"""Testes da extensão H2S (CH4-CO2-H2S): kij, normalização ternária, regressão
H2S=0, qualidade do gás tratado, segurança, dashboard e CLI.

Cobre os requisitos §4 (EOS/kij), §2 (validação), §16 (testes) e §17 (regressão):
quando H2S=0 a implementação ternária deve reproduzir o simulador binário.
"""
import numpy as np
import pytest

from biogassim import batch, cases, dashboard, safety
from biogassim.Properties import normalize_mixture
from biogassim.Properties.components import get as get_comp
from biogassim.Thermodynamics import PengRobinson, get_kij, kij_matrix


# --------------------------- kij (§4) -------------------------------------- #
def test_kij_ch4_co2_nonzero():
    """kij(CH4,CO2) não é zero -- não se assume mistura geométrica."""
    assert get_kij("CH4", "CO2") == pytest.approx(0.0919, abs=1e-3)
    assert get_kij("CH4", "CO2") > 0.0


def test_kij_h2s_pairs_nonzero():
    """Parâmetros de interação envolvendo H2S são distintos de zero (§4)."""
    assert get_kij("CH4", "H2S") > 0.0
    assert get_kij("CO2", "H2S") > 0.0


def test_kij_symmetric():
    assert get_kij("H2S", "CO2") == get_kij("CO2", "H2S")
    assert get_kij("CO2", "CH4") == get_kij("CH4", "CO2")


def test_kij_matrix_shape_symmetric_zero_diag():
    sp = ["CH4", "CO2", "H2S"]
    k = kij_matrix(sp)
    assert k.shape == (3, 3)
    assert np.allclose(np.diag(k), 0.0)
    assert np.allclose(k, k.T)
    # os três pares do ternário presentes e não-nulos
    assert k[0, 1] > 0 and k[0, 2] > 0 and k[1, 2] > 0


def test_kij_changes_compressibility_of_ternary():
    """A injeção de kij afeta o Z da mistura ternária (prova que está ativa)."""
    sp = ["CH4", "CO2", "H2S"]
    comps = [get_comp(s) for s in sp]
    z = [0.5, 0.4, 0.1]
    Z_kij = PengRobinson(comps, kij=kij_matrix(sp)).Z_and_phi(298.15, 20e5, z).Z
    Z_zero = PengRobinson(comps, kij=np.zeros((3, 3))).Z_and_phi(298.15, 20e5, z).Z
    assert Z_kij != pytest.approx(Z_zero, abs=1e-6)


def test_fugacity_coefficients_ternary_finite():
    """Coeficientes de fugacidade do ternário são finitos e positivos."""
    sp = ["CH4", "CO2", "H2S"]
    comps = [get_comp(s) for s in sp]
    r = PengRobinson(comps, kij=kij_matrix(sp)).Z_and_phi(298.15, 20e5, [0.5, 0.4, 0.1])
    assert np.all(np.isfinite(r.phi))
    assert np.all(r.phi > 0)


# --------------------- normalização / validação ternária (§2) --------------- #
def test_normalize_mixture_ternary():
    x = normalize_mixture({"CH4": 0.46, "CO2": 0.53, "H2S": 0.01})
    assert sum(x.values()) == pytest.approx(1.0)
    assert x["H2S"] == pytest.approx(0.01)


def test_normalize_mixture_renormalizes():
    x = normalize_mixture({"CH4": 46, "CO2": 53, "H2S": 1})   # em %
    assert sum(x.values()) == pytest.approx(1.0)
    assert x["CH4"] == pytest.approx(0.46, abs=1e-6)


def test_validate_case_rejects_negative():
    c = cases.Case(technology="water",
                   feed={"CH4": -0.1, "CO2": 1.1, "flow_mols": 100.0})
    with pytest.raises(ValueError):
        cases.validate_case(c)


def test_validate_case_calcs_third_from_two():
    """Inserir CH4 e CO2 (binário) calcula o complemento; H2S fica 0."""
    c = cases.Case(technology="water", feed={"CH4": 0.47, "CO2": 0.50,
                                              "flow_mols": 100.0})
    cases.validate_case(c)
    assert c.feed["CH4"] + c.feed["CO2"] == pytest.approx(1.0)


# --------------------- solubilidade e equilíbrio H2S (§5, §7) --------------- #
def test_h2s_more_soluble_than_co2_in_water():
    from biogassim.Solvents import WaterSolvent
    w = WaterSolvent()
    # K = y/x = H/P -> K menor = mais solúvel
    assert w.K_value("H2S", 298.15, 20e5, None) < w.K_value("CO2", 298.15, 20e5, None)


def test_h2s_henry_temperature_depends():
    """H2S mais solúvel em água fria (dHsol > 0, exotérmica)."""
    from biogassim.Thermodynamics.Henry import henry_water
    hl = henry_water()
    assert hl.H("H2S", 283.15) < hl.H("H2S", 303.15)


# --------------------- water scrubbing (§6, §9) ----------------------------- #
def _run(feed, op=None):
    op = op or {"P_bar": 20.0, "L_over_V": 100.0, "N_stages": 12, "height_m": 15.0}
    return cases.run_case(cases.Case(technology="water", feed=feed, operating=op))["metrics"]


def test_ternary_converges_and_removes_h2s():
    m = _run({"CH4": 0.46, "CO2": 0.53, "H2S": 0.01, "flow_mols": 100.0})
    assert m["converged"]
    assert m["H2S_removal"] > 95
    assert m["purity_CH4"] > 95
    assert m["CO2_removal"] > 90


def test_treated_gas_quality_reported():
    m = _run({"CH4": 0.46, "CO2": 0.53, "H2S": 0.01, "flow_mols": 100.0})
    for k in ("treated_CH4_pct", "treated_CO2_pct", "treated_H2S_pct", "treated_H2S_ppm",
              "treated_LHV_MJ_per_Nm3", "treated_HHV_MJ_per_Nm3",
              "treated_wobbe_MJ_per_Nm3", "treated_specific_gravity",
              "liquid_H2S_loading_mol_per_mol"):
        assert k in m, f"métrica {k} ausente"
    # gás tratado é quase puro CH4 -> Wobbe ~ biometano (50-55 MJ/Nm3)
    assert 50 < m["treated_wobbe_MJ_per_Nm3"] < 56


def test_ch4_loss_associated_with_h2s_removal():
    """Remoção de H2S (e CO2) carrega algum CH4 -- perda de metano > 0."""
    m = _run({"CH4": 0.46, "CO2": 0.53, "H2S": 0.01, "flow_mols": 100.0})
    assert m["methane_loss"] > 0
    assert m["recovery_CH4"] < 100


# --------------------- regressão H2S = 0 (§17) ------------------------------ #
def test_h2s_zero_reproduces_binary():
    """H2S=0 no feed ternário == feed binário (mesmas métricas, tolerância 1e-9)."""
    op = {"P_bar": 20.0, "L_over_V": 100.0, "N_stages": 12, "height_m": 15.0}
    m_bin = _run({"CH4": 0.47, "CO2": 0.53, "flow_mols": 100.0}, op)
    m_tri = _run({"CH4": 0.47, "CO2": 0.53, "H2S": 0.0, "flow_mols": 100.0}, op)
    for k in ("purity_CH4", "recovery_CH4", "CO2_removal", "methane_loss",
              "diameter_m", "height_m", "total_kW"):
        assert m_tri[k] == pytest.approx(m_bin[k], abs=1e-9), f"{k} diverge"


def test_h2s_zero_has_no_h2s_metrics():
    m = _run({"CH4": 0.47, "CO2": 0.53, "H2S": 0.0, "flow_mols": 100.0})
    assert "H2S_removal" not in m
    assert m.get("treated_H2S_pct") == 0.0 or m.get("treated_H2S_pct") is None


# --------------------- segurança (§14) ------------------------------------- #
def test_safety_warnings_when_h2s_present():
    w = safety.h2s_warnings(0.01, treated_h2s_ppm=5.0, liquid_h2s_loading=1e-4)
    assert len(w) >= 2
    assert any("H2S" in x or "H₂S" in x for x in w)


def test_safety_no_warnings_without_h2s():
    assert safety.h2s_warnings(0.0) == []


def test_engine_suitable_respects_limit():
    safety.set_max_h2s_treated_ppm(10.0)
    assert safety.engine_suitable(5.0)
    assert not safety.engine_suitable(20.0)
    safety.set_max_h2s_treated_ppm(4.0)
    assert not safety.engine_suitable(5.0)
    safety.set_max_h2s_treated_ppm(10.0)  # restaura default


def test_safety_distinguishes_feed_treated_liquid():
    w = safety.h2s_warnings(0.02, treated_h2s_ppm=100.0, liquid_h2s_loading=0.01)
    text = " ".join(w)
    assert "alimentacao" in text.lower()
    assert "tratado" in text.lower()
    assert "liquida" in text.lower()


# --------------------- dashboard (§15) ------------------------------------- #
def test_dashboard_sections_when_h2s_present():
    m = _run({"CH4": 0.46, "CO2": 0.53, "H2S": 0.01, "flow_mols": 100.0})
    out = dashboard.format_dashboard(m)
    assert "FEED GAS" in out
    assert "UPGRADED GAS" in out
    assert "PERFORMANCE" in out
    assert "SAFETY" in out
    assert "H2S" in out


def test_dashboard_no_safety_section_without_h2s():
    m = _run({"CH4": 0.47, "CO2": 0.53, "flow_mols": 100.0})
    out = dashboard.format_dashboard(m)
    assert "FEED GAS" in out
    assert "SAFETY" not in out


# --------------------- CLI (§11) ------------------------------------------- #
def test_cli_set_h2s_and_run(tmp_path, capsys):
    from biogassim.cli import main
    case = str(tmp_path / "case.json")
    main(["set", "CH4=46", "CO2=53", "H2S=1", "--case", case])
    c = cases.load_case(case)
    assert c.feed["H2S"] == pytest.approx(0.01, abs=1e-6)
    assert c.feed["CH4"] + c.feed["CO2"] + c.feed["H2S"] == pytest.approx(1.0)
    main(["run", case])
    out = capsys.readouterr().out
    assert "FEED GAS" in out and "SAFETY" in out


def test_cli_sweep_h2s(capsys):
    from biogassim.cli import main
    main(["sweep", "H2S=0:0.03:0.01", "--tech", "water"])
    out = capsys.readouterr().out
    assert "VARREDURA DE H2S" in out
    assert "H2Srem%" in out


def test_cli_sweep_h2s_exports_csv(tmp_path):
    from biogassim.cli import main
    out = tmp_path / "h2s.csv"
    main(["sweep", "H2S=0:0.02:0.01", "--tech", "water", "--out", str(out)])
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "feed_H2S_pct" in text
    assert "H2S_removal" in text


# --------------------- sweep paramétrico (§13) ------------------------------ #
def test_sweep_h2s_collects_required_metrics():
    rows = cases.sweep_h2s("water", cases.frange(0.0, 0.05, 0.01))
    assert len(rows) == 6
    for r in rows:
        assert "feed_H2S_pct" in r
        assert "H2S_removal" in r
        assert "recovery_CH4" in r
        assert "CO2_removal" in r
        assert "water_m3_per_h" in r
        assert "treated_H2S_ppm" in r


def test_sweep_h2s_only_water():
    with pytest.raises(ValueError):
        cases.sweep_h2s("mea", [0.0, 0.01])


# --------------------- batch (§11) ------------------------------------------ #
def test_batch_reports_h2s_removal_in_sweep():
    rows = batch.run_batch(
        [{"name": "a", "CH4": 0.46, "CO2": 0.53, "H2S": 0.01}],
        technology="water", P_bar=20.0)
    assert rows[0]["upg_H2S_removal"] not in (None, "")
    assert float(rows[0]["upg_H2S_removal"]) > 90
