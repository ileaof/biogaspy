"""Aba "Comparação de Métodos" da GUI do BioGasSim.

HerdA as condições de alimentação da aba Simulação (fonte única -- sem cópia da
composição), seleciona tecnologias, roda todas sob o mesmo feed via
:class:`biogassim.comparison.ComparisonEngine` (mesmo backend da CLI) em uma
thread separada, e apresenta tabela de resultados, KPIs, gráfico de barras,
ranking uni/multi-critério e exportação.

Camadas claras: toda a ciência fica em ``biogassim.comparison``; esta classe é
apenas apresentação + fiação de sinais Qt.
"""
from __future__ import annotations

from .qt import Qt, QtCore, QtWidgets, Signal

# canvas matplotlib (opcional -- degrada com elegância)
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _Canvas
    from matplotlib.figure import Figure
    _HAS_PLOT = True
except Exception:  # pragma: no cover
    _HAS_PLOT = False

from ..comparison import (
    COLUMNS,
    METHODS,
    ComparisonConfig,
    ComparisonEngine,
    export_comparison,
    recommended_methods,
)

# Critérios para o gráfico "Comparar por" e para "Melhor método".
_COMPARE_METRICS = [
    ("purity_CH4", "Pureza CH₄ (%)"),
    ("recovery_CH4", "Recuperação CH₄ (%)"),
    ("CO2_removal", "Remoção CO₂ (%)"),
    ("H2S_removal", "Remoção H₂S (%)"),
    ("methane_loss", "Perda CH₄ (%)"),
    ("total_kW", "Energia total (kW)"),
    ("specific_kWh_per_Nm3", "Energia específica (kWh/Nm³)"),
    ("water_m3_per_h", "Consumo de água (m³/h)"),
    ("opex_usd_yr", "OPEX (USD/ano)"),
    ("specific_cost_usd_per_Nm3", "Custo específico (USD/Nm³)"),
    ("global_efficiency_pct", "Eficiência global (%)"),
]
_BEST_METRICS = _COMPARE_METRICS[:7] + _COMPARE_METRICS[8:]   # sem water p/ best? mantém tudo

_WEIGHT_ROWS = [
    ("purity_CH4", "Pureza CH₄"),
    ("recovery_CH4", "Recuperação CH₄"),
    ("total_kW", "Energia (kW)"),
    ("specific_cost_usd_per_Nm3", "Custo (USD/Nm³)"),
    ("water_m3_per_h", "Água (m³/h)"),
]


# --------------------------------------------------------------------------- #
# Worker thread -- mantém a GUI responsiva durante a comparação
# --------------------------------------------------------------------------- #
class ComparisonWorker(QtCore.QThread):
    progress = Signal(str, str, int, int)     # (method_key, status, index, total)
    finished_rows = Signal(list)

    def __init__(self, engine: ComparisonEngine):
        super().__init__()
        self.engine = engine
        self._stop = False

    def run(self):
        rows = self.engine.run(
            progress=lambda k, s, i, n: self.progress.emit(k, s, i, n),
            should_stop=lambda: self._stop)
        self.finished_rows.emit(rows)

    def stop(self):
        self._stop = True


# --------------------------------------------------------------------------- #
# Aba
# --------------------------------------------------------------------------- #
class ComparisonTab(QtWidgets.QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.config = ComparisonConfig()      # config persistente da comparação
        self.rows: list[dict] = []
        self.worker: ComparisonWorker | None = None
        self._stale = False
        self._param_widgets: dict[str, dict] = {}   # {method: {param_key: widget}}

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self._build_header())
        lay.addWidget(self._build_methods_group())
        lay.addWidget(self._build_params_area())
        lay.addWidget(self._build_progress())
        lay.addWidget(self._build_results_area(), 1)

        # herda feed da aba principal e escuta mudanças
        self._refresh_header()
        self.main.feed_changed.connect(self._on_feed_changed)

    # ------------------------------------------------------------------ #
    # Cabeçalho: condições herdadas (somente leitura)
    # ------------------------------------------------------------------ #
    def _build_header(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Condições de alimentação (herdadas da aba Simulação)")
        self.header_lay = QtWidgets.QGridLayout(box)
        self.header_labels = {}
        for col, key in enumerate(["CH4", "CO2", "H2S", "T", "P", "Flow", "Modelo"]):
            lab = QtWidgets.QLabel("-")
            lab.setStyleSheet("font-weight: 600;")
            self.header_lay.addWidget(QtWidgets.QLabel(key), 0, col)
            self.header_lay.addWidget(lab, 1, col)
            self.header_labels[key] = lab
        self.stale_lbl = QtWidgets.QLabel("")
        self.stale_lbl.setWordWrap(True)
        self.stale_lbl.setStyleSheet("color: #b00; font-weight: 600;")
        self.header_lay.addWidget(self.stale_lbl, 2, 0, 1, 7)
        return box

    def _refresh_header(self):
        fc = self.main.feed_conditions()
        comp = fc["comp"]
        self.header_labels["CH4"].setText(f"{comp.get('CH4', 0)*100:.2f} %")
        self.header_labels["CO2"].setText(f"{comp.get('CO2', 0)*100:.2f} %")
        self.header_labels["H2S"].setText(f"{comp.get('H2S', 0)*100:.3f} %")
        self.header_labels["T"].setText(f"{fc['T_K']-273.15:.1f} °C")
        self.header_labels["P"].setText(f"{fc['P_bar']} bar")
        self.header_labels["Flow"].setText(f"{fc['flow']:.1f} mol/s")
        self.header_labels["Modelo"].setText(fc["thermodynamic_model"])

    def _on_feed_changed(self):
        self._refresh_header()
        if self.rows:
            self._stale = True
            self.stale_lbl.setText(
                "⚠ Condições de alimentação alteradas — resultados desatualizados. "
                "Rode a comparação novamente.")
        else:
            self._stale = False
            self.stale_lbl.setText("")

    # ------------------------------------------------------------------ #
    # Seleção de métodos + modo + botões
    # ------------------------------------------------------------------ #
    def _build_methods_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Métodos")
        lay = QtWidgets.QGridLayout(box)

        self.method_checks: dict[str, QtWidgets.QCheckBox] = {}
        cols = 3
        for i, spec in enumerate(METHODS.values()):
            cb = QtWidgets.QCheckBox(spec.label)
            if spec.status == "experimental":
                cb.setText(f"{spec.label} (Experimental)")
            cb.setChecked(spec.key in self.config.selected)
            cb.stateChanged.connect(self._on_method_toggled)
            self.method_checks[spec.key] = cb
            lay.addWidget(cb, i // cols, i % cols)

        btns = QtWidgets.QHBoxLayout()
        self.btn_all = QtWidgets.QPushButton("Selecionar tudo")
        self.btn_all.clicked.connect(lambda: self._set_selection(list(METHODS)))
        self.btn_none = QtWidgets.QPushButton("Limpar")
        self.btn_none.clicked.connect(lambda: self._set_selection([]))
        self.btn_rec = QtWidgets.QPushButton("Recomendados")
        self.btn_rec.clicked.connect(lambda: self._set_selection(recommended_methods()))
        btns.addWidget(self.btn_all); btns.addWidget(self.btn_none); btns.addWidget(self.btn_rec)
        btns.addStretch(1)
        self.mode_standard = QtWidgets.QRadioButton("Padrão")
        self.mode_optimized = QtWidgets.QRadioButton("Otimizado")
        self.mode_standard.setChecked(True)
        self.mode_optimized.toggled.connect(self._on_mode_changed)
        btns.addWidget(QtWidgets.QLabel("Modo:"))
        btns.addWidget(self.mode_standard); btns.addWidget(self.mode_optimized)
        lay.addLayout(btns, len(METHODS) // cols + 1, 0, 1, cols)
        return box

    def _set_selection(self, keys):
        for k, cb in self.method_checks.items():
            cb.setChecked(k in keys)

    def _on_method_toggled(self):
        self.config.selected = [k for k, cb in self.method_checks.items() if cb.isChecked()]
        self._rebuild_params()

    def _on_mode_changed(self):
        self.config.mode = "optimized" if self.mode_optimized.isChecked() else "standard"

    # ------------------------------------------------------------------ #
    # Parâmetros específicos por método (expansível)
    # ------------------------------------------------------------------ #
    def _build_params_area(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Parâmetros por tecnologia")
        lay = QtWidgets.QVBoxLayout(box)
        self.params_scroll = QtWidgets.QScrollArea()
        self.params_scroll.setWidgetResizable(True)
        self.params_host = QtWidgets.QWidget()
        self.params_host_lay = QtWidgets.QVBoxLayout(self.params_host)
        self.params_scroll.setWidget(self.params_host)
        lay.addWidget(self.params_scroll)
        self._rebuild_params()
        return box

    def _rebuild_params(self):
        # limpa
        while self.params_host_lay.count():
            it = self.params_host_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._param_widgets = {}
        for key in self.config.selected:
            spec = METHODS.get(key)
            if not spec:
                continue
            gb = QtWidgets.QGroupBox(spec.label)
            form = QtWidgets.QFormLayout(gb)
            widgets = {}
            for p in spec.params:
                if p.choices is not None:
                    w = QtWidgets.QComboBox()
                    w.addItems(list(p.choices))
                    w.setCurrentText(str(self.config.params_for(key).get(p.key, p.default)))
                    w.currentTextChanged.connect(lambda v, k=key, pk=p.key: self._set_param(k, pk, v))
                else:
                    w = QtWidgets.QDoubleSpinBox()
                    w.setRange(p.lo, p.hi)
                    w.setDecimals(p.decimals)
                    w.setValue(float(self.config.params_for(key).get(p.key, p.default)))
                    if p.unit:
                        w.setSuffix(f" {p.unit}")
                    w.valueChanged.connect(lambda v, k=key, pk=p.key: self._set_param(k, pk, v))
                widgets[p.key] = w
                form.addRow(f"{p.label}", w)
            self.params_host_lay.addWidget(gb)
            self._param_widgets[key] = widgets
        self.params_host_lay.addStretch(1)

    def _set_param(self, method, param, value):
        self.config.params.setdefault(method, {})[param] = value

    # ------------------------------------------------------------------ #
    # Botões + progresso
    # ------------------------------------------------------------------ #
    def _build_progress(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(w)
        self.run_btn = QtWidgets.QPushButton("▶ Executar comparação")
        self.run_btn.setStyleSheet("font-weight: 600;")
        self.run_btn.clicked.connect(self._on_run)
        self.stop_btn = QtWidgets.QPushButton("■ Parar")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        self.export_btn = QtWidgets.QPushButton("💾 Exportar…")
        self.export_btn.clicked.connect(self._on_export)
        self.save_btn = QtWidgets.QPushButton("Salvar config")
        self.save_btn.clicked.connect(self._save_config)
        self.load_btn = QtWidgets.QPushButton("Carregar config")
        self.load_btn.clicked.connect(self._load_config)
        lay.addWidget(self.run_btn); lay.addWidget(self.stop_btn)
        lay.addWidget(self.export_btn); lay.addWidget(self.save_btn); lay.addWidget(self.load_btn)
        lay.addStretch(1)
        self.progress_lbl = QtWidgets.QLabel("Pronto.")
        self.progress_lbl.setStyleSheet("color: #444;")
        lay.addWidget(self.progress_lbl, 1)
        return w

    # ------------------------------------------------------------------ #
    # Área de resultados: tabela + gráfico + ranking
    # ------------------------------------------------------------------ #
    def _build_results_area(self) -> QtWidgets.QWidget:
        splitter = QtWidgets.QSplitter(Qt.Vertical)

        # tabela
        table_box = QtWidgets.QGroupBox("Tabela comparativa")
        tlay = QtWidgets.QVBoxLayout(table_box)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Colunas:"))
        self.col_btn = QtWidgets.QPushButton("▾")
        self.col_btn.setFixedWidth(28)
        self.col_btn.clicked.connect(self._show_col_menu)
        top.addWidget(self.col_btn); top.addStretch(1)
        tlay.addLayout(top)
        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        tlay.addWidget(self.table)
        splitter.addWidget(table_box)

        # gráfico + ranking
        bottom = QtWidgets.QSplitter(Qt.Horizontal)
        plot_box = QtWidgets.QGroupBox("Gráfico de comparação")
        play = QtWidgets.QVBoxLayout(plot_box)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Comparar por:"))
        self.metric_cmb = QtWidgets.QComboBox()
        for k, lbl in _COMPARE_METRICS:
            self.metric_cmb.addItem(lbl, k)
        self.metric_cmb.currentIndexChanged.connect(self._plot)
        row.addWidget(self.metric_cmb); row.addStretch(1)
        play.addLayout(row)
        if _HAS_PLOT:
            self.figure = Figure(figsize=(5, 3))
            self.canvas = _Canvas(self.figure)
            self.ax = self.figure.add_subplot(111)
            play.addWidget(self.canvas)
        else:  # pragma: no cover
            self.canvas = None
            play.addWidget(QtWidgets.QLabel("matplotlib indisponível."))
        bottom.addWidget(plot_box)

        rank_box = QtWidgets.QGroupBox("Ranking / decisão")
        rlay = QtWidgets.QVBoxLayout(rank_box)
        brow = QtWidgets.QHBoxLayout()
        brow.addWidget(QtWidgets.QLabel("Melhor por:"))
        self.best_cmb = QtWidgets.QComboBox()
        for k, lbl in _COMPARE_METRICS:
            self.best_cmb.addItem(lbl, k)
        self.best_cmb.currentIndexChanged.connect(self._update_best)
        brow.addWidget(self.best_cmb); brow.addStretch(1)
        rlay.addLayout(brow)
        self.best_lbl = QtWidgets.QLabel("—")
        self.best_lbl.setStyleSheet("font-weight: 600;")
        rlay.addWidget(self.best_lbl)
        rlay.addWidget(QtWidgets.QLabel("Decisão ponderada (pesos %):"))
        self.weight_spins = {}
        wrow = QtWidgets.QGridLayout()
        for i, (k, lbl) in enumerate(_WEIGHT_ROWS):
            sp = QtWidgets.QDoubleSpinBox()
            sp.setRange(0, 100); sp.setDecimals(0); sp.setSuffix(" %")
            sp.setValue(self.config.weights.get(k, 0) * 100)
            sp.valueChanged.connect(self._on_weight_changed)
            self.weight_spins[k] = sp
            wrow.addWidget(QtWidgets.QLabel(lbl), i, 0)
            wrow.addWidget(sp, i, 1)
        rlay.addLayout(wrow)
        self.calc_rank_btn = QtWidgets.QPushButton("Calcular ranking")
        self.calc_rank_btn.clicked.connect(self._calc_ranking)
        rlay.addWidget(self.calc_rank_btn)
        self.rank_table = QtWidgets.QTableWidget(0, 2)
        self.rank_table.setHorizontalHeaderLabels(["Método", "Score"])
        self.rank_table.horizontalHeader().setStretchLastSection(True)
        rlay.addWidget(self.rank_table, 1)
        bottom.addWidget(rank_box)
        bottom.setSizes([500, 400])
        splitter.addWidget(bottom)
        splitter.setSizes([300, 220])
        return splitter

    # ------------------------------------------------------------------ #
    # Execução
    # ------------------------------------------------------------------ #
    def _build_engine(self) -> ComparisonEngine:
        fc = self.main.feed_conditions()
        feed = {k: v for k, v in fc["comp"].items() if v > 0}
        return ComparisonEngine(feed, flow=fc["flow"], config=self.config,
                                 T_K=fc["T_K"], P_feed_bar=1.01325)

    def _on_run(self):
        if not self.config.selected:
            self.progress_lbl.setText("Selecione ao menos um método.")
            return
        self.run_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.progress_lbl.setText("Executando comparação…")
        self._stale = False
        self.stale_lbl.setText("")
        self.engine = self._build_engine()
        self.worker = ComparisonWorker(self.engine)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_rows.connect(self._on_finished)
        self.worker.start()

    def _on_stop(self):
        if self.worker:
            self.worker.stop()
            self.progress_lbl.setText("Parando…")

    def _on_progress(self, key, status, i, n):
        self.progress_lbl.setText(f"[{i+1}/{n}] {METHODS[key].label}: {status}")

    def _on_finished(self, rows):
        self.rows = rows
        self.run_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        ok = sum(1 for r in rows if r.get("converged"))
        fail = len(rows) - ok
        self.progress_lbl.setText(
            f"Concluído: {ok} convergiram, {fail} falharam.")
        self._fill_table(rows)
        self._plot()
        self._update_best()
        self._calc_ranking()

    # ------------------------------------------------------------------ #
    # Tabela
    # ------------------------------------------------------------------ #
    def _fill_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, (key, _label, _unit, _fmt) in enumerate(COLUMNS):
                v = r.get(key)
                if v is None:
                    item = QtWidgets.QTableWidgetItem("")
                elif isinstance(v, bool):
                    item = QtWidgets.QTableWidgetItem("Sim" if v else "Não")
                elif isinstance(v, (int, float)):
                    item = QtWidgets.QTableWidgetItem()
                    item.setData(Qt.DisplayRole, float(v))
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item = QtWidgets.QTableWidgetItem(str(v))
                if key == "converged" and not r.get("converged"):
                    item.setForeground(Qt.red)
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def _show_col_menu(self):
        menu = QtWidgets.QMenu(self)
        for col, (_key, label, *_rest) in enumerate(COLUMNS):
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(not self.table.isColumnHidden(col))
            act.toggled.connect(lambda checked, c=col: self.table.setColumnHidden(c, not checked))
        menu.exec(self.col_btn.mapToGlobal(self.col_btn.rect().bottomLeft()))

    # ------------------------------------------------------------------ #
    # Gráfico
    # ------------------------------------------------------------------ #
    def _plot(self):
        if not _HAS_PLOT or self.canvas is None or not self.rows:
            return
        key = self.metric_cmb.currentData()
        names = [r.get("method_label", "?") for r in self.rows]
        vals = [r.get(key) for r in self.rows]
        self.ax.clear()
        good = [(n, v) for n, v in zip(names, vals) if isinstance(v, (int, float))]
        if good:
            gn, gv = zip(*good)
            self.ax.bar(range(len(gn)), gv, color="#3b6fb5")
            self.ax.set_xticks(range(len(gn)))
            self.ax.set_xticklabels(gn, rotation=20, ha="right", fontsize=8)
            self.ax.set_ylabel(self.metric_cmb.currentText())
            self.ax.grid(True, axis="y", alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    # Ranking
    # ------------------------------------------------------------------ #
    def _update_best(self):
        if not self.rows:
            self.best_lbl.setText("—")
            return
        key = self.best_cmb.currentData()
        b = self.engine.best_by(self.rows, key) if hasattr(self, "engine") \
            else ComparisonEngine.__new__(ComparisonEngine).best_by(self.rows, key)
        # fallback robusto: calcula best_by sem engine
        if not b:
            from ..comparison import _BENEFIT
            ok = [r for r in self.rows if r.get("converged") and r.get(key) is not None]
            if ok:
                b = max(ok, key=lambda r: r[key]) if _BENEFIT.get(key, False) \
                    else min(ok, key=lambda r: r[key])
        self.best_lbl.setText(b["method_label"] if b else "—")

    def _on_weight_changed(self):
        total = sum(sp.value() for sp in self.weight_spins.values())
        for k, sp in self.weight_spins.items():
            self.config.weights[k] = (sp.value() / 100.0) if total > 0 else 0.0

    def _calc_ranking(self):
        if not self.rows:
            return
        eng = getattr(self, "engine", None) or self._build_engine()
        ranked = eng.weighted_score(self.rows, self.config.weights)
        self.rank_table.setRowCount(0)
        for r in ranked:
            row = self.rank_table.rowCount()
            self.rank_table.insertRow(row)
            self.rank_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(r.get("method_label"))))
            sc = r.get("score")
            it = QtWidgets.QTableWidgetItem()
            it.setData(Qt.DisplayRole, float(sc) if sc is not None else "")
            self.rank_table.setItem(row, 1, it)

    # ------------------------------------------------------------------ #
    # Exportação
    # ------------------------------------------------------------------ #
    def _on_export(self):
        if not self.rows:
            self.progress_lbl.setText("Nada para exportar. Rode a comparação.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar comparação", "comparison.xlsx",
            "Relatório (*.xlsx *.csv *.json *.html *.pdf)")
        if not path:
            return
        eng = getattr(self, "engine", None) or self._build_engine()
        export_comparison(eng.report(self.rows), path)
        self.progress_lbl.setText(f"Exportado: {path}")

    # ------------------------------------------------------------------ #
    # Persistência da configuração
    # ------------------------------------------------------------------ #
    def _save_config(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Salvar configuração de comparação", "comparison_config.json",
            "JSON (*.json)")
        if not path:
            return
        import json
        fc = self.main.feed_conditions()
        cfg = self.config.to_dict()
        cfg["feed"] = {k: v for k, v in fc["comp"].items() if v > 0}
        cfg["flow_mols"] = fc["flow"]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        self.progress_lbl.setText(f"Configuração salva: {path}")

    def _load_config(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Carregar configuração de comparação", "", "JSON (*.json)")
        if not path:
            return
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.config = ComparisonConfig.from_dict(data)
        # reflete na UI
        self._set_selection(self.config.selected)
        self.mode_optimized.setChecked(self.config.mode == "optimized")
        for k, sp in self.weight_spins.items():
            sp.setValue(self.config.weights.get(k, 0) * 100)
        self._rebuild_params()
        self.progress_lbl.setText(f"Configuração carregada: {path}")


__all__ = ["ComparisonTab", "ComparisonWorker"]
