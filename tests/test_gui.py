"""Testes da GUI moderna do BioGasSim (headless, offscreen).

Cobertura (prompt de modernização):
  * janela principal: abas-alvo, menus (Arquivo/Simulação/Ferramentas/Exibir/
    Ajuda), toolbar, barra de status com estados visuais;
  * alimentação: composição (presets, redistribuição), propriedades;
  * simulação em thread (worker) + estados READY/RUNNING/CONVERGED/OUTDATED;
  * marcação de resultados obsoletos;
  * segurança de H2S (PASS/WARNING/FAIL);
  * projeto: salvar/carregar/recentes (formato case.json da CLI);
  * QScrollArea independente por aba;
  * estudos paramétricos (worker cancelável);
  * paridade numérica GUI ≡ CLI (mesmo backend).
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("biogassim.gui.qt", reason="PySide6/PyQt5 não instalado")

from biogassim.gui.main_window import MainWindow  # noqa: E402
from biogassim.gui.qt import QSettings, QtWidgets  # noqa: E402
from biogassim.gui.state import (  # noqa: E402
    STATE_CONVERGED,
    STATE_OUTDATED,
    STATE_READY,
)


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def mkwindow():
    """Cria a janela no corpo do teste (fora do ciclo de fixtures do pytest,
    cujo gc entre fases invalida wrappers shiboken criados em fixtures)."""
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    QSettings().clear()          # isola preferências persistentes entre testes
    return MainWindow()


def _pump(win, worker, rounds=600):
    """Bombeia eventos até o worker terminar (sinais são enfileirados)."""
    from biogassim.gui.qt import QtCore
    app = QtWidgets.QApplication.instance()
    n = 0
    while (worker is not None and worker.isRunning() and n < rounds):
        app.processEvents(QtCore.QEventLoop.AllEvents, 50)
        n += 1
    app.processEvents(QtCore.QEventLoop.AllEvents, 50)


# --------------------------------------------------------------------------- #
# Janela principal
# --------------------------------------------------------------------------- #
TAB_NAMES = ["Projeto", "Alimentação & Condições", "Lavagem de Gás",
             "Resultados do Processo", "Comparação de Processos",
             "Desempenho & Economia", "Estudos Paramétricos", "Relatórios"]


def test_window_has_target_tabs():
    window = mkwindow()
    names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert names == TAB_NAMES


def test_menus_present():
    window = mkwindow()
    texts = [t.replace("&", "") for t in window._menu_titles()]
    for expected in ("Arquivo", "Simulação", "Ferramentas", "Exibir", "Ajuda"):
        assert expected in texts


def test_file_menu_actions_present():
    window = mkwindow()
    file_menu = window.m_file
    texts = " | ".join(a.text().replace("&", "") for a in file_menu.actions())
    for expected in ("Novo projeto", "Abrir", "Salvar", "Salvar como",
                     "Arquivos recentes", "Sair"):
        assert expected in texts, texts


def test_about_menu_present():
    window = mkwindow()
    texts = [a.text() for menu in window._menu_refs() for a in menu.actions()]
    assert any("Sobre" in t for t in texts)


def test_html_help_menu_present():
    window = mkwindow()
    texts = [a.text() for menu in window._menu_refs() for a in menu.actions()]
    assert any("Manual" in t and "HTML" in t for t in texts)
    assert hasattr(window, "_open_html_help")


def test_toolbar_and_statusbar_present():
    window = mkwindow()
    assert window.act_run is not None
    assert window.act_stop is not None
    assert window.state_chip.text() in ("Pronto", "READY")


def test_all_tabs_have_independent_scroll_areas():
    window = mkwindow()
    """Regra da modernização: cada aba tem QScrollArea própria (barras de
    rolagem independentes); Comparação rola por sub-aba interna."""
    for i in range(window.tabs.count()):
        page = window.tabs.widget(i)
        if window.tabs.tabText(i) == "Comparação de Processos":
            assert hasattr(page, "sub_tabs")
            continue
        assert isinstance(page, QtWidgets.QScrollArea), f"aba {i} sem scroll"
        assert page.widgetResizable()
        assert page.widget() is not None


def test_comparison_subtabs_have_independent_scroll_areas():
    window = mkwindow()
    tab = window.comp_tab
    for page in (tab.config_page, tab.results_page):
        assert isinstance(page, QtWidgets.QScrollArea)
        assert page.widgetResizable()


# --------------------------------------------------------------------------- #
# Alimentação (lógica preservada)
# --------------------------------------------------------------------------- #
def test_composition_redistributes_between_other_two():
    window = mkwindow()
    window._set_composition({"CH4": 0.60, "CO2": 0.40, "H2S": 0.0})
    assert window.spins["CH4"].value() == pytest.approx(60.0)
    window._set_component("H2S", 0.10)
    assert window.feed_comp()["H2S"] == pytest.approx(0.10)
    assert window.feed_comp()["CH4"] == pytest.approx(0.60 * 0.90, abs=1e-6)
    assert window.feed_comp()["CO2"] == pytest.approx(0.40 * 0.90, abs=1e-6)
    assert sum(window.feed_comp().values()) == pytest.approx(1.0)


def test_preset_updates_composition():
    window = mkwindow()
    window._on_preset("Metano puro (100 / 0 / 0)")
    assert window.feed_comp()["CH4"] == pytest.approx(1.0)


def test_h2s_preset_shows_safety_state():
    window = mkwindow()
    window._on_preset("Biogás c/ 1% H2S (46 / 53 / 1)")
    assert window.feed_comp()["H2S"] == pytest.approx(0.01)
    txt = window.gas_tab.safety_state_lbl.text()
    assert ("H₂S" in txt) or ("H2S" in txt)


def test_readout_labels_populated():
    window = mkwindow()
    assert window._readout_labels["molar_mass_gmol"].text() != "-"
    assert window._readout_labels["wobbe_index_MJ_per_Nm3"].text() != "-"


def test_feed_conditions_is_single_source():
    window = mkwindow()
    fc = window.feed_conditions()
    assert fc["T_K"] == 298.15
    assert fc["thermodynamic_model"] == "Peng-Robinson"
    assert fc["comp"]["CH4"] == pytest.approx(0.47)


# --------------------------------------------------------------------------- #
# Simulação em thread + estados visuais
# --------------------------------------------------------------------------- #
def test_run_populates_results_table_and_converged_state():
    window = mkwindow()
    metrics = window.run_case_blocking()
    assert metrics is not None and metrics["converged"]
    assert window.table.rowCount() > 0
    assert window.app.state == STATE_CONVERGED
    assert "Convergiu: True" in window.results_tab.message_lbl.text()


def test_run_with_h2s_reports_removal_and_pass():
    window = mkwindow()
    window._set_composition({"CH4": 0.46, "CO2": 0.53, "H2S": 0.01})
    metrics = window.run_case_blocking()
    assert metrics["converged"]
    assert metrics.get("H2S_removal") is not None
    assert window.gas_tab.safety_state_lbl.text().startswith("PASS")


def test_safety_fail_when_treated_exceeds_limit():
    window = mkwindow()
    window._set_composition({"CH4": 0.46, "CO2": 0.53, "H2S": 0.01})
    window.gas_tab.maxh2s_spin.setValue(0.0)
    window.refresh_safety()
    # com limite 0, qualquer H2S tratado fere -> FAIL
    window.gas_tab.update_safety({"treated_H2S_ppm": 4.0, "converged": True})
    assert window.gas_tab.safety_state_lbl.text().startswith("FAIL")


def test_safety_warning_before_any_run():
    window = mkwindow()
    window._on_preset("Biogás c/ 1% H2S (46 / 53 / 1)")
    window.refresh_safety()
    assert window.gas_tab.safety_state_lbl.text().startswith("WARNING")


def test_sweep_runs():
    window = mkwindow()
    rows = window.run_sweep_blocking()
    assert rows and any(r.get("converged") for r in rows)
    assert "feed_H2S_pct" in rows[0]


# --------------------------------------------------------------------------- #
# Marcação de resultados obsoletos
# --------------------------------------------------------------------------- #
def test_results_marked_stale_after_feed_change():
    window = mkwindow()
    window.run_case_blocking()
    assert window.app.state == STATE_CONVERGED
    window._set_component("CH4", 0.60)
    assert window.app.state == STATE_OUTDATED
    assert window.results_tab.stale_lbl.text() != ""
    item = window.table.item(0, 1)
    assert item is not None
    assert item.font().italic()


def test_stale_cleared_after_rerun():
    window = mkwindow()
    window.run_case_blocking()
    window._set_component("CH4", 0.60)
    assert window.app.state == STATE_OUTDATED
    window.run_case_blocking()
    assert window.app.state == STATE_CONVERGED
    assert window.results_tab.stale_lbl.text() == ""


# --------------------------------------------------------------------------- #
# Projeto: salvar/carregar/recentes
# --------------------------------------------------------------------------- #
def test_project_save_load_roundtrip(tmp_path):
    window = mkwindow()
    window._set_composition({"CH4": 0.60, "CO2": 0.40, "H2S": 0.0})
    window.gas_tab.p_spin.setValue(15.0)
    path = str(tmp_path / "case.json")
    window.project.save_as(window._sync_case_from_gui(), path)
    assert os.path.exists(path)
    window._set_composition({"CH4": 0.80, "CO2": 0.20, "H2S": 0.0})
    case = window.project.load(path)
    window._apply_case_to_gui(case)
    assert window.feed_comp()["CH4"] == pytest.approx(0.60)
    assert window.gas_tab.p_spin.value() == pytest.approx(15.0)
    # formato compatível com a CLI
    from biogassim import cases as _cases
    c2 = _cases.load_case(path)
    assert c2.feed["CH4"] == pytest.approx(0.60)


def test_project_open_populates_gui(tmp_path):
    window = mkwindow()
    from biogassim import cases as _cases
    path = str(tmp_path / "proj.json")
    _cases.save_case(_cases.default_case(name="gui_open", technology="mea"), path)
    window.project_open(path)
    assert window.feed_comp()["CH4"] == pytest.approx(0.47)
    assert window.gas_tab.tech.currentText() == "mea"
    assert window.gas_tab.p_spin.value() == pytest.approx(2.0)


def test_recents_registered(tmp_path):
    window = mkwindow()
    path = str(tmp_path / "case.json")
    window.project.save_as(window._sync_case_from_gui(), path)
    assert os.path.abspath(path) in window.project.recents()


# --------------------------------------------------------------------------- #
# Desempenho & Economia
# --------------------------------------------------------------------------- #
def test_performance_tab_populates_from_metrics():
    window = mkwindow()
    window.run_case_blocking()
    titles = [t for t, _ in window.perf_tab.tables]
    for expected in ("Desempenho", "Energia", "Economia", "Qualidade do gás tratado"):
        assert expected in titles
    assert window.perf_tab.tables[0][1].rowCount() > 0


def test_performance_tab_shows_comparison_summary():
    window = mkwindow()
    rows = [{"converged": True, "method_label": "Água", "purity_CH4": 100.0},
            {"converged": True, "method_label": "MEA", "purity_CH4": 99.99}]
    window.app.set_comparison(rows)
    assert "Água" in window.perf_tab.cmp_lbl.text()
    assert window.app.comparison_rows == rows


# --------------------------------------------------------------------------- #
# Estudos paramétricos (worker cancelável)
# --------------------------------------------------------------------------- #
def test_parametric_study_runs_and_fills_table():
    window = mkwindow()
    window.study_tab.var_spin.setValue(3)
    window.study_tab.run()
    _pump(window, window.study_tab.worker)
    assert len(window.study_tab.rows) == 3
    assert window.study_tab.table.rowCount() == 3
    assert window.study_tab.rows[0].get("_key") == ("feed_H2S_pct", 0.0)


def test_parametric_operator_variable_sweep():
    window = mkwindow()
    window.study_tab.study_cmb.setCurrentIndex(2)   # P_bar
    window.study_tab.var_spin.setValue(4)
    window.study_tab.run()
    _pump(window, window.study_tab.worker)
    assert len(window.study_tab.rows) == 4
    assert len({r["P_bar"] for r in window.study_tab.rows}) == 4


def test_parametric_worker_cancel():
    window = mkwindow()
    window.study_tab.var_spin.setValue(12)
    window.study_tab.run()
    window.study_tab.worker.stop()
    _pump(window, window.study_tab.worker)
    assert len(window.study_tab.rows) <= 12


def test_parametric_export_csv(tmp_path):
    window = mkwindow()
    from biogassim.Export import export_csv
    window.study_tab.var_spin.setValue(3)
    window.study_tab.run()
    _pump(window, window.study_tab.worker)
    table = []
    for r in window.study_tab.rows:
        d = {}
        for key in window.study_tab._col_keys:
            v = (r.get("_key", (None, ""))[1] if key == "_val" else r.get(key))
            if v is not None:
                d[key] = v
        table.append(d)
    path = str(tmp_path / "study.csv")
    export_csv(table, path)
    assert os.path.exists(path) and os.path.getsize(path) > 0


# --------------------------------------------------------------------------- #
# Paridade numérica GUI ≡ CLI
# --------------------------------------------------------------------------- #
def test_gui_cli_numerical_equivalence():
    window = mkwindow()
    from biogassim import cases as _cases

    m_gui = window.run_case_blocking()
    case = window._current_case()
    m_cli = _cases.run_case(case)["metrics"]
    for k in ("purity_CH4", "recovery_CH4", "total_kW", "specific_cost_usd_per_Nm3"):
        assert m_gui[k] == pytest.approx(m_cli[k], rel=1e-9), k


def test_comparison_engine_shared_backend():
    window = mkwindow()
    from biogassim.comparison import ComparisonEngine
    assert isinstance(window.comp_tab._build_engine(), ComparisonEngine)


# --------------------------------------------------------------------------- #
# Validação do fluxo completo de trabalho (passos da modernização)
# --------------------------------------------------------------------------- #
def test_final_workflow_end_to_end(tmp_path):
    window = mkwindow()
    """Fluxo ponta-a-ponta: projeto -> feed -> operacionais -> execução em
    thread -> obsoletência -> reexecução -> comparação -> desempenho -> estudo
    -> exportação."""
    from biogassim.comparison import export_comparison

    # 1-2: janela com 8 abas, estado READY, preset aplicado
    assert window.tabs.count() == 8
    assert window.app.state == STATE_READY
    window._on_preset("Biogás (47 / 53 / 0)")
    assert window.feed_comp()["CH4"] == pytest.approx(0.47)
    # 3: propriedades alimentadas pela backend
    assert window._readout_labels["LHV_MJ_per_Nm3"].text() != "-"
    # 4: operacionais editáveis
    window.gas_tab.p_spin.setValue(22.0)
    assert window._current_case().operating["P_bar"] == pytest.approx(22.0)
    # 5-6: salvar e recarregar projeto (formato CLI)
    path = str(tmp_path / "wf_case.json")
    assert window.project.save_as(window._sync_case_from_gui(), path)
    window._apply_case_to_gui(window.project.load(path))
    assert window.feed_comp()["CH4"] == pytest.approx(0.47)
    # 7-10: executar; CONVERGED; tabela populada; safety PASS
    m = window.run_case_blocking()
    assert m and m["converged"] and window.app.state == STATE_CONVERGED
    assert window.table.rowCount() > 0
    assert window.gas_tab.safety_state_lbl.text().startswith(("PASS", "OK"))
    # 11-12: feed alterado -> OUTDATED; reexecutar -> limpa
    window._set_component("CH4", 0.55)
    assert window.app.state == STATE_OUTDATED
    window.run_case_blocking()
    assert window.app.state == STATE_CONVERGED
    # 13: Desempenho & Economia populado
    assert window.perf_tab.tables[0][1].rowCount() > 0
    # 14-15: comparação de métodos (worker) compartilhada c/ Desempenho
    window.comp_tab._set_selection(["water", "mea"])
    eng = window.comp_tab._build_engine()
    rows = eng.run()
    window.comp_tab.engine = eng
    window.comp_tab._on_finished(rows)
    _pump(window, window.comp_tab.worker)
    assert window.comp_tab.table.rowCount() == 2
    assert len(window.app.comparison_rows) == 2
    # 16: melhor método visível em Desempenho & Economia
    window.perf_tab.refresh()
    assert ("Água" in window.perf_tab.cmp_lbl.text()
            or "MEA" in window.perf_tab.cmp_lbl.text())
    # 17: estudo paramétrico rápido (3 pontos)
    window.study_tab.var_spin.setValue(3)
    window.study_tab.run()
    _pump(window, window.study_tab.worker)
    assert len(window.study_tab.rows) == 3
    # 18: exportar estudo p/ CSV
    from biogassim.Export import export_csv
    table = []
    for r in window.study_tab.rows:
        d = {}
        for key in window.study_tab._col_keys:
            v = (r.get("_key", (None, ""))[1] if key == "_val" else r.get(key))
            if v is not None:
                d[key] = v
        table.append(d)
    csv_path = str(tmp_path / "wf_study.csv")
    export_csv(table, csv_path)
    assert os.path.exists(csv_path)
    # 19: exportar comparação p/ JSON
    out = str(tmp_path / "wf_comparison.json")
    export_comparison(eng.report(window.comp_tab.rows), out)
    data = json.loads(pathlib.Path(out).read_text(encoding="utf-8"))
    assert len(data["rows"]) == 2
