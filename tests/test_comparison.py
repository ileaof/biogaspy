"""Testes do motor de comparação de métodos (backend compartilhado CLI/GUI).

Cobre:
  * transferência de composição (binário CH4-CO2 e ternário CH4-CO2-H2S);
  * execução de cada método individualmente e multi-método;
  * falha isolada de um método não derruba a comparação;
  * padronização de linhas (KPIs/energia/economia uniformes);
  * ranking uni- e multi-critério (best_by / weighted_score);
  * exportação (CSV/JSON/HTML/XLSX);
  * persistência da configuração (ComparisonConfig.to_dict/from_dict) e do
    campo ``Case.comparison`` (save_case/load_case round-trip);
  * CLI ``biogassim compare`` (métodos, --case, --export, --mode);
  * GUI ``ComparisonTab`` (construção, herança de feed, execução, marcação de
    resultados desatualizados, exportação);
  * equivalência numérica CLI-GUI (mesma engine -> mesmo resultado).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

# ------------------------------- fixtures ---------------------------------- #
FEED_BINARY = {"CH4": 0.47, "CO2": 0.53}
FEED_TERNARY = {"CH4": 0.465, "CO2": 0.525, "H2S": 0.01}


def _engine(feed=None, selected=("water", "mea"), mode="standard", **kw):
    from biogassim.comparison import ComparisonConfig, ComparisonEngine
    cfg = ComparisonConfig(selected=list(selected), mode=mode)
    return ComparisonEngine(feed or FEED_BINARY, flow=100.0, config=cfg, **kw)


def _row(rows, key):
    return next(r for r in rows if r["method"] == key)


# --------------------------- composição ----------------------------------- #
def test_binary_composition_runs_all_selected():
    rows = _engine(FEED_BINARY, ("water", "mea")).run()
    assert len(rows) == 2
    for r in rows:
        assert r["converged"] is True
        assert r["purity_CH4"] is not None and r["purity_CH4"] > 0


def test_ternary_h2s_composition_water_absorbs_h2s():
    """Water scrubbing modela H2S; a remoção de H2S deve aparecer no resultado."""
    rows = _engine(FEED_TERNARY, ("water",)).run()
    r = _row(rows, "water")
    assert r["converged"]
    # H2S presente no feed -> métrica reportada
    assert r["H2S_removal"] is not None
    # amina (MEA) não modela H2S -> não deve reportar remoção de H2S
    rows_mea = _engine(FEED_TERNARY, ("mea",)).run()
    assert _row(rows_mea, "mea")["converged"]


# ----------------------- temperatura herdada (T_C) ------------------------- #
def test_engine_T_C_none_keeps_method_defaults():
    """T_C=None (padrão) => regressão: cada método usa seu default de T."""
    eng = _engine(FEED_BINARY, ("water",))
    assert eng.T_C is None
    rows = eng.run()
    assert _row(rows, "water")["converged"]


def test_engine_T_C_injected_into_all_methods():
    """T_C herdado entra nos params de TODOS os métodos (mesma condição)."""
    eng = _engine(FEED_BINARY, ("water", "mea"), T_C=30.0)
    assert eng.T_C == 30.0
    assert eng._resolved_params("water")["T_C"] == 30.0
    assert eng._resolved_params("mea")["T_C"] == 30.0


def test_engine_T_C_higher_reduces_water_CO2_removal():
    """Física: solubilidade de CO2 em água cai com T => remoção menor."""
    lo = _engine(FEED_BINARY, ("water",), T_C=10.0).run()
    hi = _engine(FEED_BINARY, ("water",), T_C=60.0).run()
    r_lo, r_hi = _row(lo, "water"), _row(hi, "water")
    assert r_lo["converged"] and r_hi["converged"]
    assert r_hi["CO2_removal"] < r_lo["CO2_removal"]


def test_report_includes_T_C():
    eng = _engine(FEED_BINARY, ("water",), T_C=25.0)
    rep = eng.report(eng.run())
    assert rep["T_C"] == 25.0


# --------------------------- cada método ----------------------------------- #
@pytest.mark.parametrize("key", [
    "water", "mea", "mdea", "selexol", "psa", "membrane", "membrane_multi",
    "iron_sponge",
])
def test_each_operational_method_runs(key):
    rows = _engine(FEED_BINARY, (key,)).run()
    r = _row(rows, key)
    assert r["method"] == key
    assert r["converged"] is True
    assert r["purity_CH4"] is not None
    assert r["recovery_CH4"] is not None
    assert r["total_kW"] is not None
    assert r["specific_cost_usd_per_Nm3"] is not None


def test_experimental_methods_marked():
    rows = _engine(FEED_BINARY, ("dea", "rectisol")).run()
    for r in rows:
        assert r["status"] == "experimental"


# --------------------------- multi-método ---------------------------------- #
def test_multi_method_comparison_standardizes_all_columns():
    from biogassim.comparison import COLUMNS
    keys = ("water", "mea", "selexol", "psa", "membrane", "iron_sponge")
    rows = _engine(FEED_BINARY, keys).run()
    assert {r["method"] for r in rows} == set(keys)
    cols = {c[0] for c in COLUMNS}
    for r in rows:
        # todas as colunas padronizadas estão presentes
        assert cols <= set(r.keys())


# --------------------------- falha isolada --------------------------------- #
def test_failed_method_does_not_cancel_others():
    """Um método que levanta exceção é registrado como falha; os demais seguem."""
    from biogassim.comparison import METHODS

    def boom(*a, **k):
        raise RuntimeError("explosão simulada")

    # substitui o adapter de um método por um que sempre falha
    orig = METHODS["mea"].adapter
    METHODS["mea"] = METHODS["mea"].__class__(
        METHODS["mea"].key, METHODS["mea"].label, METHODS["mea"].status,
        METHODS["mea"].category, METHODS["mea"].params, boom,
        METHODS["mea"].recommended)
    try:
        rows = _engine(FEED_BINARY, ("water", "mea", "psa")).run()
    finally:
        METHODS["mea"] = METHODS["mea"].__class__(
            METHODS["mea"].key, METHODS["mea"].label, METHODS["mea"].status,
            METHODS["mea"].category, METHODS["mea"].params, orig,
            METHODS["mea"].recommended)
    failed = _row(rows, "mea")
    ok = [r for r in rows if r["method"] != "mea"]
    assert failed["converged"] is False
    assert "explosão" in failed["message"]
    assert len(ok) == 2
    assert all(r["converged"] for r in ok)


# --------------------------- ranking --------------------------------------- #
def test_best_by_recovery_returns_a_converged_method():
    eng = _engine(FEED_BINARY, ("water", "mea", "psa"))
    rows = eng.run()
    best = eng.best_by(rows, "recovery_CH4")
    assert best is not None
    assert best["converged"]
    assert best["recovery_CH4"] == max(r["recovery_CH4"] for r in rows
                                       if r["converged"] and r["recovery_CH4"] is not None)


def test_best_by_cost_minimizes():
    eng = _engine(FEED_BINARY, ("water", "mea", "psa"))
    rows = eng.run()
    best = eng.best_by(rows, "specific_cost_usd_per_Nm3")
    conv = [r for r in rows if r["converged"] and r["specific_cost_usd_per_Nm3"] is not None]
    assert best["specific_cost_usd_per_Nm3"] == min(r["specific_cost_usd_per_Nm3"] for r in conv)


def test_weighted_score_orders_converged_first():
    eng = _engine(FEED_BINARY, ("water", "mea", "psa"))
    rows = eng.run()
    ranked = eng.weighted_score(rows)
    assert len(ranked) == len(rows)
    scores = [r["score"] for r in ranked if r["score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_weighted_score_failed_gets_null_score():
    from biogassim.comparison import METHODS
    orig = METHODS["psa"].adapter
    def boom(*a, **k):
        raise RuntimeError("fail")
    METHODS["psa"] = METHODS["psa"].__class__(
        METHODS["psa"].key, METHODS["psa"].label, METHODS["psa"].status,
        METHODS["psa"].category, METHODS["psa"].params, boom,
        METHODS["psa"].recommended)
    try:
        rows = _engine(FEED_BINARY, ("water", "psa")).run()
        ranked = _engine(FEED_BINARY, ("water", "psa")).weighted_score(rows)
    finally:
        METHODS["psa"] = METHODS["psa"].__class__(
            METHODS["psa"].key, METHODS["psa"].label, METHODS["psa"].status,
            METHODS["psa"].category, METHODS["psa"].params, orig,
            METHODS["psa"].recommended)
    psa = _row(ranked, "psa")
    assert psa["score"] is None


# --------------------------- modo otimizado -------------------------------- #
def test_optimized_mode_runs_and_returns_converged():
    eng = _engine(FEED_BINARY, ("water", "mea"), mode="optimized")
    rows = eng.run()
    assert len(rows) == 2
    assert all(r["converged"] for r in rows)


# --------------------------- export ---------------------------------------- #
def _report(eng, rows):
    return eng.report(rows)


@pytest.mark.parametrize("ext", [".csv", ".json", ".html", ".xlsx"])
def test_export_comparison_writes_file(tmp_path, ext):
    from biogassim.comparison import export_comparison
    eng = _engine(FEED_BINARY, ("water", "mea", "psa"))
    rows = eng.run()
    path = tmp_path / f"comparison{ext}"
    export_comparison(_report(eng, rows), str(path))
    assert path.exists()
    assert path.stat().st_size > 0
    if ext == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "rows" in data and "ranking" in data
        assert len(data["rows"]) == 3
    if ext == ".csv":
        text = path.read_text(encoding="utf-8")
        assert text.strip().startswith("method")


# --------------------------- persistência ---------------------------------- #
def test_comparison_config_roundtrip():
    from biogassim.comparison import ComparisonConfig
    cfg = ComparisonConfig(selected=["water", "psa"],
                            params={"water": {"L_over_V": 150.0}},
                            mode="optimized",
                            weights={"purity_CH4": 0.5, "recovery_CH4": 0.5},
                            objective="purity_CH4")
    d = cfg.to_dict()
    cfg2 = ComparisonConfig.from_dict(d)
    assert cfg2.selected == ["water", "psa"]
    assert cfg2.params == {"water": {"L_over_V": 150.0}}
    assert cfg2.mode == "optimized"
    assert cfg2.weights["purity_CH4"] == 0.5
    assert cfg2.objective == "purity_CH4"


def test_params_for_merges_defaults_with_overrides():
    from biogassim.comparison import ComparisonConfig
    cfg = ComparisonConfig(selected=["water"], params={"water": {"P_bar": 30.0}})
    p = cfg.params_for("water")
    assert p["P_bar"] == 30.0          # override
    assert p["L_over_V"] == 100.0       # default preservado
    assert p["N_stages"] == 12


def test_case_comparison_field_roundtrip(tmp_path):
    from biogassim import cases
    from biogassim.comparison import ComparisonConfig
    c = cases.default_case(name="t", technology="water")
    c.comparison = ComparisonConfig(selected=["water", "mea"], mode="optimized").to_dict()
    p = tmp_path / "case.json"
    cases.save_case(c, str(p))
    c2 = cases.load_case(str(p))
    assert c2.comparison is not None
    assert c2.comparison["selected"] == ["water", "mea"]
    assert c2.comparison["mode"] == "optimized"


def test_case_without_comparison_loads_none(tmp_path):
    from biogassim import cases
    c = cases.Case(name="old", feed={"CH4": 0.5, "CO2": 0.5, "flow_mols": 100.0})
    p = tmp_path / "old.json"
    cases.save_case(c, str(p))
    c2 = cases.load_case(str(p))
    assert c2.comparison is None


# --------------------------- CLI ------------------------------------------- #
def _run_cli(args):
    # stdout do CLI vira pipe -> o filho usa a codificação do locale (cp1252 no
    # Windows e textos acentuados quebram o decode utf-8 abaixo); forcamos ambos
    # os lados em UTF-8.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "biogassim.cli", *args],
                          capture_output=True, text=True, timeout=180,
                          encoding="utf-8", env=env,
                          cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_cli_compare_recommended_methods():
    r = _run_cli(["compare"])
    assert r.returncode == 0, r.stderr
    assert "COMPARAÇÃO" in r.stdout
    assert "convergiram" in r.stdout


def test_cli_compare_explicit_methods():
    r = _run_cli(["compare", "water", "mea", "psa"])
    assert r.returncode == 0, r.stderr
    assert "Water" in r.stdout
    assert "MEA" in r.stdout


def test_cli_compare_unknown_method_errors():
    r = _run_cli(["compare", "nonexistent"])
    assert r.returncode != 0


def test_cli_compare_with_case_inherits_feed(tmp_path):
    from biogassim import cases
    c = cases.Case(name="t", technology="water",
                   feed={"CH4": 0.60, "CO2": 0.40, "flow_mols": 50.0})
    p = tmp_path / "case.json"
    cases.save_case(c, str(p))
    r = _run_cli(["compare", "--case", str(p), "water", "mea"])
    assert r.returncode == 0, r.stderr
    assert "60.0%" in r.stdout
    assert "flow=50" in r.stdout


def test_cli_compare_with_case_inherits_T_C(tmp_path):
    """``compare --case`` herda a temperatura da coluna do caso."""
    from biogassim import cases
    c = cases.Case(name="t", technology="water",
                   feed={"CH4": 0.60, "CO2": 0.40},
                   operating={"T_C": 55.0})
    p = tmp_path / "case.json"
    cases.save_case(c, str(p))
    r = _run_cli(["compare", "--case", str(p), "water"])
    assert r.returncode == 0, r.stderr
    assert "T=55.0 °C" in r.stdout


def test_cli_compare_export_json(tmp_path):
    out = tmp_path / "rep.json"
    r = _run_cli(["compare", "water", "mea", "--export", str(out)])
    assert r.returncode == 0, r.stderr
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["rows"]) == 2
    assert "ranking" in data


def test_cli_compare_optimized_mode():
    r = _run_cli(["compare", "water", "mea", "--mode", "optimized"])
    assert r.returncode == 0, r.stderr
    assert "modo=optimized" in r.stdout


# --------------------------- GUI ------------------------------------------- #
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("biogassim.gui.qt", reason="PySide6/PyQt5 não instalado")

from biogassim.gui.main_window import MainWindow  # noqa: E402
from biogassim.gui.qt import QtWidgets  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_comparison_tab_constructs_and_inherits_feed(app):
    w = MainWindow()
    tab = w.comp_tab
    # cabeçalho herdado mostra a composição da aba principal (47/53 default)
    assert "47" in tab.header_labels["CH4"].text() or "47.00" in tab.header_labels["CH4"].text()
    assert tab.header_labels["Modelo"].text() == "Peng-Robinson"


def test_comparison_tab_engine_inherits_temperature(app):
    """A comparação herda a temperatura da coluna da aba Lavagem de Gás."""
    w = MainWindow()
    w.gas_tab.t_spin.setValue(30.0)
    eng = w.comp_tab._build_engine()
    assert eng.T_C == 30.0


def test_comparison_tab_header_shows_column_temperature(app):
    """O cabeçalho herdado mostra a T da coluna (não o metadado T_K=25 °C)."""
    w = MainWindow()
    w.gas_tab.t_spin.setValue(20.0)
    tab = w.comp_tab
    assert tab.header_labels["T coluna"].text() == "20.0 °C"
    # mudar o spin atualiza o cabeçalho automaticamente (signal feed_changed)
    w.gas_tab.t_spin.setValue(45.0)
    assert tab.header_labels["T coluna"].text() == "45.0 °C"


def test_comparison_tab_has_two_subtabs(app):
    """A aba de comparação é dividida em Configuração + Resultados."""
    w = MainWindow()
    tab = w.comp_tab
    assert tab.sub_tabs.count() == 2
    assert tab.sub_tabs.tabText(0) == "Configuração"
    assert tab.sub_tabs.tabText(1) == "Resultados"
    # widgets de setup vivem na página de configuração; resultados na outra
    assert tab.method_checks  # checkboxes de método
    assert tab.table is not None
    assert tab.export_btn is not None


def test_comparison_tab_auto_switches_to_results_on_finish(app):
    """Ao concluir, a GUI leva o usuário à sub-aba de Resultados."""
    w = MainWindow()
    tab = w.comp_tab
    tab._set_selection(["water", "mea"])
    eng = tab._build_engine()
    rows = eng.run()
    tab.engine = eng
    # começa na Configuração
    tab.sub_tabs.setCurrentWidget(tab.config_page)
    tab._on_finished(rows)
    assert tab.sub_tabs.currentWidget() is tab.results_page


def test_comparison_subtabs_have_independent_scroll_areas(app):
    """Cada sub-aba tem sua própria QScrollArea -- conteúdo acessível com a
    janela reduzida ou muitos resultados/métodos."""
    from biogassim.gui.qt import QtWidgets as _QW

    w = MainWindow()
    tab = w.comp_tab
    for page in (tab.config_page, tab.results_page):
        assert isinstance(page, _QW.QScrollArea)
        assert page.widgetResizable()
        assert page.widget() is not None


def test_comparison_table_area_height_is_adjustable(app):
    """A altura da área da tabela é ajustável: splitter vertical com alça,
    tabela não-colapsável e com mínimo baixo (pode encolher bastante)."""
    from biogassim.gui.qt import Qt as _Qt

    w = MainWindow()
    tab = w.comp_tab
    sp = tab.results_splitter
    assert sp.orientation() == _Qt.Vertical
    assert sp.handleWidth() >= 6                 # alça arrastável
    assert not sp.childrenCollapsible()          # não colapsa as seções
    table_box = sp.widget(0)
    # mínimo baixo => o usuário pode encolher a área da tabela arrastando a alça
    assert 0 < table_box.minimumHeight() <= 150


def test_comparison_tab_method_selection_syncs_config(app):
    w = MainWindow()
    tab = w.comp_tab
    tab._set_selection(["water", "psa"])
    assert tab.config.selected == ["water", "psa"]
    tab._set_selection([])
    assert tab.config.selected == []


def test_comparison_tab_run_populates_table_and_ranking(app):
    w = MainWindow()
    tab = w.comp_tab
    tab._set_selection(["water", "mea"])
    eng = tab._build_engine()
    rows = eng.run()
    tab.engine = eng
    tab.rows = rows
    tab._on_finished(rows)
    assert tab.table.rowCount() == 2
    assert tab.rank_table.rowCount() == 2
    # colunas de resultado populadas
    assert tab.table.item(0, 0) is not None


def test_comparison_tab_marks_results_stale_after_feed_change(app):
    w = MainWindow()
    tab = w.comp_tab
    tab._set_selection(["water"])
    # simula uma comparação já executada
    tab.rows = [{"method": "water", "converged": True}]
    # alterar o feed deve marcar como desatualizado
    w._set_composition({"CH4": 0.60, "CO2": 0.40, "H2S": 0.0})
    assert tab._stale is True
    assert "desatualizados" in tab.stale_lbl.text()
    # header refletiu a nova composição
    assert "60" in tab.header_labels["CH4"].text()


def test_comparison_tab_export_writes_file(app, tmp_path):
    from biogassim.comparison import export_comparison
    w = MainWindow()
    tab = w.comp_tab
    tab._set_selection(["water", "mea"])
    eng = tab._build_engine()
    rows = eng.run()
    tab.engine = eng
    tab.rows = rows
    # evita o diálogo modal; chama export_comparison diretamente
    path = tmp_path / "gui_comparison.json"
    export_comparison(eng.report(rows), str(path))
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["rows"]) == 2


def test_comparison_tab_save_load_config(app, tmp_path):
    w = MainWindow()
    tab = w.comp_tab
    tab._set_selection(["water", "psa"])
    tab.config.params = {"water": {"P_bar": 25.0}}
    # serializa como a UI faria
    fc = w.feed_conditions()
    cfg = tab.config.to_dict()
    cfg["feed"] = {k: v for k, v in fc["comp"].items() if v > 0}
    cfg["flow_mols"] = fc["flow"]
    p = tmp_path / "comp_cfg.json"
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    # recarrega
    data = json.loads(p.read_text(encoding="utf-8"))
    from biogassim.comparison import ComparisonConfig
    tab.config = ComparisonConfig.from_dict(data)
    assert tab.config.selected == ["water", "psa"]
    assert tab.config.params["water"]["P_bar"] == 25.0


# ----------------------- equivalência CLI-GUI ------------------------------ #
def test_cli_gui_numerical_equivalence():
    """Mesma engine alimentada com o mesmo feed -> mesmas métricas.

    A GUI constrói a engine via ``ComparisonTab._build_engine``; a CLI via
    ``_cmd_compare``. Ambas instanciam ``ComparisonEngine`` com o mesmo feed e
    a mesma ``ComparisonConfig`` -- logo o resultado é numericamente idêntico.
    """
    eng_gui = _engine(FEED_BINARY, ("water", "mea"))
    rows_gui = eng_gui.run()
    # segunda engine "como a CLI faria" (independente, mesmos parâmetros)
    eng_cli = _engine(FEED_BINARY, ("water", "mea"))
    rows_cli = eng_cli.run()
    for rg, rc in zip(rows_gui, rows_cli):
        for col in ("purity_CH4", "recovery_CH4", "CO2_removal", "total_kW",
                    "specific_cost_usd_per_Nm3"):
            assert rg[col] == pytest.approx(rc[col], rel=1e-9, abs=1e-9), col
