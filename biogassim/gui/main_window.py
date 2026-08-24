"""Janela principal da GUI do BioGasSim (composição CH4-CO2-H2S).

Painéis:
  * Composição da alimentação -- frações CH4/CO2/H2S editáveis (spin + slider +
    presets), normalização automática (editar um componente redistribui o
    restante entre os outros dois preservando a razão atual), validação e
    leitura contínua das propriedades da mistura (MM, Z, densidade, LHV, HHV,
    Índice de Wobbe, densidade relativa).
  * Aviso de segurança -- H2S é tóxico/corosivo; banner exibido sempre que H2S
    estiver presente na alimentação.
  * Condições operacionais -- tecnologia, pressão, L/V, estágios, altura.
  * Controles do solver + monitor de convergência.
  * Dashboard de resultados (tabela de métricas, incluindo remoção de H2S e
    concentração de H2S no gás tratado).
  * Gráfico interativo (varredura de H2S: remoção/recuperação vs H2S%).

Toda a lógica de processo reusa ``biogassim.cases`` e
``biogassim.Properties.mixture_properties_general``; a GUI é só a camada de
interação.
"""
from __future__ import annotations

from .. import cases, safety
from ..Properties import mixture_properties_general
from .qt import Qt, QtWidgets, Signal

# Canvas matplotlib (opcional -- degrada com elegância se indisponível)
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _Canvas
    from matplotlib.figure import Figure
    _HAS_PLOT = True
except Exception:  # pragma: no cover - depende do backend
    _HAS_PLOT = False

# Presets como (rótulo, {CH4, CO2, H2S}) -- frações molares.
PRESETS = {
    "Biogás (47 / 53 / 0)":            {"CH4": 0.47, "CO2": 0.53, "H2S": 0.00},
    "Biogás c/ 1% H2S (46 / 53 / 1)":   {"CH4": 0.46, "CO2": 0.53, "H2S": 0.01},
    "Biogás c/ 2% H2S (45 / 53 / 2)":   {"CH4": 0.45, "CO2": 0.53, "H2S": 0.02},
    "Biogás c/ 5% H2S (40 / 55 / 5)":   {"CH4": 0.40, "CO2": 0.55, "H2S": 0.05},
    "Digestor anaeróbio (60 / 40 / 0)": {"CH4": 0.60, "CO2": 0.40, "H2S": 0.00},
    "Metano puro (100 / 0 / 0)":         {"CH4": 1.00, "CO2": 0.00, "H2S": 0.00},
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

# Métricas mostradas na tabela de resultados (rótulo, chave, unidade).
_RESULT_ROWS = [
    ("Pureza CH₄", "purity_CH4", "%"),
    ("Recuperação CH₄", "recovery_CH4", "%"),
    ("Remoção CO₂", "CO2_removal", "%"),
    ("Remoção H₂S", "H2S_removal", "%"),
    ("H₂S no gás tratado", "treated_H2S_ppm", "ppm"),
    ("Perda de metano", "methane_loss", "%"),
    ("Vazão de solvente", "solvent_flow_mols", "mol/s"),
    ("Consumo de água", "water_m3_per_h", "m³/h"),
    ("Energia total", "total_kW", "kW"),
    ("Consumo específico", "specific_kWh_per_Nm3", "kWh/Nm³"),
    ("Diâmetro da coluna", "diameter_m", "m"),
    ("Altura da coluna", "height_m", "m"),
    ("Margem de inundação", "flooding_pct", "% flood"),
    ("Wobbe (gás tratado)", "treated_wobbe_MJ_per_Nm3", "MJ/Nm³"),
    ("Custo específico", "specific_cost_usd_per_Nm3", "USD/Nm³"),
]

_COMPS = ("CH4", "CO2", "H2S")
_COMP_LABEL = {"CH4": "CH₄", "CO2": "CO₂", "H2S": "H₂S"}


class MainWindow(QtWidgets.QMainWindow):
    #: emitido quando a composição/condições da alimentação mudam (a aba de
    #: comparação escuta para herdar o feed e marcar resultados como obsoletos).
    feed_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BioGasSim -- Upgrading de biogás CH₄–CO₂–H₂S")
        self._updating = False
        self._comp = {"CH4": 0.47, "CO2": 0.53, "H2S": 0.0}

        # ---- aba 1: Simulação (paineis existentes, inalterados) ----
        sim_widget = QtWidgets.QWidget()
        root = QtWidgets.QHBoxLayout(sim_widget)

        left = QtWidgets.QVBoxLayout()
        left.addWidget(self._build_operating_group())   # antes: define P p/ leituras
        left.addWidget(self._build_composition_group())
        left.addWidget(self._build_safety_group())
        left.addWidget(self._build_solver_group())
        left.addStretch(1)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self._build_results_group(), 1)
        right.addWidget(self._build_plot_group(), 1)

        root.addLayout(left, 0)
        root.addLayout(right, 1)

        # barra de rolagem própria da aba Simulação -- conteúdo acessível com a
        # janela reduzida (consistente com as sub-abas de comparação). Largura
        # acompanha a janela (sem rolagem horizontal); rolagem vertical só entra
        # quando o conteúdo não cabe.
        sim_scroll = QtWidgets.QScrollArea()
        sim_scroll.setWidgetResizable(True)
        sim_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        sim_scroll.setWidget(sim_widget)

        # ---- container de abas: Simulação + Comparação de Métodos ----
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(sim_scroll, "Simulação")
        from .comparison_tab import ComparisonTab
        self.comp_tab = ComparisonTab(self)   # herda o feed desta janela
        self.tabs.addTab(self.comp_tab, "Comparação de Métodos")
        self.setCentralWidget(self.tabs)

        self._set_composition(dict(self._comp))         # popula leituras iniciais

    # ------------------------------------------------------------------ #
    # Painéis
    # ------------------------------------------------------------------ #
    def _build_composition_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Composição da alimentação (CH₄ / CO₂ / H₂S)")
        lay = QtWidgets.QGridLayout(box)

        self.preset = QtWidgets.QComboBox()
        self.preset.addItems(list(PRESETS))
        self.preset.currentTextChanged.connect(self._on_preset)
        lay.addWidget(QtWidgets.QLabel("Preset"), 0, 0)
        lay.addWidget(self.preset, 0, 1, 1, 2)

        self.spins: dict[str, QtWidgets.QDoubleSpinBox] = {}
        self.sliders: dict[str, QtWidgets.QSlider] = {}
        row = 1
        for s in _COMPS:
            sp = self._pct_spin()
            sl = self._pct_slider()
            # captura s via default arg para evitar late-binding
            sp.valueChanged.connect(lambda v, name=s: self._set_component(name, v / 100.0))
            sl.valueChanged.connect(lambda v, name=s: self._set_component(name, v / 1000.0))
            self.spins[s] = sp
            self.sliders[s] = sl
            lay.addWidget(QtWidgets.QLabel(f"{_COMP_LABEL[s]} (%)"), row, 0)
            lay.addWidget(sp, row, 1)
            lay.addWidget(sl, row, 2)
            row += 1

        lay.addWidget(QtWidgets.QLabel("Total"), row, 0)
        self.total_lbl = QtWidgets.QLabel("100.0 %")
        self.total_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.total_lbl, row, 1, 1, 2)

        # leituras de propriedades
        self._readout_labels = {}
        props = QtWidgets.QGroupBox("Propriedades da mistura")
        form = QtWidgets.QFormLayout(props)
        for key, label, unit, _fmt in _READOUTS:
            val = QtWidgets.QLabel("-")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._readout_labels[key] = val
            form.addRow(f"{label} [{unit}]" if unit else label, val)
        lay.addWidget(props, row + 1, 0, 1, 3)
        return box

    def _build_safety_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Segurança -- H₂S")
        lay = QtWidgets.QVBoxLayout(box)
        self.safety_lbl = QtWidgets.QLabel("Sem H₂S na alimentação.")
        self.safety_lbl.setWordWrap(True)
        self.safety_lbl.setStyleSheet("color: #444;")
        lay.addWidget(self.safety_lbl)
        lay.addWidget(QtWidgets.QLabel("Limite máx. H₂S no gás tratado (ppm):"))
        self.maxh2s_spin = self._num_spin(0.0, 1000.0, safety.max_h2s_treated_ppm(), 1)
        self.maxh2s_spin.valueChanged.connect(self._refresh_safety)
        lay.addWidget(self.maxh2s_spin)
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
        # qualquer mudança operacional notifica a aba de comparação (feed alterado)
        for sp in (self.flow_spin, self.p_spin, self.lv_spin, self.n_spin, self.h_spin):
            sp.valueChanged.connect(lambda _v: self.feed_changed.emit())
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
        self.sweep_btn = QtWidgets.QPushButton("Varrer H₂S")
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
        box = QtWidgets.QGroupBox("Mapa de desempenho (varredura de H₂S)")
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
        s.setDecimals(2)
        s.setSingleStep(0.5)
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
    # composição: normalização + redistribuição em tempo real
    # ------------------------------------------------------------------ #
    def _set_component(self, name: str, frac: float):
        """Editar ``name`` para ``frac`` e redistribuir o restante entre os
        outros dois componentes preservando a razão atual entre eles."""
        if self._updating:
            return
        frac = min(max(float(frac), 0.0), 1.0)
        others = [s for s in _COMPS if s != name]
        s_other = sum(self._comp[o] for o in others)
        rem = 1.0 - frac
        if s_other > 1e-9:
            for o in others:
                self._comp[o] = rem * (self._comp[o] / s_other)
        else:
            # ambos os outros são ~0: atribui o restante ao CO2 (complemento padrão)
            for o in others:
                self._comp[o] = rem if o == "CO2" else 0.0
        self._comp[name] = frac
        # clamp numérico e renormalização final (defesa contra drift)
        tot = sum(self._comp.values())
        if tot > 0:
            for s in _COMPS:
                self._comp[s] = self._comp[s] / tot
        self._set_composition(dict(self._comp))

    def _set_composition(self, comp: dict):
        """Sincroniza spins/sliders/total a partir do dict de frações."""
        if self._updating:
            return
        self._updating = True
        try:
            for s in _COMPS:
                v = float(comp.get(s, 0.0))
                self._comp[s] = v
                self.spins[s].setValue(v * 100.0)
                self.sliders[s].setValue(int(round(v * 1000)))
            tot = sum(self._comp.values())
            self.total_lbl.setText(f"{tot * 100:5.1f} %")
        finally:
            self._updating = False
        self._refresh_props()
        self._refresh_safety()
        self.feed_changed.emit()

    def _refresh_props(self):
        p_bar = self.p_spin.value() if hasattr(self, "p_spin") else 1.01325
        comp = {s: self._comp[s] for s in _COMPS if self._comp[s] > 0}
        if not comp:
            comp = {"CH4": 1.0}
        props = mixture_properties_general(comp, T=298.15, P=p_bar * 1e5)
        d = props.as_dict()
        for key, _label, _unit, fmt in _READOUTS:
            self._readout_labels[key].setText(fmt.format(d[key]))

    def _refresh_safety(self):
        if not hasattr(self, "safety_lbl"):
            return
        if hasattr(self, "maxh2s_spin"):
            safety.set_max_h2s_treated_ppm(self.maxh2s_spin.value())
        feed_h2s = self._comp["H2S"]
        if safety.h2s_present(feed_h2s):
            warns = safety.h2s_warnings(feed_h2s, 0.0)
            head = warns[0] if warns else "H₂S presente na alimentação."
            self.safety_lbl.setText(head + "\n\n⚠ Gas tóxico e corrosivo -- "
                                     "requer remocao antes do uso.")
            self.safety_lbl.setStyleSheet("color: #b00; font-weight: 600;")
        else:
            self.safety_lbl.setText("Sem H₂S na alimentação.")
            self.safety_lbl.setStyleSheet("color: #444;")

    def _on_preset(self, name: str):
        frac = PRESETS.get(name)
        if frac is not None:
            self._set_composition(dict(frac))

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
        self.feed_changed.emit()

    # ------------------------------------------------------------------ #
    # estado de alimentação compartilhado (fonte única p/ aba de comparação)
    # ------------------------------------------------------------------ #
    def feed_conditions(self) -> dict:
        """Estado de alimentação herdado pela aba de comparação (fonte única).

        Composição (CH4/CO2/H2S), vazão, pressão e temperatura do feed -- os
        mesmos valores da aba Simulação, sem cópia independente.
        """
        return {
            "comp": dict(self._comp),
            "flow": self.flow_spin.value(),
            "P_bar": self.p_spin.value(),
            "T_K": 298.15,                      # feed a 25 °C (modelo isotérmico)
            "tech": self.tech.currentText(),
            "thermodynamic_model": "Peng-Robinson",
        }

    def _current_case(self) -> cases.Case:
        feed = {s: self._comp[s] for s in _COMPS if self._comp[s] > 1e-9}
        if not feed:
            feed = {"CH4": 1.0}
        feed["flow_mols"] = self.flow_spin.value()
        return cases.Case(
            name="gui",
            technology=self.tech.currentText(),
            feed=feed,
            operating={"P_bar": self.p_spin.value(), "L_over_V": self.lv_spin.value(),
                       "N_stages": int(self.n_spin.value()), "height_m": self.h_spin.value()},
        )

    def _on_run(self):
        self.status.setText("Executando...")
        try:
            out = cases.run_case(self._current_case())
            metrics = out["metrics"]
        except Exception as exc:  # pragma: no cover - erro numérico
            self.status.setText(f"Erro: {exc}")
            return
        self._fill_table(metrics)
        self._refresh_safety_with_result(metrics)
        conv = metrics.get("converged")
        self.status.setText(
            f"Convergiu: {conv} | iterações: {metrics.get('iterations', '-')} | "
            f"pureza {metrics.get('purity_CH4')}% | recuperação {metrics.get('recovery_CH4')}%"
        )
        return metrics

    def _refresh_safety_with_result(self, metrics: dict):
        feed_h2s = self._comp["H2S"]
        if not safety.h2s_present(feed_h2s):
            return
        t_ppm = metrics.get("treated_H2S_ppm", 0.0) or 0.0
        warns = safety.h2s_warnings(feed_h2s, t_ppm,
                                    metrics.get("liquid_H2S_loading_mol_per_mol"))
        suit = safety.engine_suitable(t_ppm)
        text = "\n".join(warns) + f"\nAdequado p/ motor: {'SIM' if suit else 'NÃO'}"
        self.safety_lbl.setText(text)
        self.safety_lbl.setStyleSheet("color: #b00; font-weight: 600;" if not suit
                                       else "color: #060; font-weight: 600;")

    def _on_sweep(self):
        self.status.setText("Varrendo H2S...")
        op = self._current_case().operating
        try:
            rows = cases.sweep_h2s("water", cases.frange(0.0, 0.05, 0.005),
                                   ch4_co2_ratio=(self._comp["CH4"]
                                                  / max(self._comp["CH4"] + self._comp["CO2"], 1e-9)),
                                   operating=op, flow=self.flow_spin.value())
        except Exception as exc:  # pragma: no cover
            self.status.setText(f"Erro na varredura: {exc}")
            return []
        self._plot_sweep(rows)
        ok = sum(1 for r in rows if r.get("converged"))
        self.status.setText(f"Varredura H₂S: {ok}/{len(rows)} pontos convergiram.")
        return rows

    def _fill_table(self, metrics: dict):
        self.table.setRowCount(0)
        for label, key, unit in _RESULT_ROWS:
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
        xs = [r["feed_H2S_pct"] for r in rows if r.get("converged")]
        h2sr = [r.get("H2S_removal") for r in rows if r.get("converged")]
        rec = [r.get("recovery_CH4") for r in rows if r.get("converged")]
        co2r = [r.get("CO2_removal") for r in rows if r.get("converged")]
        self.ax.clear()
        if xs:
            self.ax.plot(xs, h2sr, "-o", label="Remoção H₂S (%)", markersize=3)
            self.ax.plot(xs, rec, "-s", label="Recuperação CH₄ (%)", markersize=3)
            self.ax.plot(xs, co2r, "-^", label="Remoção CO₂ (%)", markersize=3)
        self.ax.set_xlabel("H₂S na alimentação (mol%)")
        self.ax.set_ylabel("%")
        self.ax.set_title("Desempenho vs H₂S")
        self.ax.legend(fontsize=8)
        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw_idle()


__all__ = ["MainWindow", "PRESETS"]
