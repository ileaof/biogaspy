"""Janela principal da GUI do BioGasSim (CH₄–CO₂–H₂S) — arquitetura moderna.

Visão geral (modernização da GUI):
  * **Modelo** (:mod:`biogassim.gui.state`)  -- AppState com sinais compartilhados
    e estado visual (READY/RUNNING/CONVERGED/WARNING/FAILED/OUTDATED).
  * **Projeto** (:mod:`biogassim.gui.project`)  -- novo/abrir/salvar/salvar como/
    recentes reutilizando ``cases.Case`` (mesmo formato do ``case.json`` da CLI).
  * **Workers** (:mod:`biogassim.gui.workers`)  -- toda simulação/estudo roda em
    QThread; a GUI nunca bloqueia.
  * **Abas** (:mod:`biogassim.gui.tabs`)  -- Projeto | Alimentação | Lavagem de
    Gás | Resultados | Comparação | Desempenho & Economia | Estudos | Relatórios,
    cada uma com QScrollArea **independente**.

Toda a ciência continua no backend compartilhado com a CLI (``cases``/
``comparison``/``Properties``) -- nada é duplicado nesta camada.
"""
from __future__ import annotations

from .. import cases
from .project import ProjectManager
from .qt import QSettings, Qt, QtCore, QtGui, QtWidgets, Signal
from .state import (
    STATE_FAILED,
    STATE_READY,
    STATE_RUNNING,
    AppState,
    state_css,
)
from .tabs import (
    FeedTab,
    GasWashingTab,
    ParametricTab,
    PerformanceTab,
    ProjectTab,
    ReportsTab,
    ResultsTab,
    wrap_scroll,
)
from .workers import FunctionWorker

# QAction mudou de QtWidgets (PyQt5) para QtGui (PySide6/PyQt6) -- portável:
QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction  # noqa: B009
QActionGroup = getattr(QtGui, "QActionGroup", None)  # noqa: B009  (Qt6: QtGui)
QDesktopServices = (getattr(QtGui, "QDesktopServices", None)
                    or QtWidgets.QDesktopServices)  # noqa: B009

_SETTINGS_GEOMETRY = "gui/main_window/geometry"
_SETTINGS_THEME = "gui/theme"


class MainWindow(QtWidgets.QMainWindow):
    #: emitido quando a composição/condições da alimentação mudam (a aba de
    #: comparação escuta para herdar o feed e marcar resultados como obsoletos).
    feed_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BioGasSim -- Upgrading de biogás CH₄–CO₂–H₂S")
        self.app = AppState()
        self.project = ProjectManager()
        self.sim_worker: FunctionWorker | None = None
        self._closing = False

        self._build_tabs()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._wire()
        theme = QSettings().value(_SETTINGS_THEME, "light")
        self._apply_theme(theme == "dark")

        # condição inicial: popula leituras/propriedades/segurança
        self.feed_tab.set_composition(dict(self.feed_tab._comp))

    # ================================================================== #
    # Construção da interface
    # ================================================================== #
    def _build_tabs(self):
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)

        # 1) Projeto
        self.project_tab = ProjectTab(self.app, self.project, self)
        self.tabs.addTab(wrap_scroll(self.project_tab), "Projeto")

        # 2) Alimentação & Condições
        self.feed_tab = FeedTab(self.app, self)
        self.tabs.addTab(wrap_scroll(self.feed_tab), "Alimentação & Condições")

        # 3) Lavagem de gás
        self.gas_tab = GasWashingTab(self.app, self)
        self.tabs.addTab(wrap_scroll(self.gas_tab), "Lavagem de Gás")

        # 4) Resultados do processo
        self.results_tab = ResultsTab(self.app, self)
        self.tabs.addTab(wrap_scroll(self.results_tab), "Resultados do Processo")

        # 5) Comparação de métodos (preservada -- já completa)
        from .comparison_tab import ComparisonTab
        self.comp_tab = ComparisonTab(self)
        self.tabs.addTab(self.comp_tab, "Comparação de Processos")

        # 6) Desempenho & Economia
        self.perf_tab = PerformanceTab(self.app)
        self.tabs.addTab(wrap_scroll(self.perf_tab), "Desempenho & Economia")

        # 7) Estudos paramétricos
        self.study_tab = ParametricTab(self.app, self)
        self.tabs.addTab(wrap_scroll(self.study_tab), "Estudos Paramétricos")

        # 8) Relatórios
        self.reports_tab = ReportsTab(self.app, self)
        self.tabs.addTab(wrap_scroll(self.reports_tab), "Relatórios")

        self.setCentralWidget(self.tabs)

    # ------------------------------------------------------------------ #
    # Menu
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        mb = self.menuBar()

        # --- Arquivo --------------------------------------------------- #
        m_file = self.m_file = mb.addMenu("&Arquivo")
        self._add(m_file, "&Novo projeto…", self.project_new, "Ctrl+N")
        self._add(m_file, "&Abrir…", self.project_open, "Ctrl+O")
        self._add(m_file, "&Salvar", self.project_save, "Ctrl+S")
        self._add(m_file, "Salvar &como…", self.project_save_as, "Ctrl+Shift+S")
        self.recent_menu = m_file.addMenu("Arquivos &recentes")
        self._rebuild_recents()
        m_file.addSeparator()
        self._add(m_file, "Sai&r", self.close, "Ctrl+Q")

        # --- Simulação ------------------------------------------------- #
        m_sim = self.m_sim = mb.addMenu("&Simulação")
        self._add(m_sim, "&Executar caso", self._on_run, "F5")
        m_sim.addSeparator()
        self._add(m_sim, "Varredura de &H₂S (água)", self._on_run_h2s_study)
        self._add(m_sim, "Estudo &paramétrico…", self._go_to_studies)

        # --- Ferramentas ----------------------------------------------- #
        m_tools = self.m_tools = mb.addMenu("&Ferramentas")
        self._add(m_tools, "&Relatórios / exportar…", self._go_to_reports)
        self._add(m_tools, "&Comparação de métodos", self._go_to_comparison)
        m_tools.addSeparator()
        self._add(m_tools, "&Limpar resultados", self._clear_results)

        # --- Exibir ---------------------------------------------------- #
        m_view = self.m_view = mb.addMenu("&Exibir")
        for idx, label in enumerate(("Projeto", "Alimentação & Condições",
                                     "Lavagem de Gás", "Resultados do Processo",
                                     "Comparação de Processos",
                                     "Desempenho & Economia",
                                     "Estudos Paramétricos", "Relatórios")):
            act = QAction(label, self)
            act.triggered.connect(lambda _c=False, i=idx: self.tabs.setCurrentIndex(i))
            m_view.addAction(act)
        m_view.addSeparator()
        self.theme_light = QAction("Tema &claro", self, checkable=True)
        self.theme_dark = QAction("Tema &escuro", self, checkable=True)
        self.theme_group = QActionGroup(self) if QActionGroup is not None else None
        if self.theme_group is not None:
            self.theme_group.addAction(self.theme_light)
            self.theme_group.addAction(self.theme_dark)
        self.theme_light.triggered.connect(lambda: self._apply_theme(False))
        self.theme_dark.triggered.connect(lambda: self._apply_theme(True))
        m_view.addAction(self.theme_light)
        m_view.addAction(self.theme_dark)

        # --- Ajuda ----------------------------------------------------- #
        m_help = self.m_help = mb.addMenu("&Ajuda")
        self._add(m_help, "&Manual de Ajuda (HTML)…", self._open_html_help)
        m_help.addSeparator()
        self._add(m_help, "&Sobre o BioGasPy…", self._show_about)

    def _menu_refs(self):
        """Referências diretas aos menus (evita QAction.menu(), que pode
        devolver wrapper inválido em alguns ambientes de teste)."""
        return [self.m_file, self.m_sim, self.m_tools, self.m_view, self.m_help]

    def _menu_titles(self):
        return [m.title() for m in self._menu_refs()]

    @staticmethod
    def _add(menu, text, slot, shortcut=None):
        act = QAction(text, menu)
        if shortcut:
            act.setShortcut(shortcut)
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    # ------------------------------------------------------------------ #
    # Barra de ferramentas
    # ------------------------------------------------------------------ #
    def _build_toolbar(self):
        tb = self.addToolBar("Principal")
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        tb.setIconSize(QtCore.QSize(20, 20))
        act_new = QAction("🆕", self)
        act_new.setToolTip("Novo projeto (Ctrl+N)")
        act_new.triggered.connect(self.project_new)
        act_open = QAction("📂", self)
        act_open.setToolTip("Abrir projeto (Ctrl+O)")
        act_open.triggered.connect(self.project_open)
        act_save = QAction("💾", self)
        act_save.setToolTip("Salvar projeto (Ctrl+S)")
        act_save.triggered.connect(self.project_save)
        self.act_run = QAction("▶ Executar", self)
        self.act_run.setToolTip("Executar caso (F5)")
        self.act_run.triggered.connect(self._on_run)
        self.act_stop = QAction("■ Parar", self)
        self.act_stop.setEnabled(False)
        self.act_stop.setToolTip("Parar estudo/comparação (roda em background)")
        self.act_stop.triggered.connect(self._on_stop_requested)
        act_rep = QAction("📄", self)
        act_rep.setToolTip("Relatórios / exportação")
        act_rep.triggered.connect(self._go_to_reports)
        for a in (act_new, act_open, act_save):
            tb.addAction(a)
        tb.addSeparator()
        for a in (self.act_run, self.act_stop):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(act_rep)

    # ------------------------------------------------------------------ #
    # Barra de status
    # ------------------------------------------------------------------ #
    def _build_statusbar(self):
        sb = self.statusBar()
        self.state_chip = QtWidgets.QLabel("Pronto")
        self.state_chip.setStyleSheet(state_css(STATE_READY))
        self.state_chip.setFixedWidth(140)
        self.state_chip.setAlignment(Qt.AlignCenter)
        sb.addWidget(self.state_chip)
        self.context_lbl = QtWidgets.QLabel("")
        sb.addWidget(self.context_lbl, 1)
        binding = (QtWidgets.QApplication.instance()
                   and QtWidgets.QApplication.instance().__class__.__module__)
        self.qt_lbl = QtWidgets.QLabel(f"Qt: {binding or '?'}")
        sb.addPermanentWidget(self.qt_lbl)

    def _wire(self):
        """Fiação central de sinais (modelo -> visões)."""
        self.app.sim_state_changed.connect(self._on_state_changed)
        self.app.metrics_ready.connect(self._on_metrics)
        self.app.solver_log.connect(lambda line: None)  # (results_tab já escuta)
        self.project.project_changed.connect(self._on_project_changed)
        self.app.error.connect(self._show_error)

        # feed_changed: marca obsoleto (backend state) + projeto sujo
        self.feed_changed.connect(self._on_feed_changed_ui)
        self.comp_tab.comparison_finished.connect(self.app.set_comparison)

    def _show_error(self, msg: str):
        QtWidgets.QMessageBox.warning(self, "BioGasSim", msg)

        self._refresh_title(self.project.path, self.project.dirty)

    # ================================================================== #
    # Estado da alimentação (facades de compatibilidade c/ as abas)
    # ================================================================== #
    @property
    def _comp(self) -> dict:
        return self.feed_tab._comp

    @property
    def spins(self) -> dict:
        return self.feed_tab.spins

    @property
    def sliders(self) -> dict:
        return self.feed_tab.sliders

    @property
    def _readout_labels(self) -> dict:
        return self.feed_tab.readout_labels

    @property
    def safety_lbl(self) -> QtWidgets.QLabel:
        return self.gas_tab.safety_lbl

    @property
    def table(self) -> QtWidgets.QTableWidget:
        return self.results_tab.table

    @property
    def status(self) -> QtWidgets.QLabel:
        return self.results_tab.message_lbl

    # ------------------------------------------------------------------ #
    def feed_comp(self) -> dict:
        return dict(self.feed_tab._comp)

    def feed_conditions(self) -> dict:
        """Estado de alimentação herdado pelas outras abas (fonte única)."""
        return {
            "comp": self.feed_comp(),
            "flow": self.feed_tab.flow_mols(),
            "P_bar": self.gas_tab.p_spin.value(),
            "T_K": 298.15,                      # feed a 25 °C (modelo isotérmico)
            "tech": self.gas_tab.tech.currentText(),
            "thermodynamic_model": "Peng-Robinson",
        }

    def _current_case(self) -> cases.Case:
        feed = {s: v for s, v in self.feed_comp().items() if v > 1e-9}
        if not feed:
            feed = {"CH4": 1.0}
        feed["flow_mols"] = self.feed_tab.flow_mols()
        return cases.Case(
            name=self.project.display_name() or "gui",
            technology=self.gas_tab.tech.currentText(),
            feed=feed,
            operating={"P_bar": self.gas_tab.p_spin.value(),
                       "T_C": self.gas_tab.t_spin.value(),
                       "L_over_V": self.gas_tab.lv_spin.value(),
                       "N_stages": int(self.gas_tab.n_spin.value()),
                       "height_m": self.gas_tab.h_spin.value()},
        )

    # -- handlers de edição --------------------------------------------- #
    def _set_composition(self, comp: dict):
        self.feed_tab.set_composition(comp)

    def _set_component(self, name: str, frac: float):
        self.feed_tab._set_component(name, frac)

    def _on_preset(self, name: str):
        self.feed_tab._on_preset(name)

    def on_operating_changed(self):
        """Qualquer parâmetro operacional mudou: marca feed alterado."""
        self.feed_changed.emit()

    def _on_tech_changed(self, tech: str):
        # aplica condições operacionais padrão da tecnologia
        op = cases.DEFAULT_OPERATING.get(str(tech).lower())
        if op:
            self.gas_tab.p_spin.blockSignals(True)
            self.gas_tab.t_spin.blockSignals(True)
            self.gas_tab.lv_spin.blockSignals(True)
            self.gas_tab.n_spin.blockSignals(True)
            self.gas_tab.h_spin.blockSignals(True)
            try:
                self.gas_tab.p_spin.setValue(op["P_bar"])
                self.gas_tab.t_spin.setValue(op["T_C"])
                self.gas_tab.lv_spin.setValue(op["L_over_V"])
                self.gas_tab.n_spin.setValue(op["N_stages"])
                self.gas_tab.h_spin.setValue(op["height_m"])
            finally:
                for sp in (self.gas_tab.p_spin, self.gas_tab.t_spin,
                           self.gas_tab.lv_spin, self.gas_tab.n_spin,
                           self.gas_tab.h_spin):
                    sp.blockSignals(False)
        self.feed_changed.emit()

    def refresh_safety(self):
        self.gas_tab.update_safety(self.app.metrics)

    def _refresh_safety(self):
        self.refresh_safety()

    def _on_feed_changed_ui(self):
        # estado de resultados obsoletos
        self.app.mark_stale()
        self.project.mark_dirty()
        self.refresh_safety()
        if self.app.metrics is not None:
            # redesenha a tabela como obsoleta (itálico/cinza)
            self.results_tab.fill(self.app.metrics, stale=True)
        self.results_tab.mark_stale_banner(self.app.stale)
        self.app.log("Condições de alimentação alteradas.")

    # ================================================================== #
    # Simulação (thread separada -- GUI nunca bloqueia)
    # ================================================================== #
    def _on_state(self, state):
        pass  # (o chip é atualizado via _on_state_changed)

    def _on_state_changed(self, state: str):
        self.state_chip.setText(state)
        self.state_chip.setStyleSheet(state_css(state))

    def _on_run(self):
        """Executa o caso corrente em background (worker QThread)."""
        if self.sim_worker is not None and self.sim_worker.isRunning():
            return
        case = self._current_case()
        self.app.set_state(STATE_RUNNING)
        self.results_tab.show_message(
            f"Executando {case.technology} | "
            f"{self.feed_tab.format_flow(case.feed.get('flow_mols', 0.0))} | "
            f"{case.operating.get('P_bar')} bar…")
        self.app.log(f">>> Executando caso: tech={case.technology} "
                     f"feed={ {k: v for k, v in case.feed.items() if k != 'flow_mols'} } "
                     f"op={case.operating}")
        self.act_run.setEnabled(False)
        self.sim_worker = FunctionWorker(lambda: cases.run_case(case))
        self.sim_worker.ok.connect(self._on_run_ok)
        self.sim_worker.err.connect(self._on_run_err)
        self.sim_worker.start()

    def run_case_blocking(self) -> dict | None:
        """Executa o caso e espera (para testes; a GUI usa ``_on_run``).

        Bombeia eventos: os sinais ``ok``/``err`` do worker são enfileirados
        (emitidos fora da GUI thread) e só chegam aos slots com um event loop."""
        self._on_run()
        w = self.sim_worker
        if w is not None:
            app = QtWidgets.QApplication.instance()
            while w.isRunning():
                app.processEvents(QtCore.QEventLoop.AllEvents, 50)
            app.processEvents(QtCore.QEventLoop.AllEvents, 50)
        return self.app.metrics

    def run_sweep_blocking(self) -> list[dict]:
        """Varredura H₂S síncrona (compat/testes; GUI usa a aba de estudos)."""
        case = self._current_case()
        comp = self.feed_comp()
        r = comp["CH4"] / max(comp["CH4"] + comp["CO2"], 1e-9)
        return cases.sweep_h2s("water", cases.frange(0.0, 0.05, 0.005),
                               ch4_co2_ratio=r, operating=case.operating,
                               flow=self.feed_tab.flow_spin.value())

    def _on_run_ok(self, payload):
        out = payload if isinstance(payload, dict) and "metrics" in payload \
            else {"metrics": payload, "result": None}
        metrics = out["metrics"]
        result = out.get("result")
        self.app.set_metrics(metrics, result)
        it = metrics.get("iterations", "-")
        pur = metrics.get("purity_CH4")
        rec = metrics.get("recovery_CH4")
        self.results_tab.show_message(
            f"Convergiu: {metrics.get('converged')} | iterações: {it} | "
            f"pureza {pur}% | recuperação {rec}%")
        self.app.log(f"<<< Concluído: convergiu={metrics.get('converged')} "
                     f"iterações={it} pur={pur} rec={rec}")
        self.refresh_safety()
        self.tabs.setCurrentWidget(self.results_tab)

    def _on_run_err(self, msg: str):
        self.app.set_state(STATE_FAILED)
        self.results_tab.show_message(f"Falhou: {msg}")
        self.app.log(f"!!! Erro: {msg}")
        if self.sim_worker is not None and self.sim_worker.trace_text:
            self.app.log(self.sim_worker.trace_text.splitlines()[-1][:300])
        self.act_run.setEnabled(True)

    def _on_metrics(self, _metrics):
        self.act_run.setEnabled(True)
        if self.app.metrics is not None:
            self.results_tab.fill(self.app.metrics, stale=False)
            self.results_tab.mark_stale_banner(False)

    def _on_stop_requested(self):
        """Interrompe os workers canceláveis (estudos/comparação)."""
        stopped = False
        if self.study_tab.worker is not None and self.study_tab.worker.isRunning():
            self.study_tab.worker.stop()
            stopped = True
        if self.comp_tab.worker is not None and self.comp_tab.worker.isRunning():
            self.comp_tab.worker.stop()
            stopped = True
        if stopped:
            self.results_tab.show_message("Interrompendo cálculo em background…")

    # ================================================================== #
    # Ações de projeto
    # ================================================================== #
    def _maybe_save(self) -> bool:
        """Confirma mudanças não salvas. True se pode continuar."""
        if not self.project.dirty:
            return True
        ret = QtWidgets.QMessageBox.question(
            self, "Projeto não salvo",
            "O projeto tem alterações não salvas. Salvar agora?",
            QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard
            | QtWidgets.QMessageBox.Cancel)
        if ret == QtWidgets.QMessageBox.Save:
            return self.project_save()
        return ret == QtWidgets.QMessageBox.Discard

    def _sync_case_from_gui(self) -> cases.Case:
        case = self._current_case()
        case.comparison = self.comp_tab.config.to_dict()
        return case

    def _apply_case_to_gui(self, case: cases.Case):
        comp = {s: case.feed.get(s, 0.0) for s in ("CH4", "CO2", "H2S")}
        self.feed_tab.set_composition(comp)
        self.feed_tab.set_flow_mols(float(case.feed.get("flow_mols", 100.0)))
        idx = self.gas_tab.tech.findText(case.technology)
        if idx >= 0:
            self.gas_tab.tech.setCurrentIndex(idx)
        op = case.operating or {}
        self.gas_tab.p_spin.setValue(float(op.get("P_bar", self.gas_tab.p_spin.value())))
        self.gas_tab.t_spin.setValue(float(
            op.get("T_C", cases.DEFAULT_OPERATING.get(
                case.technology, {}).get("T_C",
                                         self.gas_tab.t_spin.value()))))
        self.gas_tab.lv_spin.setValue(float(op.get("L_over_V", self.gas_tab.lv_spin.value())))
        self.gas_tab.n_spin.setValue(int(op.get("N_stages", self.gas_tab.n_spin.value())))
        self.gas_tab.h_spin.setValue(float(op.get("height_m", self.gas_tab.h_spin.value())))
        if case.comparison:
            from .comparison_tab import ComparisonConfig
            self.comp_tab.config = ComparisonConfig.from_dict(dict(case.comparison))

    def project_new(self):
        if not self._maybe_save():
            return
        self.project.mark_clean("")
        self.app.metrics = None
        self.app.result = None
        self.results_tab.fill({})
        self.results_tab.show_message("Novo projeto: configure o caso e execute.")
        self.project_tab._refresh("", False)

    def project_open(self, path: str | None = None):
        if path is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Abrir projeto (case.json)", "", "Projeto BioGasPy (*.json)")
            if not path:
                return
        try:
            case = self.project.load(path)
        except Exception as exc:
            from .workers import friendly_error
            QtWidgets.QMessageBox.warning(self, "Abrir projeto",
                                          f"Não foi possível abrir o projeto:\n"
                                          f"{friendly_error(exc)}")
            return
        self._apply_case_to_gui(case)
        self.project_tab._refresh(self.project.path, False)

    def project_save(self) -> bool:
        if not self.project.has_file:
            return self.project_save_as()
        try:
            self.project.save(self._sync_case_from_gui())
        except Exception as exc:
            from .workers import friendly_error
            QtWidgets.QMessageBox.warning(self, "Salvar projeto", friendly_error(exc))
            return False
        self.app.log(f"Projeto salvo: {self.project.path}")
        return True

    def project_save_as(self) -> bool:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Salvar projeto como", "case.json", "Projeto BioGasPy (*.json)")
        if not path:
            return False
        try:
            self.project.save_as(self._sync_case_from_gui(), path)
        except Exception as exc:
            from .workers import friendly_error
            QtWidgets.QMessageBox.warning(self, "Salvar projeto", friendly_error(exc))
            return False
        self.app.log(f"Projeto salvo: {self.project.path}")
        return True

    def _rebuild_recents(self):
        self.recent_menu.clear()
        recs = self.project.recents()
        if not recs:
            act = self.recent_menu.addAction("(nenhum)")
            act.setEnabled(False)
            return
        for p in recs:
            act = self.recent_menu.addAction(p)
            act.triggered.connect(lambda _c=False, path=p: self.project_open(path))

    def _refresh_title(self):
        star = "*" if self.project.dirty else ""
        self.setWindowTitle(
            f"BioGasSim — {self.project.display_name()}{star} — "
            f"Upgrading de biogás CH₄–CO₂–H₂S")

    def _on_project_changed(self, path, dirty):
        self._rebuild_recents()
        self._refresh_title()

    # ================================================================== #
    # Navegação / utilidades
    # ================================================================== #
    def _go_to_results(self):
        self.tabs.setCurrentWidget(self.results_tab)

    def _go_to_studies(self):
        self.tabs.setCurrentWidget(self.study_tab)

    def _go_to_comparison(self):
        self.tabs.setCurrentWidget(self.comp_tab)

    def _go_to_reports(self):
        self.tabs.setCurrentWidget(self.reports_tab)

    def _on_run_h2s_study(self):
        self._go_to_studies()
        self.study_tab.run()

    def _clear_results(self):
        self.app.metrics = None
        self.app.result = None
        self.results_tab.fill({})
        self.results_tab.show_message("Resultados limpos.")
        self.app.set_state(STATE_READY)

    def _apply_theme(self, dark: bool):
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        app.setStyle("Fusion")
        if dark:
            pal = QtGui.QPalette()
            pal.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
            pal.setColor(QtGui.QPalette.WindowText, Qt.white)
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
            pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
            pal.setColor(QtGui.QPalette.Text, Qt.white)
            pal.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
            pal.setColor(QtGui.QPalette.ButtonText, Qt.white)
            pal.setColor(QtGui.QPalette.ToolTipBase, Qt.black)
            pal.setColor(QtGui.QPalette.ToolTipText, Qt.white)
            pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
            pal.setColor(QtGui.QPalette.HighlightedText, Qt.black)
            pal.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text,
                         QtGui.QColor(127, 127, 127))
            app.setPalette(pal)
        else:
            app.setPalette(app.style().standardPalette())
        QSettings().setValue(_SETTINGS_THEME, "dark" if dark else "light")
        self.theme_light.setChecked(not dark)
        self.theme_dark.setChecked(dark)

    def _show_about(self):
        """Caixa 'Sobre' com a autoria/afiliação do projeto (sem inventar dados)."""
        QtWidgets.QMessageBox.about(
            self, "Sobre o BioGasPy",
            "<p><b>BioGasPy — Thermodynamic Gas Upgrading Simulator</b></p>"
            "<p>Prof. Dr. Ivaldo Leão Ferreira<br>"
            "Federal University of Pará — UFPA<br>"
            "Faculty of Mechanical Engineering</p>"
            "<p>FEM-ITEC-UFPA 2026</p>")

    def open_html_help(self):
        self._open_html_help()

    def _open_html_help(self):
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[2]
        path = root / "docs" / "HELP.html"
        if not path.exists():
            try:
                from ..Reporting.help_html import build_help_html

                path = build_help_html(out=path)
            except ImportError as e:
                QtWidgets.QMessageBox.warning(
                    self, "Ajuda",
                    "O manual HTML precisa do pacote 'markdown' (pip install markdown).\n"
                    f"Detalhe: {e}")
                return
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Ajuda",
                    "Não foi possível gerar o manual HTML.\n"
                    "Rode: python -m biogassim.Reporting.help_html\n"
                    f"Detalhe: {e}")
                return
        QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    # ------------------------------------------------------------------ #
    # Fechamento: geometria + alterações não salvas
    # ------------------------------------------------------------------ #
    def closeEvent(self, event):
        QSettings().setValue(_SETTINGS_GEOMETRY, self.saveGeometry())
        if self._maybe_save():
            event.accept()
        else:
            event.ignore()


__all__ = ["MainWindow"]
