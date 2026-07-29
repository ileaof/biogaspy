"""Janela principal da GUI do BioGasSim (Milestone 1 -- CH4-CO2).

Painéis:
  * Composição da alimentação -- frações CH4/CO2 editáveis (spin + slider +
    presets), normalização automática, fração complementar em tempo real e
    leitura contínua das propriedades da mistura (MM, Z, densidade, LHV, HHV,
    Índice de Wobbe, densidade relativa).
  * Condições operacionais -- tecnologia, pressão, L/V, estágios, altura.
  * Controles do solver + monitor de convergência.
  * Dashboard de resultados (tabela de métricas).
  * Gráfico interativo (varredura de composição: recuperação/pureza vs CH4%).

Toda a lógica de processo reusa ``biogassim.cases`` e
``biogassim.Properties.mixture_properties``; a GUI é só a camada de interação.
"""
from __future__ import annotations

from .. import cases
from ..Properties import mixture_properties
from .qt import Qt, QtWidgets

# Canvas matplotlib (opcional -- degrada com elegância se indisponível)
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _Canvas
    from matplotlib.figure import Figure
    _HAS_PLOT = True
except Exception:  # pragma: no cover - depende do backend
    _HAS_PLOT = False

PRESETS = {
    "Biogás (47 / 53)": 0.47,
    "Digestor anaeróbio (60 / 40)": 0.60,
    "Aterro / landfill (50 / 50)": 0.50,
    "Metano puro (100 / 0)": 1.00,
    "Personalizado": None,
}

_READOUTS = [
    ("molar_mass_gmol", "Massa molar", "g/mol", "{:.3f}"),
    ("Z", "Fator Z", "", "{:.4f}"),
    ("density", "Densidade (T,P)", "kg/m³", "{:.3f}"),
    ("density_normal", "Densidade normal", "kg/Nm³", "{:.4f}"),
    ("LHV_MJ_per_Nm3", "PCI (LHV)", "MJ/Nm³", "{:.2f}"),
    ("HHV_MJ_per_Nm3", "PCS (HHV)", "MJ/Nm³", "{:.2f}"),
    ("wobbe_index_MJ_per_Nm3", "Índice de Wobbe", "MJ/Nm³", "{:.2f}"),
    ("specific_gravity", "Densidade relativa", "(ar=1)", "{:.4f}"),
]

_RESULT_ROWS = [
    ("purity_CH4", "Pureza CH₄", "%"),
    ("recovery_CH4", "Recuperação CH₄", "%"),
    ("CO2_removal", "Remoção CO₂", "%"),
    ("methane_loss", "Perda de metano", "%"),
    ("solvent_flow_mols", "Vazão de solvente", "mol/s"),
    ("water_m3_per_h", "Consumo de água", "m³/h"),
    ("total_kW", "Energia total", "kW"),
    ("specific_kWh_per_Nm3", "Consumo específico", "kWh/Nm³"),
    ("diameter_m", "Diâmetro da coluna", "m"),
    ("height_m", "Altura da coluna", "m"),
    ("pressure_drop_Pa", "Perda de carga", "Pa/m·total"),
    ("flooding_pct", "Margem de inundação", "% flood"),
    ("specific_cost_usd_per_Nm3", "Custo específico", "USD/Nm³"),
]


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BioGasSim -- Upgrading de biogás CH₄–CO₂")
        self._updating = False
        self._ch4 = 0.47

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QHBoxLayout(central)

        left = QtWidgets.QVBoxLayout()
        left.addWidget(self._build_operating_group())   # antes: define P p/ leituras
        left.addWidget(self._build_composition_group())
        left.addWidget(self._build_solver_group())
        left.addStretch(1)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self._build_results_group(), 1)
        right.addWidget(self._build_plot_group(), 1)

        root.addLayout(left, 0)
        root.addLayout(right, 1)

        self._set_composition(self._ch4)                # popula leituras iniciais

    # ------------------------------------------------------------------ #
    # Painéis
    # ------------------------------------------------------------------ #
    def _build_composition_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Composição da alimentação (CH₄ / CO₂)")
        lay = QtWidgets.QGridLayout(box)

        self.preset = QtWidgets.QComboBox()
        self.preset.addItems(list(PRESETS))
        self.preset.currentTextChanged.connect(self._on_preset)
        lay.addWidget(QtWidgets.QLabel("Preset"), 0, 0)
        lay.addWidget(self.preset, 0, 1, 1, 2)

        self.ch4_spin = self._pct_spin()
        self.co2_spin = self._pct_spin()
        self.ch4_slider = self._pct_slider()
        self.co2_slider = self._pct_slider()
        self.ch4_spin.valueChanged.connect(lambda v: self._set_composition(v / 100.0))
        self.co2_spin.valueChanged.connect(lambda v: self._set_composition(1.0 - v / 100.0))
        self.ch4_slider.valueChanged.connect(lambda v: self._set_composition(v / 1000.0))
        self.co2_slider.valueChanged.connect(lambda v: self._set_composition(1.0 - v / 1000.0))

        lay.addWidget(QtWidgets.QLabel("CH₄ (%)"), 1, 0)
        lay.addWidget(self.ch4_spin, 1, 1)
        lay.addWidget(self.ch4_slider, 1, 2)
        lay.addWidget(QtWidgets.QLabel("CO₂ (%)"), 2, 0)
        lay.addWidget(self.co2_spin, 2, 1)
        lay.addWidget(self.co2_slider, 2, 2)

        # leituras de propriedades
        self._readout_labels = {}
        props = QtWidgets.QGroupBox("Propriedades da mistura")
        form = QtWidgets.QFormLayout(props)
        for key, label, unit, _fmt in _READOUTS:
            val = QtWidgets.QLabel("-")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._readout_labels[key] = val
            form.addRow(f"{label} [{unit}]" if unit else label, val)
        lay.addWidget(props, 3, 0, 1, 3)
        return box

    def _build_operating_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Condições operacionais")
        form = QtWidgets.QFormLayout(box)
        self.tech = QtWidgets.QComboBox()
        self.tech.addItems(list(cases.TECHNOLOGIES))
        self.tech.currentTextChanged.connect(self._on_tech_changed)
        self.flow_spin = self._num_spin(1.0, 1e5, 100.0, 1)
        self.p_spin = self._num_spin(0.5, 120.0, 20.0, 1)
        self.p_spin.valueChanged.connect(lambda _v: self._refresh_props())
        self.lv_spin = self._num_spin(1.0, 1000.0, 100.0, 1)
        self.n_spin = self._num_spin(1, 60, 12, 0)
        self.h_spin = self._num_spin(1.0, 60.0, 15.0, 1)
        form.addRow("Tecnologia", self.tech)
        form.addRow("Vazão do biogás [mol/s]", self.flow_spin)
        form.addRow("Pressão [bar]", self.p_spin)
        form.addRow("Razão L/V", self.lv_spin)
        form.addRow("Nº de estágios", self.n_spin)
        form.addRow("Altura [m]", self.h_spin)
        return box

    def _build_solver_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Solver")
        lay = QtWidgets.QVBoxLayout(box)
        btns = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Executar caso")
        self.run_btn.clicked.connect(self._on_run)
        self.sweep_btn = QtWidgets.QPushButton("Varrer composição")
        self.sweep_btn.clicked.connect(self._on_sweep)
        btns.addWidget(self.run_btn)
        btns.addWidget(self.sweep_btn)
        lay.addLayout(btns)
        self.status = QtWidgets.QLabel("Pronto.")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        return box

    def _build_results_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Resultados")
        lay = QtWidgets.QVBoxLayout(box)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Métrica", "Valor", "Unidade"])
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table)
        return box

    def _build_plot_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Mapa de desempenho (varredura de composição)")
        lay = QtWidgets.QVBoxLayout(box)
        if _HAS_PLOT:
            self.figure = Figure(figsize=(4, 3))
            self.canvas = _Canvas(self.figure)
            self.ax = self.figure.add_subplot(111)
            lay.addWidget(self.canvas)
        else:  # pragma: no cover
            self.canvas = None
            lay.addWidget(QtWidgets.QLabel("matplotlib indisponível: gráfico desativado."))
        return box

    # ------------------------------------------------------------------ #
    # helpers de widgets
    # ------------------------------------------------------------------ #
    def _pct_spin(self) -> QtWidgets.QDoubleSpinBox:
        s = QtWidgets.QDoubleSpinBox()
        s.setRange(0.0, 100.0)
        s.setDecimals(1)
        s.setSingleStep(1.0)
        s.setSuffix(" %")
        return s

    def _pct_slider(self) -> QtWidgets.QSlider:
        sl = QtWidgets.QSlider(Qt.Horizontal)
        sl.setRange(0, 1000)
        return sl

    def _num_spin(self, lo, hi, val, decimals) -> QtWidgets.QDoubleSpinBox:
        s = QtWidgets.QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(decimals)
        s.setValue(val)
        return s

    # ------------------------------------------------------------------ #
    # composição: normalização + fração complementar em tempo real
    # ------------------------------------------------------------------ #
    def _set_composition(self, ch4_frac: float):
        if self._updating:
            return
        ch4 = min(max(float(ch4_frac), 0.0), 1.0)
        self._ch4 = ch4
        co2 = 1.0 - ch4
        self._updating = True
        try:
            self.ch4_spin.setValue(ch4 * 100.0)
            self.co2_spin.setValue(co2 * 100.0)
            self.ch4_slider.setValue(int(round(ch4 * 1000)))
            self.co2_slider.setValue(int(round(co2 * 1000)))
        finally:
            self._updating = False
        self._refresh_props()

    def _refresh_props(self):
        p_bar = self.p_spin.value() if hasattr(self, "p_spin") else 1.01325
        props = mixture_properties(ch4=self._ch4, T=298.15, P=p_bar * 1e5)
        d = props.as_dict()
        for key, _label, _unit, fmt in _READOUTS:
            self._readout_labels[key].setText(fmt.format(d[key]))

    def _on_preset(self, name: str):
        frac = PRESETS.get(name)
        if frac is not None:
            self._set_composition(frac)

    def _on_tech_changed(self, tech: str):
        # aplica condições operacionais padrão da tecnologia
        op = cases.DEFAULT_OPERATING.get(tech.lower())
        if not op:
            return
        self._updating = True
        try:
            self.p_spin.setValue(op["P_bar"])
            self.lv_spin.setValue(op["L_over_V"])
            self.n_spin.setValue(op["N_stages"])
            self.h_spin.setValue(op["height_m"])
        finally:
            self._updating = False
        self._refresh_props()

    # ------------------------------------------------------------------ #
    # solver
    # ------------------------------------------------------------------ #
    def _current_case(self) -> cases.Case:
        return cases.Case(
            name="gui",
            technology=self.tech.currentText(),
            feed={"CH4": self._ch4, "CO2": 1.0 - self._ch4,
                  "flow_mols": self.flow_spin.value()},
            operating={"P_bar": self.p_spin.value(), "L_over_V": self.lv_spin.value(),
                       "N_stages": int(self.n_spin.value()), "height_m": self.h_spin.value()},
        )

    def _on_run(self):
        self.status.setText("Executando...")
        try:
            metrics = cases.run_case(self._current_case())["metrics"]
        except Exception as exc:  # pragma: no cover - erro numérico
            self.status.setText(f"Erro: {exc}")
            return
        self._fill_table(metrics)
        conv = metrics.get("converged")
        self.status.setText(
            f"Convergiu: {conv} | iterações: {metrics.get('iterations', '-')} | "
            f"pureza {metrics.get('purity_CH4')}% | recuperação {metrics.get('recovery_CH4')}%"
        )
        return metrics

    def _on_sweep(self):
        self.status.setText("Varrendo composição...")
        tech = self.tech.currentText()
        op = self._current_case().operating
        try:
            rows = cases.sweep_composition(tech, ch4_values=cases.frange(0.20, 0.95, 0.05),
                                           operating=op, flow=self.flow_spin.value())
        except Exception as exc:  # pragma: no cover
            self.status.setText(f"Erro na varredura: {exc}")
            return []
        self._plot_sweep(rows)
        ok = sum(1 for r in rows if r.get("converged"))
        self.status.setText(f"Varredura concluída: {ok}/{len(rows)} pontos convergiram.")
        return rows

    def _fill_table(self, metrics: dict):
        self.table.setRowCount(0)
        for key, label, unit in _RESULT_ROWS:
            if key not in metrics or metrics[key] is None:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(label))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(metrics[key])))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(unit))

    def _plot_sweep(self, rows):
        if not _HAS_PLOT or self.canvas is None:
            return
        xs = [r["feed_CH4_pct"] for r in rows if r.get("converged")]
        pur = [r["purity_CH4"] for r in rows if r.get("converged")]
        rec = [r["recovery_CH4"] for r in rows if r.get("converged")]
        self.ax.clear()
        self.ax.plot(xs, pur, "-o", label="Pureza CH₄ (%)", markersize=3)
        self.ax.plot(xs, rec, "-s", label="Recuperação CH₄ (%)", markersize=3)
        self.ax.set_xlabel("CH₄ na alimentação (%)")
        self.ax.set_ylabel("%")
        self.ax.set_title("Desempenho vs composição")
        self.ax.legend(fontsize=8)
        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw_idle()


__all__ = ["MainWindow", "PRESETS"]
