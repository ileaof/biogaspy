"""Testes do modelo de casos, execução paramétrica e CLI (Milestone 1)."""
import pytest

from biogassim import cases
from biogassim.cli import main


# ------------------------------- modelo ------------------------------------ #
def test_default_case_is_valid():
    c = cases.validate_case(cases.default_case())
    assert c.feed["CH4"] + c.feed["CO2"] == pytest.approx(1.0)
    assert c.technology in cases.TECHNOLOGIES


def test_validate_normalizes_composition():
    c = cases.Case(feed={"CH4": 0.9, "CO2": 0.9, "flow_mols": 100.0})
    cases.validate_case(c)
    assert c.feed["CH4"] == pytest.approx(0.5)


@pytest.mark.parametrize("case", [
    cases.Case(feed={"CH4": -0.1, "CO2": 0.5, "flow_mols": 100.0}),
    cases.Case(feed={"CH4": 0.5, "CO2": 0.5, "flow_mols": -1.0}),
    cases.Case(technology="xyz"),
])
def test_invalid_cases_rejected(case):
    with pytest.raises(ValueError):
        cases.validate_case(case)


def test_save_load_roundtrip(tmp_path):
    c = cases.default_case(name="t", technology="mea")
    p = tmp_path / "c.json"
    cases.save_case(c, str(p))
    c2 = cases.load_case(str(p))
    assert c2.name == "t"
    assert c2.technology == "mea"
    assert c2.feed["CH4"] == pytest.approx(c.feed["CH4"])


def test_save_case_creates_parent_dir(tmp_path):
    """save_case deve criar o diretório-pai quando ele não existe (ex.: `biogassim set
    ... --case subdir/case.json`)."""
    c = cases.default_case(name="t", technology="water")
    p = tmp_path / "novo_projeto" / "case.json"
    assert not p.parent.exists()
    cases.save_case(c, str(p))
    assert p.exists()
    assert cases.load_case(str(p)).name == "t"


def test_new_project_scaffold(tmp_path):
    proj = tmp_path / "proj"
    cases.new_project(str(proj))
    assert (proj / "case.json").exists()
    assert (proj / "results").is_dir()


def test_frange_inclusive():
    assert cases.frange(0.2, 0.4, 0.1) == [0.2, 0.3, 0.4]


# ------------------------------ execução ----------------------------------- #
def test_run_case_water_metrics():
    m = cases.run_case(cases.default_case(technology="water"))["metrics"]
    for k in ["purity_CH4", "recovery_CH4", "CO2_removal", "methane_loss",
              "solvent_flow_mols", "water_m3_per_h", "total_kW", "flooding_pct",
              "x_CH4", "feed_LHV_MJ_per_Nm3", "specific_cost_usd_per_Nm3"]:
        assert k in m
    assert m["converged"]


def test_run_case_mea_metrics():
    m = cases.run_case(cases.default_case(technology="mea"))["metrics"]
    assert m["converged"]
    assert "rich_loading" in m


def test_run_case_respects_composition():
    lo = cases.run_case(cases.Case(technology="water",
                                   feed={"CH4": 0.30, "CO2": 0.70, "flow_mols": 100.0}))["metrics"]
    hi = cases.run_case(cases.Case(technology="water",
                                   feed={"CH4": 0.80, "CO2": 0.20, "flow_mols": 100.0}))["metrics"]
    assert lo["x_CH4"] == pytest.approx(0.30)
    assert hi["x_CH4"] == pytest.approx(0.80)
    # planta completa (regeneração Wellmann): recuperação robusta (~97-100)
    # em toda a faixa de composição -- feeds com mais CO2 devolvem mais CH4
    # via reciclo, compensando a maior carga; pureza alta nos dois extremos
    for m in (lo, hi):
        assert 95.0 <= m["recovery_CH4"] <= 100.0
        # no extremo pobre em CH4 (30%) o CO2 residual do topo escala com a
        # carga (70% CO2 no feed) -> pureza ~93%; feeds tipicamente >= 40%
        assert m["purity_CH4"] >= 90.0


def test_sweep_composition_recovery_trend():
    # idem: recuperação robusta (não-monótona) na varredura de composição
    rows = cases.sweep_composition("water", ch4_values=cases.frange(0.30, 0.70, 0.20))
    assert all(r["converged"] for r in rows)
    recs = [r["recovery_CH4"] for r in rows]
    assert all(95.0 <= r <= 100.0 for r in recs)
    assert all((r["purity_CH4"] or 0) >= 90.0 for r in rows)


# -------------------------------- CLI -------------------------------------- #
def test_cli_props(capsys):
    main(["props", "CH4=1.0"])
    out = capsys.readouterr().out
    assert "Wobbe" in out
    assert "LHV_MJ_per_Nm3" in out


def test_cli_set_complementary_and_run(tmp_path, capsys):
    case = str(tmp_path / "case.json")
    main(["set", "CH4=0.6", "--case", case])
    c = cases.load_case(case)
    assert c.feed["CO2"] == pytest.approx(0.4)         # fração complementar automática
    main(["run", case])
    out = capsys.readouterr().out
    # dashboard novo (formato feed/upgraded/performance) mostra recuperação de CH4
    assert "CH4 Recovery" in out
    assert "UPGRADED GAS" in out


def test_cli_sweep_exports_csv(tmp_path):
    out = tmp_path / "sweep.csv"
    main(["sweep", "CH4=0.4:0.6:0.1", "--tech", "water", "--out", str(out)])
    assert out.exists()


def test_cli_sweep_exports_xlsx(tmp_path):
    """--out .xlsx gera Excel de verdade (com openpyxl) ou cai em .csv sem ele."""
    out = tmp_path / "sweep.xlsx"
    main(["sweep", "CH4=0.4:0.6:0.1", "--tech", "water", "--out", str(out)])
    assert out.exists() or (tmp_path / "sweep.csv").exists()
    if out.exists():
        openpyxl = pytest.importorskip("openpyxl")
        ws = openpyxl.load_workbook(out)["sweep"]
        assert "specific_cost_usd_per_Nm3" in [c.value for c in ws[1]]


def test_cli_export_falls_back_when_no_openpyxl(tmp_path):
    case = str(tmp_path / "case.json")
    main(["set", "CH4=0.5", "--case", case])
    main(["export", str(tmp_path / "r.xlsx"), "--case", case])
    # xlsx (se openpyxl instalado) ou csv de fallback
    assert (tmp_path / "r.xlsx").exists() or (tmp_path / "r.csv").exists()
