"""Smoke tests da GUI (headless, offscreen).

Constrói a janela e exercita a lógica dos slots sem loop de eventos nem display.
Valida a fiação (composição -> propriedades -> solver -> tabela/gráfico); não
substitui teste visual/interação, impossível neste ambiente sem tela.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# pula todo o módulo se nenhum binding Qt estiver instalado
pytest.importorskip("biogassim.gui.qt", reason="PySide6/PyQt5 não instalado")

from biogassim.gui.main_window import MainWindow  # noqa: E402
from biogassim.gui.qt import QtWidgets  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_window_constructs_with_live_readouts(app):
    w = MainWindow()
    # a leitura de propriedades é preenchida na construção
    assert w._readout_labels["molar_mass_gmol"].text() != "-"
    assert w._readout_labels["wobbe_index_MJ_per_Nm3"].text() != "-"


def test_composition_redistributes_between_other_two(app):
    w = MainWindow()
    w._set_composition({"CH4": 0.60, "CO2": 0.40, "H2S": 0.0})
    assert w.spins["CH4"].value() == pytest.approx(60.0)
    assert w.spins["CO2"].value() == pytest.approx(40.0)
    assert w.spins["H2S"].value() == pytest.approx(0.0)
    # editar H2S para 10% redistribui o restante (90%) preservando CH4:CO2 (60:40)
    w._set_component("H2S", 0.10)
    assert w._comp["H2S"] == pytest.approx(0.10)
    assert w._comp["CH4"] == pytest.approx(0.60 * 0.90, abs=1e-6)
    assert w._comp["CO2"] == pytest.approx(0.40 * 0.90, abs=1e-6)
    # soma fecha em 1
    assert sum(w._comp.values()) == pytest.approx(1.0)


def test_preset_updates_composition(app):
    w = MainWindow()
    w._on_preset("Metano puro (100 / 0 / 0)")
    assert w._comp["CH4"] == pytest.approx(1.0)
    assert w._comp["H2S"] == pytest.approx(0.0)


def test_h2s_preset_shows_safety_warning(app):
    w = MainWindow()
    w._on_preset("Biogás c/ 1% H2S (46 / 53 / 1)")
    assert w._comp["H2S"] == pytest.approx(0.01)
    assert "H2S" in w.safety_lbl.text() or "H₂S" in w.safety_lbl.text()


def test_run_populates_results_table(app):
    w = MainWindow()
    w._set_composition({"CH4": 0.50, "CO2": 0.50, "H2S": 0.0})
    metrics = w._on_run()
    assert metrics is not None and metrics["converged"]
    assert w.table.rowCount() > 0
    assert "Convergiu: True" in w.status.text()


def test_run_with_h2s_reports_removal(app):
    w = MainWindow()
    w._set_composition({"CH4": 0.46, "CO2": 0.53, "H2S": 0.01})
    metrics = w._on_run()
    assert metrics is not None and metrics["converged"]
    assert metrics.get("H2S_removal") is not None


def test_sweep_runs_and_reports(app):
    w = MainWindow()
    rows = w._on_sweep()
    assert rows and any(r.get("converged") for r in rows)
    assert "convergiram" in w.status.text()
    assert "feed_H2S_pct" in rows[0]


def test_simulation_tab_has_scroll_area(app):
    """A aba Simulação tem barra de rolagem própria -- conteúdo acessível com a
    janela reduzida (consistente com as sub-abas de comparação)."""
    w = MainWindow()
    sim = w.tabs.widget(0)              # primeira aba = Simulação
    from biogassim.gui.qt import QtWidgets as _QW
    assert isinstance(sim, _QW.QScrollArea)
    assert sim.widgetResizable()
    assert sim.widget() is not None
