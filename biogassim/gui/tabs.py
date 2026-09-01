"""Abas da GUI moderna do BioGasSim (camada de visão).

Cada aba é apenas apresentação + fiação de sinais: toda a ciência reusa o
backend compartilhado com a CLI (``biogassim.cases``, ``biogassim.studies``,
``biogassim.comparison``, ``biogassim.Properties``) -- nenhuma conta foi
duplicada em classes de GUI (regra do prompt de modernização).

Estrutura-alvo (modernização):
  * :class:`ProjectTab`         -- projeto corrente (novo/abrir/salvar/info).
  * :class:`FeedTab`            -- alimentação & propriedades (extraída da antiga
    aba Simulação, sem mudança demodelo: spin+slider+presets, normalização).
  * :class:`GasWashingTab`      -- tecnologia/operacionais + segurança de H2S
    (classificação PASS/WARNING/FAIL).
  * :class:`ResultsTab`         -- dashboard de métricas + log do solver
    (colapsável) + estado visual.
  * :class:`PerformanceTab`     -- desempenho & economia (leitura do estado;
    QScrollArea própria).
  * :class:`ParametricTab`      -- estudos paramétricos canceláveis (worker).
  * :class:`ReportsTab`         -- exportação (JSON/CSV/HTML/XLSX).

Observação de arquitetura: **cada aba é embrulhada em QScrollArea própria**
(assim como as sub-abas da comparação já eram) -- as barras de rolagem são
independentes entre abas por construção do QTabWidget.
"""
from __future__ import annotations

from .. import cases, safety
from ..Properties import mixture_properties_general
from .qt import Qt, QtWidgets
from .state import (
    STATE_CONVERGED,
    STATE_FAILED,
    STATE_READY,
    STATE_RUNNING,
    AppState,
    state_css,
)
from .workers import ParametricWorker, friendly_error

# canvas matplotlib (opcional -- degrada com elegância)
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _Canvas
    from matplotlib.figure import Figure
    _HAS_PLOT = True
except Exception:  # pragma: no cover
    _HAS_PLOT = False

QAction = None  # (não usado aqui; main_window define o port)


# --------------------------------------------------------------------------- #
# constantes de apresentação (mesmas da versão anterior -- preservadas)
# --------------------------------------------------------------------------- #
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

# Unidades de vazão da alimentação (rótulo, decimais, fator).
# O fator converte a unidade exibida -> mol/s (SI). Fator None => dinâmico
# (depende da composição; calculado pelo backend em FeedTab._flow_factor).
# O caso (case.json) guarda sempre ``flow_mols`` em mol/s -- a unidade é só
# preferência de exibição/entrada da GUI.
_FLOW_RANGE_MOLS = (1.0, 1e5)          # faixa física admitida, em mol/s
FLOW_UNITS = [                          # (rótulo, decimais, fator)
    ("mol/s", 1, 1.0),
    ("mol/h", 0, 1.0 / 3600.0),
    ("kmol/s", 3, 1000.0),
    ("kmol/h", 2, 1000.0 / 3600.0),
    ("kg/h", 1, None),                 # massa: requer massa molar da mistura
    ("Nm³/h", 1, None),                # volume normal: requer densidade normal
]

# Métricas do dashboard de resultados (rótulo, chave, unidade).
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

# Seções do painel Desempenho & Economia (título, [(chave, rótulo, unidade)]).
_PERF_SECTIONS = [
    ("Desempenho", [
        ("purity_CH4", "Pureza CH₄", "%", "{:.2f}"),
        ("recovery_CH4", "Recuperação CH₄", "%", "{:.2f}"),
        ("CO2_removal", "Remoção CO₂", "%", "{:.2f}"),
        ("H2S_removal", "Remoção H₂S", "%", "{:.2f}"),
        ("methane_loss", "Perda de metano", "%", "{:.2f}"),
    ]),
    ("Energia", [
        ("total_kW", "Potência total", "kW", "{:.2f}"),
        ("specific_kWh_per_Nm3", "Consumo específico", "kWh/Nm³", "{:.4f}"),
        ("dryer_regen_kW", "Secador (regeneração)", "kW", "{:.3f}"),
        ("recycle_compression_kW", "Recompressão do reciclo", "kW", "{:.2f}"),
        ("lean_pump_kW", "Bomba do solvente", "kW", "{:.2f}"),
    ]),
    ("Dimensionamento hidráulico", [
        ("diameter_m", "Diâmetro da coluna", "m", "{:.3f}"),
        ("height_m", "Altura", "m", "{:.2f}"),
        ("flooding_pct", "Margem de inundação", "%", "{:.1f}"),
        ("pressure_drop_Pa", "Perda de carga", "Pa", "{:.2f}"),
    ]),
    ("Água", [
        ("water_m3_per_h", "Consumo (makeup)", "m³/h", "{:.3f}"),
        ("water_circulation_m3_per_h", "Circulação (L/V)", "m³/h", "{:.2f}"),
        ("solvent_flow_mols", "Vazão de solvente", "mol/s", "{:.1f}"),
    ]),
    ("Economia", [
        ("opex_usd_yr", "OPEX", "USD/ano", "{:.0f}"),
        ("specific_cost_usd_per_Nm3", "Custo específico", "USD/Nm³", "{:.4f}"),
        ("co2_avoided_t_per_yr", "CO₂ evitado", "t/ano", "{:.1f}"),
    ]),
    ("Qualidade do gás tratado", [
        ("treated_CH4_pct", "CH₄", "%", "{:.2f}"),
        ("treated_CO2_pct", "CO₂", "%", "{:.2f}"),
        ("treated_H2S_ppm", "H₂S", "ppm", "{:.1f}"),
        ("treated_LHV_MJ_per_Nm3", "PCI (LHV)", "MJ/Nm³", "{:.2f}"),
        ("treated_HHV_MJ_per_Nm3", "PCS (HHV)", "MJ/Nm³", "{:.2f}"),
        ("treated_wobbe_MJ_per_Nm3", "Índice de Wobbe", "MJ/Nm³", "{:.2f}"),
        ("treated_density_kg_per_Nm3", "Densidade normal", "kg/Nm³", "{:.3f}"),
        ("treated_H2O_mg_per_Nm3", "H₂O (antes do secador)", "mg/Nm³", "{:.1f}"),
        ("treated_dew_point_C", "Ponto de orvalho (H₂O)", "°C", "{:.1f}"),
    ]),
]

_COMPS = ("CH4", "CO2", "H2S")
_COMP_LABEL = {"CH4": "CH₄", "CO2": "CO₂", "H2S": "H₂S"}


def wrap_scroll(widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    """Embrulha um widget em QScrollArea com scrollbar **própria e independente**
    (frameless, widgetResizable) -- regra da modernização para todas as abas."""
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    scroll.setWidget(widget)
    return scroll


# --------------------------------------------------------------------------- #
# Aba: Projeto
# --------------------------------------------------------------------------- #
class ProjectTab(QtWidgets.QWidget):
    """Informações do projeto corrente + atalhos de arquivo."""

    def __init__(self, app_state: AppState, project, main):
        super().__init__()
        self.app = app_state
        self.project = project
        self.main = main
        lay = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QGroupBox("Projeto corrente")
        form = QtWidgets.QFormLayout(info)
        self.name_lbl = QtWidgets.QLabel(project.display_name())
        self.path_lbl = QtWidgets.QLabel(project.path or "—")
        self.path_lbl.setWordWrap(True)
        self.dirty_lbl = QtWidgets.QLabel("Salvo" if not project.dirty else "Não salvo")
        form.addRow("Nome:", self.name_lbl)
        form.addRow("Arquivo:", self.path_lbl)
        form.addRow("Estado:", self.dirty_lbl)
        lay.addWidget(info)

        btns = QtWidgets.QGroupBox("Arquivo")
        bl = QtWidgets.QGridLayout(btns)
        actions = [
            ("Novo projeto…", lambda: main.project_new()),
            ("Abrir…", lambda: main.project_open()),
            ("Salvar", lambda: main.project_save()),
            ("Salvar como…", lambda: main.project_save_as()),
        ]
        for i, (label, slot) in enumerate(actions):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(slot)
            bl.addWidget(b, i // 2, i % 2)
        lay.addWidget(btns)
        lay.addStretch(1)

        self.project.project_changed.connect(self._refresh)
        self._refresh(project.path, project.dirty)

    def _refresh(self, path: str, dirty: bool):
        self.name_lbl.setText(self.project.display_name())
        self.path_lbl.setText(path or "—")
        self.dirty_lbl.setText("⚠ Não salvo" if dirty else "Salvo")
        self.dirty_lbl.setStyleSheet("color: #b00; font-weight: 600;" if dirty
                                     else "color: #060;")


# --------------------------------------------------------------------------- #
# Aba: Alimentação & Condições de Operação
# --------------------------------------------------------------------------- #
class FeedTab(QtWidgets.QWidget):
    """Composição (CH₄/CO₂/H₂S) + vazão + leitura de propriedades.

    Extraída da antiga aba Simulação **sem alterar a lógica** de normalização
    (editar um componente redistribui o restante preservando a razão dos
    outros dois) nem da leitura de propriedades (via backend).
    """

    def __init__(self, app_state: AppState, main):
        super().__init__()
        self.app = app_state
        self.main = main
        self._updating = False
        self._comp = {"CH4": 0.47, "CO2": 0.53, "H2S": 0.0}

        lay = QtWidgets.QHBoxLayout(self)

        left = QtWidgets.QVBoxLayout()
        left.addWidget(self._build_operating_group())
        left.addWidget(self._build_composition_group())
        left.addStretch(1)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self._build_readouts_group(), 1)
        right.addStretch(1)

        lay.addLayout(left, 0)
        lay.addLayout(right, 1)

    # -- painéis ------------------------------------------------------------- #
    def _build_operating_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Condições da alimentação")
        form = QtWidgets.QFormLayout(box)
        self.flow_spin = QtWidgets.QDoubleSpinBox()
        self.flow_spin.valueChanged.connect(lambda _v: self.main.feed_changed.emit())
        self.flow_unit = QtWidgets.QComboBox()
        for label, _dec, _f in FLOW_UNITS:
            self.flow_unit.addItem(label)
        self._flow_unit_idx = 0
        self.flow_unit.currentIndexChanged.connect(self._on_flow_unit_changed)
        self._update_flow_range()
        self.set_flow_mols(100.0)
        flow_row = QtWidgets.QHBoxLayout()
        flow_row.addWidget(self.flow_spin, 1)
        flow_row.addWidget(self.flow_unit)
        flow_holder = QtWidgets.QWidget()
        flow_holder.setLayout(flow_row)
        form.addRow("Vazão do biogás", flow_holder)
        lab = QtWidgets.QLabel("Temperatura: 25 °C | Modelo termodinâmico: Peng–Robinson")
        lab.setStyleSheet("color: #444;")
        form.addRow(lab)
        return box

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
            sp.valueChanged.connect(lambda v, name=s: self._set_component(name, v / 100.0))
            sl.valueChanged.connect(lambda v, name=s: self._set_component(name, v / 1000.0))
            self.spins[s] = sp
            self.sliders[s] = sl
            lay.addWidget(QtWidgets.QLabel(f"{_COMP_LABEL[s]} (%)"), row, 0)
            lay.addWidget(sp, row, 1)
            lay.addWidget(sl, row, 2)
            row += 1

        self.total_lbl = QtWidgets.QLabel("100.0 %")
        self.total_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(QtWidgets.QLabel("Total"), row, 0)
        lay.addWidget(self.total_lbl, row, 1, 1, 2)
        self.feed_box = box
        return box

    def _build_readouts_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Propriedades da mistura (calculadas pelo backend)")
        form = QtWidgets.QFormLayout(box)
        self.readout_labels: dict[str, QtWidgets.QLabel] = {}
        for key, label, unit, _fmt in _READOUTS:
            val = QtWidgets.QLabel("-")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.readout_labels[key] = val
            form.addRow(f"{label} [{unit}]" if unit else label, val)
        return box

    # -- helpers de widgets -------------------------------------------------- #
    @staticmethod
    def _pct_spin() -> QtWidgets.QDoubleSpinBox:
        s = QtWidgets.QDoubleSpinBox()
        s.setRange(0.0, 100.0)
        s.setDecimals(2)
        s.setSingleStep(0.5)
        s.setSuffix(" %")
        return s

    @staticmethod
    def _pct_slider() -> QtWidgets.QSlider:
        sl = QtWidgets.QSlider(Qt.Horizontal)
        sl.setRange(0, 1000)
        return sl

    # -- vazão: unidades de entrada (o caso guarda sempre mol/s) ------------- #
    def _flow_factor(self, idx: int | None = None) -> float:
        """Fator unidade-exibida -> mol/s. Para kg/h e Nm³/h o fator depende
        da composição (massa molar e densidade normal, via backend)."""
        label, _dec, f = FLOW_UNITS[self.flow_unit.currentIndex()
                                    if idx is None else idx]
        if f is not None:
            return float(f)
        comp = {s: v for s, v in self._comp.items() if v > 1e-9} or {"CH4": 1.0}
        props = mixture_properties_general(comp, T=298.15, P=101325.0).as_dict()
        mm = float(props["molar_mass_gmol"])          # g/mol
        if label == "kg/h":
            return 1000.0 / 3600.0 / mm               # kg/h -> mol/s
        rho_n = float(props["density_normal"])        # kg/Nm³
        return 1000.0 * rho_n / 3600.0 / mm           # Nm³/h -> mol/s

    def flow_mols(self) -> float:
        """Vazão da alimentação em mol/s (unidade canônica do caso)."""
        return max(self.flow_spin.value() * self._flow_factor(), 0.0)

    def set_flow_mols(self, mols: float):
        """Define a vazão física (mol/s), exibida na unidade corrente."""
        self.flow_spin.setValue(float(mols) / self._flow_factor())

    def format_flow(self, mols: float) -> str:
        """Formata uma vazão em mol/s na unidade corrente do seletor
        (p/ exibição em outras abas -- cabeçalho da Comparação, status)."""
        label, dec, _f = FLOW_UNITS[self.flow_unit.currentIndex()]
        return f"{mols / self._flow_factor():.{dec}f} {label}"

    def _update_flow_range(self):
        label, dec, _f = FLOW_UNITS[self.flow_unit.currentIndex()]
        lo, hi = _FLOW_RANGE_MOLS
        f = self._flow_factor()
        self.flow_spin.setRange(lo / f, hi / f)
        self.flow_spin.setDecimals(dec)
        self.flow_spin.setSuffix(f" {label}")

    def _on_flow_unit_changed(self, idx: int):
        """Troca de unidade preservando o valor físico da vazão."""
        mols = self.flow_spin.value() * self._flow_factor(self._flow_unit_idx)
        self._flow_unit_idx = idx
        self._update_flow_range()
        self.flow_spin.setValue(mols / self._flow_factor())

    # -- composição: preservado da versão anterior --------------------------- #
    def _set_component(self, name: str, frac: float):
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
            for o in others:
                self._comp[o] = rem if o == "CO2" else 0.0
        self._comp[name] = frac
        tot = sum(self._comp.values())
        if tot > 0:
            for s in _COMPS:
                self._comp[s] = self._comp[s] / tot
        self.set_composition(dict(self._comp))

    def set_composition(self, comp: dict):
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
        self.refresh_props()
        self.main.feed_changed.emit()

    def _on_preset(self, name: str):
        frac = PRESETS.get(name)
        if frac is not None:
            self.set_composition(dict(frac))

    def refresh_props(self, p_bar: float = 1.01325):
        comp = {s: self._comp[s] for s in _COMPS if self._comp[s] > 0}
        if not comp:
            comp = {"CH4": 1.0}
        props = mixture_properties_general(comp, T=298.15, P=p_bar * 1e5)
        d = props.as_dict()
        for key, _label, _unit, fmt in _READOUTS:
            if key in d:
                self.readout_labels[key].setText(fmt.format(d[key]))


# --------------------------------------------------------------------------- #
# Aba: Lavagem de Gás (tecnologia + operacionais + H2S PASS/WARNING/FAIL)
# --------------------------------------------------------------------------- #
class GasWashingTab(QtWidgets.QWidget):
    """Tecnologia/solvente, condições da coluna e segurança de H₂S."""

    def __init__(self, app_state: AppState, main):
        super().__init__()
        self.app = app_state
        self.main = main

        lay = QtWidgets.QHBoxLayout(self)

        # coluna esquerda: tecnologia + condições
        box = QtWidgets.QGroupBox("Sistema de lavagem / absorção")
        form = QtWidgets.QFormLayout(box)
        self.tech = QtWidgets.QComboBox()
        self.tech.addItems(list(cases.TECHNOLOGIES))
        self.tech.currentTextChanged.connect(main._on_tech_changed)
        self.p_spin = self._num_spin(0.5, 120.0, 20.0, 1, " bar")
        self.t_spin = self._num_spin(0.0, 80.0, 20.0, 1, " °C")
        self.lv_spin = self._num_spin(1.0, 1000.0, 100.0, 1, "")
        self.n_spin = QtWidgets.QSpinBox()
        self.n_spin.setRange(1, 60)
        self.n_spin.setValue(12)
        self.h_spin = self._num_spin(1.0, 60.0, 15.0, 1, " m")
        for sp in (self.p_spin, self.t_spin, self.lv_spin, self.n_spin, self.h_spin):
            sp.valueChanged.connect(self.main.on_operating_changed)
        form.addRow("Tecnologia", self.tech)
        form.addRow("Pressão da coluna", self.p_spin)
        form.addRow("Temperatura da coluna", self.t_spin)
        form.addRow("Razão L/V", self.lv_spin)
        form.addRow("Nº de estágios", self.n_spin)
        form.addRow("Altura de recheio", self.h_spin)
        note = QtWidgets.QLabel(
            "Água (physical washing): absorve CO₂/H₂S/H₂O. MEA (amina reativa): "
            "absorção química, carregamento rico α ≤ 0,5.")
        note.setWordWrap(True)
        form.addRow(note)
        lay.addWidget(box, 0)

        # coluna direita: segurança H2S com classificação
        safe = QtWidgets.QGroupBox("Segurança — H₂S")
        sl = QtWidgets.QVBoxLayout(safe)
        self.safety_state_lbl = QtWidgets.QLabel("—")
        self.safety_state_lbl.setAlignment(Qt.AlignCenter)
        self.safety_state_lbl.setStyleSheet("font-weight: 700; padding: 6px;")
        sl.addWidget(self.safety_state_lbl)
        self.safety_lbl = QtWidgets.QLabel("Sem H₂S na alimentação.")
        self.safety_lbl.setWordWrap(True)
        self.safety_lbl.setStyleSheet("color: #444;")
        sl.addWidget(self.safety_lbl)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Limite máx. H₂S no gás tratado (ppm):"))
        self.maxh2s_spin = QtWidgets.QDoubleSpinBox()
        self.maxh2s_spin.setRange(0.0, 1000.0)
        self.maxh2s_spin.setDecimals(1)
        self.maxh2s_spin.setValue(safety.max_h2s_treated_ppm())
        self.maxh2s_spin.valueChanged.connect(self.main.refresh_safety)
        row.addWidget(self.maxh2s_spin)
        row.addStretch(1)
        sl.addLayout(row)
        lim = QtWidgets.QLabel(
            f"Referências: IDLH {safety.H2S_IDLH_PPM:.0f} ppm · TLV-TWA "
            f"{safety.H2S_TLV_TWA_PPM} ppm · gasoduto ~{safety.H2S_PIPELINE_PPM} ppm · "
            f"motor ~{safety.H2S_ENGINE_TYPICAL_PPM} ppm")
        lim.setWordWrap(True)
        lim.setStyleSheet("color: #555;")
        sl.addWidget(lim)
        sl.addStretch(1)
        lay.addWidget(safe, 1)

    @staticmethod
    def _num_spin(lo, hi, val, decimals, suffix) -> QtWidgets.QDoubleSpinBox:
        s = QtWidgets.QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(decimals)
        s.setValue(val)
        s.setSuffix(suffix)
        return s

    # -- classificação PASS/WARNING/FAIL --------------------------------- #
    def update_safety(self, metrics: dict | None = None):
        """Avalia a segurança de H₂S: sem resultado => baseado no feed;
        com métricas => PASS/WARNING/FAIL pelo limite configurado."""
        feed_h2s = self.main.feed_comp().get("H2S", 0.0)
        limit = self.maxh2s_spin.value()
        safety.set_max_h2s_treated_ppm(limit)
        if not safety.h2s_present(feed_h2s):
            self.safety_state_lbl.setText("OK — sem H₂S na alimentação")
            self.safety_state_lbl.setStyleSheet(state_css(STATE_CONVERGED))
            self.safety_lbl.setText("Sem H₂S na alimentação.")
            self.safety_lbl.setStyleSheet("color: #444;")
            return
        t_ppm = float((metrics or {}).get("treated_H2S_ppm", 0.0) or 0.0)
        if metrics is None:
            level, color = "WARNING", "#856404"
            head = (f"WARNING — H₂S presente na alimentação "
                    f"({feed_h2s * 100:.4f} % mol) — gás tóxico/corosivo. "
                    f"Execute o caso para avaliar o gás tratado.")
        else:
            liquid = metrics.get("liquid_H2S_loading_mol_per_mol")
            warns = safety.h2s_warnings(feed_h2s, t_ppm, liquid, max_ppm=limit)
            suit = safety.engine_suitable(t_ppm, max_ppm=limit)
            if suit:
                level, color = "PASS", "#155724"
            elif limit > 0.0 and t_ppm <= max(limit * 2.0, limit + 5.0):
                level, color = "WARNING", "#856404"
            else:
                level, color = "FAIL", "#721c24"
            head = f"{level} — H₂S tratado: {t_ppm:.1f} ppm (limite {limit:.1f} ppm)"
            head += ("\nAdequado para motor/gasoduto: SIM" if suit
                     else "\nAdequado para motor/gasoduto: NÃO")
            head += "\n\n" + "\n".join(warns)
        self.safety_state_lbl.setText(head.splitlines()[0])
        self.safety_state_lbl.setStyleSheet(
            state_css(STATE_CONVERGED if level == "PASS" else
                      (STATE_FAILED if level == "FAIL" else STATE_RUNNING)))
        self.safety_lbl.setText(head)
        self.safety_lbl.setStyleSheet(f"color: {color}; font-weight: 600;"
                                      if level != "PASS" else "color: #060;")

    def reset_safety(self):
        self.update_safety(None)


# --------------------------------------------------------------------------- #
# Aba: Resultados do Processo (dashboard + log do solver)
# --------------------------------------------------------------------------- #
class ResultsTab(QtWidgets.QWidget):
    """Dashboard de métricas do último caso + log do solver colapsável."""

    def __init__(self, app_state: AppState, main):
        super().__init__()
        self.app = app_state
        self.main = main

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        # faixa de estado + mensagem
        banner = QtWidgets.QWidget()
        bl = QtWidgets.QHBoxLayout(banner)
        bl.setContentsMargins(8, 4, 8, 4)
        self.state_chip = QtWidgets.QLabel("Pronto")
        self.state_chip.setStyleSheet(state_css(STATE_READY))
        self.state_chip.setFixedWidth(140)
        self.state_chip.setAlignment(Qt.AlignCenter)
        bl.addWidget(self.state_chip)
        self.message_lbl = QtWidgets.QLabel(
            "Configure a alimentação e execute a simulação (F5).")
        self.message_lbl.setWordWrap(True)
        bl.addWidget(self.message_lbl, 1)
        self.stale_lbl = QtWidgets.QLabel("")
        self.stale_lbl.setStyleSheet("color: #b00; font-weight: 600;")
        bl.addWidget(self.stale_lbl)
        lay.addWidget(banner)

        # tabela de métricas
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Métrica", "Valor", "Unidade"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table, 1)

        # log do solver colapsável
        self.log_btn = QtWidgets.QPushButton("▸ Log do solver")
        self.log_btn.setCheckable(True)
        self.log_btn.toggled.connect(lambda on: self.log_group.setVisible(on))
        self.log_btn.toggled.connect(
            lambda on: self.log_btn.setText("▾ Log do solver" if on else "▸ Log do solver"))
        lay.addWidget(self.log_btn)
        self.log_group = QtWidgets.QWidget()
        gl = QtWidgets.QVBoxLayout(self.log_group)
        gl.setContentsMargins(0, 0, 0, 0)
        self.log_edit = QtWidgets.QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(160)
        self.log_edit.setPlaceholderText(
            "Linhas de convergência e mensagens do solver aparecem aqui.")
        gl.addWidget(self.log_edit)
        self.log_group.setVisible(False)
        lay.addWidget(self.log_group)

        self.app.sim_state_changed.connect(self.on_state)
        self.app.solver_log.connect(self._append_log)

    # -- reações ------------------------------------------------------------- #
    def on_state(self, state: str):
        from .state import STATE_STYLE
        text = STATE_STYLE.get(state, ("?",))[0]
        self.state_chip.setText(text)
        self.state_chip.setStyleSheet(state_css(state))

    def _append_log(self, line: str):
        self.log_edit.appendPlainText(line)

    def show_message(self, msg: str):
        self.message_lbl.setText(msg)

    def mark_stale_banner(self, on: bool):
        self.stale_lbl.setText(
            "⚠ Resultados desatualizados — condições de alimentação mudaram. "
            "Reexecute a simulação." if on else "")

    def fill(self, metrics: dict, stale: bool = False):
        """Popula a tabela de métricas (valores do backend, sem formatação local
        de números além do str -- a fonte é ``cases.run_case``)."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for label, key, unit in _RESULT_ROWS:
            if key not in metrics or metrics[key] is None:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            it_l = QtWidgets.QTableWidgetItem(label)
            it_v = QtWidgets.QTableWidgetItem(str(metrics[key]))
            it_v.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_u = QtWidgets.QTableWidgetItem(unit)
            if stale:
                for it in (it_l, it_v, it_u):
                    f = it.font()
                    f.setItalic(True)
                    f.setStrikeOut(False)
                    it.setFont(f)
                    it.setForeground(Qt.gray)
            self.table.setItem(row, 0, it_l)
            self.table.setItem(row, 1, it_v)
            self.table.setItem(row, 2, it_u)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()


# --------------------------------------------------------------------------- #
# Aba: Desempenho & Economia
# --------------------------------------------------------------------------- #
class PerformanceTab(QtWidgets.QWidget):
    """Leitura detalhada de desempenho/economia do último caso + resumo da
    comparação de métodos (mesmo objeto de resultado compartilhado)."""

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app = app_state

        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        self.hint_lbl = QtWidgets.QLabel(
            "Sem resultados ainda — execute a simulação (F5) ou uma comparação.")
        lay.addWidget(self.hint_lbl)

        # seções de métricas (todas vindas do dict de métricas do backend)
        self.tables: list[tuple[str, QtWidgets.QTableWidget]] = []
        self.group_boxes = QtWidgets.QWidget()
        gl = QtWidgets.QVBoxLayout(self.group_boxes)
        for title, rows in _PERF_SECTIONS:
            gb = QtWidgets.QGroupBox(title)
            tl = QtWidgets.QVBoxLayout(gb)
            t = QtWidgets.QTableWidget(0, 3)
            t.setHorizontalHeaderLabels(["Métrica", "Valor", "Unidade"])
            t.horizontalHeader().setStretchLastSection(True)
            t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            t.setAlternatingRowColors(True)
            t.verticalHeader().setVisible(False)
            t.setMinimumHeight(min(30 * (len(rows) + 1), 220))
            tl.addWidget(t)
            self.tables.append((title, t))
            gl.addWidget(gb)

        # resumo da comparação (mesmo resultado compartilhado com a aba Comparação)
        self.cmp_box = QtWidgets.QGroupBox("Comparação de métodos — melhor por critério")
        cl = QtWidgets.QVBoxLayout(self.cmp_box)
        self.cmp_lbl = QtWidgets.QLabel("—")
        self.cmp_lbl.setWordWrap(True)
        cl.addWidget(self.cmp_lbl)
        gl.addWidget(self.cmp_box)
        gl.addStretch(1)
        lay.addWidget(self.group_boxes)

        # QScrollArea própria: rolagem independente da aba Comparação
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(wrap_scroll(page))

        self.app.metrics_ready.connect(lambda _m: self.refresh())
        self.app.comparison_ready.connect(lambda _rows: self.refresh())

    def refresh(self):
        m = self.app.metrics
        has_cmp = bool(self.app.comparison_rows)
        self.hint_lbl.setVisible(not (bool(m) or has_cmp))
        self.group_boxes.setVisible(bool(m))
        if m:
            for _title, t in self.tables:
                t.setRowCount(0)
            for i, (_title, rows) in enumerate(_PERF_SECTIONS):
                t = self.tables[i][1]
                for key, label, unit, fmt in rows:
                    v = m.get(key)
                    if v is None:
                        continue
                    r = t.rowCount()
                    t.insertRow(r)
                    t.setItem(r, 0, QtWidgets.QTableWidgetItem(label))
                    try:
                        txt = fmt.format(float(v))
                    except (TypeError, ValueError):
                        txt = str(v)
                    iv = QtWidgets.QTableWidgetItem(txt)
                    iv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    t.setItem(r, 1, iv)
                    t.setItem(r, 2, QtWidgets.QTableWidgetItem(unit))
                t.resizeColumnsToContents()
        # resumo da comparação
        texts: list[str] = []
        if has_cmp:
            from .comparison_tab import _COMPARE_METRICS
            for key, label in _COMPARE_METRICS[:6]:
                ok = [r for r in self.app.comparison_rows
                      if r.get("converged") and r.get(key) is not None]
                if not ok:
                    continue
                best = max(ok, key=lambda r: float(r[key]))
                texts.append(f"• {label}: {best.get('method_label', '?')}")
            n_ok = sum(1 for r in self.app.comparison_rows if r.get("converged"))
            texts.insert(0,
                f"Métodos comparados: {n_ok}/{len(self.app.comparison_rows)} convergiram.")
        self.cmp_box.setVisible(bool(texts))
        self.cmp_lbl.setText("\n".join(texts) if texts else "—")


# --------------------------------------------------------------------------- #
# Aba: Estudos Paramétricos
# --------------------------------------------------------------------------- #
_PARAM_STUDIES = [
    ("h2s", "H₂S na alimentação (0–5 %) — água"),
    ("ch4", "Composição CH₄ (20–95 %)"),
    ("P_bar", "Pressão da coluna (bar)"),
    ("T_C", "Temperatura da coluna (°C)"),
    ("L_over_V", "Razão L/V"),
    ("N_stages", "Nº de estágios"),
    ("height_m", "Altura de recheio (m)"),
    ("flow_mols", "Vazão de biogás (mol/s)"),
]

_PLOT_METRICS = [
    ("purity_CH4", "Pureza CH₄ (%)"),
    ("recovery_CH4", "Recuperação CH₄ (%)"),
    ("CO2_removal", "Remoção CO₂ (%)"),
    ("H2S_removal", "Remoção H₂S (%)"),
    ("treated_H2S_ppm", "H₂S tratado (ppm)"),
    ("methane_loss", "Perda CH₄ (%)"),
    ("total_kW", "Energia total (kW)"),
    ("specific_kWh_per_Nm3", "Energia específica (kWh/Nm³)"),
    ("diameter_m", "Diâmetro (m)"),
    ("specific_cost_usd_per_Nm3", "Custo específico (USD/Nm³)"),
]
_PLOT_METRIC_KEYS = {k for k, _l in _PLOT_METRICS} | {"converged"}


class ParametricTab(QtWidgets.QWidget):
    """Estudos paramétricos (varreduras 1-D) executados em thread separada,
    canceláveis (:class:`biogassim.gui.workers.ParametricWorker`).

    Cada ponto roda um ``cases.Case`` no backend compartilhado com a CLI; a GUI
    só coleta as linhas (streaming na tabela) e desenha o gráfico.
    """

    def __init__(self, app_state: AppState, main):
        super().__init__()
        self.app = app_state
        self.main = main
        self.rows: list[dict] = []
        self.worker = None
        self._col_keys: list[str] = []

        lay = QtWidgets.QVBoxLayout(self)

        cfg = QtWidgets.QGroupBox("Configuração do estudo")
        form = QtWidgets.QFormLayout(cfg)
        self.study_cmb = QtWidgets.QComboBox()
        for _k, label in _PARAM_STUDIES:
            self.study_cmb.addItem(label)
        self.var_spin = QtWidgets.QSpinBox()
        self.var_spin.setRange(3, 50)
        self.var_spin.setValue(8)
        self.var_spin.setToolTip("Número de pontos da varredura.")
        form.addRow("Estudo", self.study_cmb)
        form.addRow("Nº de pontos", self.var_spin)
        lay.addWidget(cfg)

        btns = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("▶ Executar estudo")
        self.run_btn.setStyleSheet("font-weight: 600;")
        self.run_btn.clicked.connect(self.run)
        self.stop_btn = QtWidgets.QPushButton("■ Parar")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        export = QtWidgets.QPushButton("💾 Exportar CSV…")
        export.clicked.connect(self._on_export)
        btns.addWidget(self.run_btn)
        btns.addWidget(self.stop_btn)
        btns.addWidget(export)
        btns.addStretch(1)
        self.progress_lbl = QtWidgets.QLabel("Pronto.")
        self.progress_lbl.setStyleSheet("color: #444;")
        btns.addWidget(self.progress_lbl, 1)
        lay.addLayout(btns)

        split = QtWidgets.QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.setStretchFactor(0, 2)

        plot_box = QtWidgets.QGroupBox("Gráfico do estudo")
        pl = QtWidgets.QVBoxLayout(plot_box)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Métrica:"))
        self.metric_cmb = QtWidgets.QComboBox()
        for k, lbl in _PLOT_METRICS:
            self.metric_cmb.addItem(lbl, k)
        self.metric_cmb.currentIndexChanged.connect(self._plot)
        row.addWidget(self.metric_cmb)
        row.addStretch(1)
        pl.addLayout(row)
        if _HAS_PLOT:
            self.figure = Figure(figsize=(5, 3.2))
            self.canvas = _Canvas(self.figure)
            self.ax = self.figure.add_subplot(111)
            pl.addWidget(self.canvas)
        else:  # pragma: no cover
            self.canvas = None
            pl.addWidget(QtWidgets.QLabel("matplotlib indisponível."))
        split.addWidget(plot_box)

        table_box = QtWidgets.QGroupBox("Tabela do estudo")
        tlay = QtWidgets.QVBoxLayout(table_box)
        self.table = QtWidgets.QTableWidget(0, 0)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        tlay.addWidget(self.table)
        split.addWidget(table_box)

        lay.addWidget(split, 1)

    # ------------------------------------------------------------------ #
    # grade de valores + pontos
    # ------------------------------------------------------------------ #
    def _study_key(self) -> str:
        return _PARAM_STUDIES[self.study_cmb.currentIndex()][0]

    def _grid(self) -> list:
        """Grade de valores do estudo corrente (faixas típicas de biogás)."""
        n = max(self.var_spin.value(), 2)
        k = self._study_key()
        if k == "h2s":
            return cases.frange(0.0, 0.05, 0.05 / (n - 1))
        lo, hi = self._range_for(k)
        return [round(lo + i * (hi - lo) / (n - 1), 10) for i in range(n)]

    def _range_for(self, key: str) -> tuple:
        if key in ("P_bar", "T_C", "L_over_V", "N_stages", "height_m", "flow_mols"):
            case = self.main._current_case()
            # flow_mols vive no feed (em mol/s); os demais, em operating.
            base = float(case.feed["flow_mols"] if key == "flow_mols"
                         else case.operating[key])
            span = {"P_bar": (0.25, 1.5), "T_C": (0.75, 1.5),
                    "L_over_V": (0.25, 2.0),
                    "N_stages": (0.5, 2.0), "height_m": (0.25, 2.0),
                    "flow_mols": (0.25, 3.0)}[key]
            lo = max(base * span[0], 0.5 if key != "N_stages" else 1)
            return (lo, base * span[1])
        return {"ch4": (0.20, 0.95), "h2s": (0.0, 0.05)}[key]

    def _points(self) -> list:
        """Pontos ((coluna, valor), callable) do estudo -- cada callable roda um
        caso no backend e devolve a linha de métricas."""
        k = self._study_key()
        fc = self.main.feed_conditions()
        op = dict(self.main._current_case().operating)
        comp = dict(fc["comp"])
        flow = fc["flow"]
        tech = fc["tech"]
        pts = []
        for v in self._grid():
            var_name = k
            if k == "h2s":
                r = comp["CH4"] / max(comp["CH4"] + comp["CO2"], 1e-9)
                feed = {"CH4": (1.0 - v) * r, "CO2": (1.0 - v) * (1.0 - r),
                        "H2S": v, "flow_mols": flow}
                var_name = "feed_H2S_pct"
                col_val = round(v * 100, 3)
            elif k == "ch4":
                feed = {"CH4": v, "CO2": 1.0 - v, "H2S": comp.get("H2S", 0.0),
                        "flow_mols": flow}
                var_name = "feed_CH4_pct"
                col_val = round(v * 100, 1)
            elif k == "flow_mols":
                feed = {s: c for s, c in comp.items()}
                feed["flow_mols"] = v
                col_val = v
            else:
                feed = {s: c for s, c in comp.items()}
                feed["flow_mols"] = flow
                op = {**op, k: (int(round(v)) if k == "N_stages" else float(v))}
                col_val = v
            case = cases.Case(name="gui_study", technology=tech, feed=feed,
                              operating=dict(op))

            def _fn(case=case, var_name=var_name, val=col_val):
                try:
                    mtr = cases.run_case(case)["metrics"]
                    row = {var_name: val, "converged": mtr.get("converged")}
                    for kk, vv in mtr.items():
                        if kk in _PLOT_METRIC_KEYS:
                            row[kk] = vv
                    return row
                except Exception as exc:      # ponto inviável -> linha reportada
                    return {var_name: val, "converged": False,
                            "error": friendly_error(exc)}

            pts.append(((var_name, col_val), _fn))
        return pts

    # ------------------------------------------------------------------ #
    # execução
    # ------------------------------------------------------------------ #
    def run(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.rows = []
        self.table.setRowCount(0)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_lbl.setText("Executando estudo…")
        self._col_keys = []
        self.table.setColumnCount(0)
        self.worker = ParametricWorker(self._points())
        self.worker.progress.connect(self._on_progress)
        self.worker.point.connect(self._on_point)
        self.worker.ok.connect(self._on_ok)
        self.worker.err.connect(self._on_err)
        self.worker.start()

    def _on_stop(self):
        if self.worker is not None:
            self.worker.stop()
            self.progress_lbl.setText("Parando…")

    def _on_progress(self, i, n):
        self.progress_lbl.setText(f"Ponto {i}/{n}…")

    def _on_point(self, row: dict):
        if not self._col_keys:
            self._build_columns(row)
        self.rows.append(row)
        self._append_row(row)
        self._plot()

    def _on_ok(self, rows):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        okc = sum(1 for r in rows if r.get("converged"))
        self.progress_lbl.setText(f"Concluído: {okc}/{len(rows)} pontos convergiram.")

    def _on_err(self, msg):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_lbl.setText(f"Erro: {msg}")

    # ------------------------------------------------------------------ #
    # tabela / gráfico
    # ------------------------------------------------------------------ #
    def _grid_columns(self) -> list[tuple[str, str]]:
        cols: list[tuple[str, str]] = [("_val", "Valor")]
        for col, _label, _unit in _RESULT_ROWS:
            if col in _PLOT_METRIC_KEYS and any(col in r for r in self.rows):
                cols.append((col, _label))
        return cols

    def _build_columns(self, _first_row: dict):
        cols = self._grid_columns()
        self.table.clear()
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels([lbl for _k, lbl in cols])
        self._col_keys = [k for k, _l in cols]
        self.table.setRowCount(0)

    def _append_row(self, row: dict):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, key in enumerate(self._col_keys):
            v = (row.get("_key", (None, ""))[1] if key == "_val" else row.get(key))
            txt = "" if v is None else str(v)
            item = QtWidgets.QTableWidgetItem(txt)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if key == "converged" and v is False:
                item.setForeground(Qt.red)
            self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()

    def _plot(self):
        if not _HAS_PLOT or self.canvas is None or len(self.rows) < 1:
            return
        key = self.metric_cmb.currentData()
        col = self.rows[0].get("_key", ("value", None))[0]
        pts = [(r["_key"][1], r.get(key)) for r in self.rows
               if r.get(key) is not None and r.get("converged")]
        self.ax.clear()
        if pts:
            xs, ys = zip(*pts)
            self.ax.plot(xs, ys, "-o", markersize=4, color="#3b6fb5")
            self.ax.set_xlabel(col)
            self.ax.set_ylabel(self.metric_cmb.currentText())
            self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    # exportação
    # ------------------------------------------------------------------ #
    def _on_export(self):
        if not self.rows:
            self.progress_lbl.setText("Nada para exportar — rode o estudo.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar estudo paramétrico", "study.csv", "CSV (*.csv)")
        if not path:
            return
        from ..Export import export_csv
        table = []
        for r in self.rows:
            d = {}
            for key in self._col_keys:
                v = (r.get("_key", (None, ""))[1] if key == "_val" else r.get(key))
                if v is not None:
                    d[key] = v
            table.append(d)
        try:
            export_csv(table, path)
            self.progress_lbl.setText(f"Exportado: {path}")
        except Exception as exc:
            self.progress_lbl.setText(f"Erro: {friendly_error(exc)}")


# --------------------------------------------------------------------------- #
# Aba: Relatórios
# --------------------------------------------------------------------------- #
class ReportsTab(QtWidgets.QWidget):
    """Exportação dos resultados correntes (mesmos exportadores da CLI)."""

    def __init__(self, app_state: AppState, main):
        super().__init__()
        self.app = app_state
        self.main = main
        lay = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QGroupBox("Gerar relatório do último caso")
        il = QtWidgets.QVBoxLayout(info)
        self.info_lbl = QtWidgets.QLabel(
            "Exporta as métricas do caso atual (aba Resultados do Processo) com os "
            "mesmos exportadores da CLI (biogassim.Export).")
        self.info_lbl.setWordWrap(True)
        il.addWidget(self.info_lbl)
        grid = QtWidgets.QGridLayout()
        actions = [("Métricas → JSON", self._export_json),
                   ("Métricas → CSV", self._export_csv),
                   ("Métricas → HTML", self._export_html),
                   ("Métricas → Excel", self._export_excel)]
        for i, (label, slot) in enumerate(actions):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(slot)
            grid.addWidget(b, i // 2, i % 2)
        il.addLayout(grid)
        lay.addWidget(info)

        cmp_info = QtWidgets.QGroupBox("Comparação de métodos")
        cl = QtWidgets.QVBoxLayout(cmp_info)
        cl.addWidget(QtWidgets.QLabel(
            "A exportação da comparação completa (CSV/JSON/HTML/XLSX/PDF) fica na "
            "aba Comparação de Processos → botão Exportar."))
        lay.addWidget(cmp_info)
        lay.addStretch(1)
        self.status_lbl = QtWidgets.QLabel("")
        self.status_lbl.setStyleSheet("color: #444;")
        lay.addWidget(self.status_lbl)

    def _need_metrics(self) -> bool:
        if not self.app.metrics:
            self.status_lbl.setText("Nada para exportar — execute a simulação primeiro.")
            return False
        return True

    def _pick(self, fmt: str, ext: str) -> str:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar relatório", f"biogassim_results.{ext}",
            f"{fmt} (*.{ext})")
        return path

    def _export_json(self):
        if not self._need_metrics():
            return
        path = self._pick("JSON", "json")
        if not path:
            return
        from ..Export import export_json
        export_json(dict(self.app.metrics), path)
        self.status_lbl.setText(f"Exportado: {path}")

    def _export_csv(self):
        if not self._need_metrics():
            return
        path = self._pick("CSV", "csv")
        if not path:
            return
        from ..Export import export_csv
        table = [{"metric": k, "value": v}
                 for k, v in self.app.metrics.items() if v is not None]
        export_csv(table, path)
        self.status_lbl.setText(f"Exportado: {path}")

    def _export_html(self):
        if not self._need_metrics():
            return
        path = self._pick("HTML", "html")
        if not path:
            return
        from ..Export import export_html
        table = [{"metric": k, "value": str(v)}
                 for k, v in self.app.metrics.items() if v is not None]
        export_html(table, path,
                    title=f"BioGasSim — {self.main.project.display_name()}")
        self.status_lbl.setText(f"Exportado: {path}")

    def _export_excel(self):
        if not self._need_metrics():
            return
        path = self._pick("Excel", "xlsx")
        if not path:
            return
        from ..Export import export_excel
        table = [{"metric": k, "value": str(v)}
                 for k, v in self.app.metrics.items() if v is not None]
        export_excel({"results": table}, path)
        self.status_lbl.setText(f"Exportado: {path}")


__all__ = [
    "ProjectTab", "FeedTab", "GasWashingTab", "ResultsTab", "PerformanceTab",
    "ParametricTab", "ReportsTab", "PRESETS", "wrap_scroll", "_RESULT_ROWS",
    "_READOUTS",
]
