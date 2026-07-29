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


def test_composition_normalizes_and_fills_complement(app):
    w = MainWindow()
    w._set_composition(0.60)
    assert w.ch4_spin.value() == pytest.approx(60.0)
    assert w.co2_spin.value() == pytest.approx(40.0)         # complemento automático
    assert w.ch4_slider.value() == 600
    # editar CO2 atualiza CH4
    w.co2_spin.setValue(30.0)
    assert w._ch4 == pytest.approx(0.70)


def test_preset_updates_composition(app):
    w = MainWindow()
    w._on_preset("Metano puro (100 / 0)")
    assert w._ch4 == pytest.approx(1.0)


def test_run_populates_results_table(app):
    w = MainWindow()
    w._set_composition(0.50)
    metrics = w._on_run()
    assert metrics is not None and metrics["converged"]
    assert w.table.rowCount() > 0
    assert "Convergiu: True" in w.status.text()


def test_sweep_runs_and_reports(app):
    w = MainWindow()
    rows = w._on_sweep()
    assert rows and any(r["converged"] for r in rows)
    assert "convergiram" in w.status.text()
