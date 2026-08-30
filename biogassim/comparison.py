"""Motor de comparação entre tecnologias de upgrading -- backend compartilhado.

Usado pela CLI (``biogassim compare``) e pela GUI (aba "Comparação de Métodos").
Cada tecnologia é rodada sob a **mesma alimentação** (composição / vazão / T / P)
por um adaptador que reusa os módulos de processo já existentes
(``UnitOperations``, ``Solvents``, ``PSA``, ``Membranes``, ``Examples``).
**Nenhuma termodinâmica é duplicada** -- apenas orquestração e padronização.

Arquitetura (fonte única de verdade)::

    CLI  ──┐
          ├──> ComparisonEngine ──> WaterScrubbing / MEA / DEA / MDEA /
    GUI ──┘                          Selexol / Rectisol / PSA / Membrane(...)
                                       (mesmo solver da simulação principal)

* :class:`ComparisonEngine` -- recebe feed + métodos selecionados + parâmetros +
  modo (standard/optimized) + premissas econômicas; roda cada método com
  tratamento de erro individual e devolve linhas padronizadas (KPIs/energia/
  economia uniformes para comparação justa).
* :func:`best_by` / :func:`weighted_score` -- ranking uni/multi-critério.
* :func:`export_comparison` -- CSV / JSON / HTML / Excel (+ stub PDF).
* :class:`ComparisonConfig` -- persistência (salvar/restaurar configuração).

A mesma engine alimentada com o mesmo projeto gera resultados numericamente
equivalentes na CLI e na GUI (mesmo código de cálculo).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from . import cases
from .Examples import PSA, Membrane, MembraneMultiStage, WaterScrubbing
from .Optimization import EnergySummary, compression_energy, regeneration_energy
from .Properties import mixture_properties_general, normalize_mixture
from .Properties.components import get
from .Solvents import (
    DEASolvent,
    MDEASolvent,
    MEASolvent,
    SelexolSolvent,
)
from .UnitOperations import Absorber, AbsorberSpec, Stream
from .UnitOperations.Compressor import compress

# --------------------------------------------------------------------------- #
# Colunas padronizadas da tabela de comparação (chave, rótulo, unidade, fmt).
# ORDEM = ordem padrão de exibição; a GUI pode esconder/reordenar colunas.
# --------------------------------------------------------------------------- #
COLUMNS = [
    ("method", "Método", "", "{}"),
    ("status", "Estado", "", "{}"),
    ("converged", "Convergiu", "", "{}"),
    ("mass_balance_error", "Erro balanço massa", "", "{:.1e}"),
    ("gpdc_extrapolated", "GPDC extrap.", "", "{}"),
    ("purity_CH4", "Pureza CH₄", "%", "{:.2f}"),
    ("recovery_CH4", "Recuperação CH₄", "%", "{:.2f}"),
    ("CO2_removal", "Remoção CO₂", "%", "{:.2f}"),
    ("H2S_removal", "Remoção H₂S", "%", "{:.2f}"),
    ("methane_loss", "Perda CH₄", "%", "{:.2f}"),
    ("product_flow_nm3h", "Vazão gás tratado", "Nm³/h", "{:.2f}"),
    ("water_m3_per_h", "Consumo de água", "m³/h", "{:.2f}"),
    ("solvent_flow_mols", "Vazão de solvente", "mol/s", "{:.1f}"),
    ("elec_kW", "Energia elétrica", "kW", "{:.2f}"),
    ("thermal_kW", "Energia térmica", "kW", "{:.2f}"),
    ("total_kW", "Energia total", "kW", "{:.2f}"),
    ("specific_kWh_per_Nm3", "Energia específica", "kWh/Nm³", "{:.3f}"),
    ("operating_pressure_bar", "Pressão operação", "bar", "{:.2f}"),
    ("column_height_m", "Altura coluna", "m", "{:.2f}"),
    ("column_diameter_m", "Diâmetro coluna", "m", "{:.2f}"),
    ("global_efficiency_pct", "Eficiência global", "%", "{:.2f}"),
    ("opex_usd_yr", "OPEX", "USD/ano", "{:.0f}"),
    ("specific_cost_usd_per_Nm3", "Custo específico", "USD/Nm³", "{:.4f}"),
    ("treated_LHV_MJ_per_Nm3", "LHV tratado", "MJ/Nm³", "{:.2f}"),
    ("treated_HHV_MJ_per_Nm3", "HHV tratado", "MJ/Nm³", "{:.2f}"),
    ("treated_wobbe_MJ_per_Nm3", "Wobbe tratado", "MJ/Nm³", "{:.2f}"),
    ("message", "Mensagem", "", "{}"),
]


# --------------------------------------------------------------------------- #
# Especificação de métodos e parâmetros
# --------------------------------------------------------------------------- #
@dataclass
class ParamSpec:
    """Parâmetro editável de uma tecnologia (para a GUI e a CLI)."""
    key: str
    label: str
    unit: str
    lo: float
    hi: float
    default: float | str
    decimals: int = 2
    choices: tuple[str, ...] | None = None  # se informado, vira caixa de seleção

    def coerce(self, value):
        if self.choices is not None:
            return str(value)
        return float(value)


@dataclass
class MethodSpec:
    """Descriptor de uma tecnologia de upgrading comparável."""
    key: str
    label: str
    status: str               # "operational" | "experimental"
    category: str             # "water" | "amine" | "physical" | "psa" | "membrane"
    params: list[ParamSpec]
    adapter: Callable[[dict, float, dict], dict]
    recommended: bool = True   # entra no conjunto "métodos recomendados"

    def default_params(self) -> dict:
        return {p.key: p.default for p in self.params}


# ------------------------------- adaptadores -------------------------------- #
# Cada adaptador recebe (composition, flow, params) e devolve um dict de
# métricas "cruas" (campos variáveis por tecnologia). O engine padroniza depois.
# Reusam os mesmos run_case / Absorber / Solvent -- sem duplicar ciência.

def _ch4_co2(composition: dict | None) -> dict:
    """Composição CH4/CO2 renormalizada (aminas/PSA/membrana modelam CH4-CO2)."""
    if not composition:
        return {"CH4": 0.47, "CO2": 0.53}
    c = {k: float(v) for k, v in composition.items()
         if k in ("CH4", "CO2") and float(v) > 0.0}
    if not c:
        return {"CH4": 0.47, "CO2": 0.53}
    return normalize_mixture(c)


# nome do kwarg de fração mássica em cada solvente amina (diferem por classe)
_AMINE_W_KW = {"MEA": "w_mea", "DEA": "w_dea", "MDEA": "w_mdea"}


def _make_solvent(solvent_cls, amine: str, w: float):
    """Instancia o solvente amina com o kwarg certo (w_mea/w_dea/w_mdea)."""
    kw = _AMINE_W_KW.get(amine, "w_mea")
    try:
        return solvent_cls(**{kw: w})
    except TypeError:
        return solvent_cls()


def _adapt_water(composition, flow, p):
    out = WaterScrubbing.run_case(
        P_bar=p["P_bar"], L_over_V=p["L_over_V"], N_stages=int(p["N_stages"]),
        height=p["height_m"], flow=flow, save=False, composition=composition)
    m = dict(out["metrics"])
    m["operating_pressure_bar"] = p["P_bar"]
    return m


def _run_amine(amine: str, solvent_cls, composition, flow, p):
    """Adaptador genérico de amina química (MEA/DEA/MDEA).

    Reusa o mesmo padrão do exemplo MEA (lean_solvent + Absorber + energia),
    parametrizando o solvente e a espécie amina. Composição = CH4/CO2 (a
    absorção reativa de H2S em amina é roadmap; H2S não é modelado aqui -- consistente
    com ``cases.run_case`` para 'mea').
    """
    comp = _ch4_co2(composition)
    species = ["CH4", "CO2", "H2O", amine]
    P = p["P_bar"] * 1e5
    from .Examples.common import biogas_stream, metrics_from_absorber
    gas_in = biogas_stream(flow, species=species, T=313.15, P=1.01325e5, composition=comp)
    c = compress(gas_in, P, eta=0.75)
    gas_feed = Stream.make(species, c.out.z, c.out.flow, c.out.T, c.out.P, "vapor")
    # solvente magro: w_amine mássico -> frações molares
    mm_a = get(amine).MM
    mm_w = get("H2O").MM
    w = p.get("w_amine", 0.30)
    x_a = (w / mm_a) / (w / mm_a + (1 - w) / mm_w)
    z = np.zeros(len(species))
    z[species.index(amine)] = x_a
    z[species.index("H2O")] = 1.0 - x_a
    solv = Stream.make(species, z, p["L_over_V"] * flow, T=313.15, P=P, phase="liquid")
    spec = AbsorberSpec(N_stages=int(p["N_stages"]), packing="Pall_50",
                        mode="isothermal", T_op=313.15, pressure=P,
                        height=p["height_m"], max_iter=400)
    r = Absorber(gas_feed, solv, _make_solvent(solvent_cls, amine, w), spec).solve()
    m = metrics_from_absorber(f"{amine} (chemical)", r, gas_in)
    i_co2 = species.index("CO2")
    co2_abs = gas_in.flow * gas_in.z[i_co2] - r.gas_out.flow * r.gas_out.z[i_co2]
    regen = regeneration_energy(max(co2_abs, 0.0), specific_mj_per_kg=4.0)
    energy = EnergySummary(compression=compression_energy([c]), regeneration=regen)
    bio_nm3h = r.gas_out.flow * 0.0224 * 3600
    energy.finalize(bio_nm3h)
    m.update({"compression_kW": round(energy.compression, 2),
              "regeneration_kW": round(energy.regeneration, 2),
              "pumping_kW": 0.0,
              "total_kW": round(energy.total_kw, 2),
              "specific_kWh_per_Nm3": round(energy.specific_kwh_per_nm3, 3),
              "operating_pressure_bar": p["P_bar"],
              "solvent_flow_mols": round(p["L_over_V"] * flow, 2),
              "amine": amine, "amine_w": w})
    m = cases._treated_gas_quality(m, r, p["P_bar"])
    return m


def _adapt_mea(composition, flow, p):
    return _run_amine("MEA", MEASolvent, composition, flow, p)


def _adapt_dea(composition, flow, p):
    return _run_amine("DEA", DEASolvent, composition, flow, p)


def _adapt_mdea(composition, flow, p):
    return _run_amine("MDEA", MDEASolvent, composition, flow, p)


def _run_physical(solvent_cls, composition, flow, p):
    """Adaptador genérico de solvente físico (Selexol/Rectisol).

    Reusa o padrão do exemplo Water (biogas_stream + Absorber + energia),
    trocando o solvente. A fase líquida usa a constante de Henry do solvente
    físico (K_value do objeto Solvent); 'H2O' é apenas o veículo líquido inerte
    no vetor de espécies (mesma lista do absorvedor de água). A massa/vazão do
    solvente usam MM/ρ do próprio solvente (não da água).
    """
    from .Examples.common import biogas_stream, metrics_from_absorber
    comp_dict = dict(composition) if composition else {"CH4": 0.47, "CO2": 0.53}
    gas_species = [s for s in comp_dict if float(comp_dict.get(s, 0.0)) > 0.0 and s != "H2O"]
    if not gas_species:
        gas_species = ["CH4", "CO2"]
    species = [*gas_species, "H2O"]
    P = p["P_bar"] * 1e5
    gas_in = biogas_stream(flow, species=species, T=298.15, P=1.01325e5, composition=comp_dict)
    c = compress(gas_in, P, eta=0.75)
    gas_feed = c.out
    z_solv = np.zeros(len(species))
    z_solv[species.index("H2O")] = 1.0
    solv = Stream.make(species, z_solv, p["L_over_V"] * flow, T=298.15, P=P, phase="liquid")
    spec = AbsorberSpec(N_stages=int(p["N_stages"]), packing="Pall_50",
                        mode="isothermal", T_op=298.15, pressure=P,
                        height=p["height_m"], max_iter=400)
    solvent = solvent_cls()
    r = Absorber(gas_feed, solv, solvent, spec).solve()
    m = metrics_from_absorber(solvent.name, r, gas_in)
    # remoção por espécie além de CH4/CO2 (H2S, NH3, N2, ...)
    for s in gas_species:
        if s in ("CH4", "CO2"):
            continue
        i = gas_in.species.index(s)
        fin = gas_in.flow * gas_in.z[i]
        if fin > 1e-12:
            fout = r.gas_out.flow * r.gas_out.z[i]
            m[f"{s}_removal"] = round(100.0 * (1.0 - fout / fin), 2)
    # pumping com MM/ρ do solvente físico (não da água)
    mm = solvent.molar_mass_liquid()
    rho = solvent.density(298.15)
    pumping = (p["L_over_V"] * flow * mm / rho) * P / 0.7 / 1000.0
    energy = EnergySummary(compression=compression_energy([c]), pumping=pumping)
    bio_nm3h = r.gas_out.flow * 0.0224 * 3600
    energy.finalize(bio_nm3h)
    m.update({"compression_kW": round(energy.compression, 2),
              "pumping_kW": round(energy.pumping, 2),
              "regeneration_kW": 0.0,
              "total_kW": round(energy.total_kw, 2),
              "specific_kWh_per_Nm3": round(energy.specific_kwh_per_nm3, 3),
              "operating_pressure_bar": p["P_bar"],
              "solvent_flow_mols": round(p["L_over_V"] * flow, 2)})
    m = cases._treated_gas_quality(m, r, p["P_bar"])
    return m


def _adapt_selexol(composition, flow, p):
    return _run_physical(SelexolSolvent, composition, flow, p)


def _adapt_rectisol(composition, flow, p):
    return _adapt_selexol(composition, flow, p)  # Rectisol usa T baixa; mesmas params aqui


def _adapt_psa(composition, flow, p):
    m = PSA.run_case(P_high_bar=p["P_high_bar"], P_low_bar=p["P_low_bar"],
                     adsorbent=p["adsorbent"], composition=composition,
                     flow=flow, save=False)["metrics"]
    m["operating_pressure_bar"] = p["P_high_bar"]
    return m


def _adapt_membrane(composition, flow, p):
    m = Membrane.run_case(material=p["material"], P_feed_bar=p["P_feed_bar"],
                          P_perm_bar=p["P_perm_bar"], stage_cut=p["stage_cut"],
                          flow=flow, composition=composition, save=False)["metrics"]
    m["operating_pressure_bar"] = p["P_feed_bar"]
    return m


def _adapt_membrane_multi(composition, flow, p):
    m = MembraneMultiStage.run_case(material=p["material"], P_feed_bar=p["P_feed_bar"],
                                    P_perm_bar=p["P_perm_bar"], flow=flow,
                                    composition=composition, save=False)["metrics"]
    m["operating_pressure_bar"] = p["P_feed_bar"]
    return m


# ------------------------------ registro de métodos ------------------------- #
def _method_registry() -> dict[str, MethodSpec]:
    def P(*a, **k):
        return ParamSpec(*a, **k)
    return {
        "water": MethodSpec(
            "water", "Water Scrubbing", "operational", "water",
            [P("P_bar", "Pressão", "bar", 1.0, 40.0, 20.0),
             P("L_over_V", "Razão L/V", "", 5.0, 500.0, 100.0),
             P("N_stages", "Nº estágios", "", 1, 40, 12, 0),
             P("height_m", "Altura", "m", 1.0, 60.0, 15.0)],
            _adapt_water),
        "mea": MethodSpec(
            "mea", "MEA (amina)", "operational", "amine",
            [P("P_bar", "Pressão", "bar", 0.5, 10.0, 2.0),
             P("L_over_V", "Razão L/V", "", 1.0, 100.0, 20.0),
             P("N_stages", "Nº estágios", "", 1, 40, 8, 0),
             P("height_m", "Altura", "m", 1.0, 60.0, 12.0),
             P("w_amine", "Concentração MEA", "fr. máss.", 0.1, 0.5, 0.30)],
            _adapt_mea),
        "dea": MethodSpec(
            "dea", "DEA (amina)", "experimental", "amine",
            [P("P_bar", "Pressão", "bar", 0.5, 10.0, 2.0),
             P("L_over_V", "Razão L/V", "", 1.0, 100.0, 20.0),
             P("N_stages", "Nº estágios", "", 1, 40, 8, 0),
             P("height_m", "Altura", "m", 1.0, 60.0, 12.0),
             P("w_amine", "Concentração DEA", "fr. máss.", 0.1, 0.5, 0.30)],
            _adapt_dea, recommended=False),
        "mdea": MethodSpec(
            "mdea", "MDEA (amina)", "operational", "amine",
            [P("P_bar", "Pressão", "bar", 0.5, 10.0, 2.0),
             P("L_over_V", "Razão L/V", "", 1.0, 100.0, 20.0),
             P("N_stages", "Nº estágios", "", 1, 40, 8, 0),
             P("height_m", "Altura", "m", 1.0, 60.0, 12.0),
             P("w_amine", "Concentração MDEA", "fr. máss.", 0.1, 0.6, 0.40)],
            _adapt_mdea),
        "selexol": MethodSpec(
            "selexol", "Selexol (solvente físico)", "operational", "physical",
            [P("P_bar", "Pressão", "bar", 5.0, 80.0, 20.0),
             P("L_over_V", "Razão L/V", "", 0.5, 50.0, 5.0),
             P("N_stages", "Nº estágios", "", 1, 40, 10, 0),
             P("height_m", "Altura", "m", 1.0, 60.0, 14.0)],
            _adapt_selexol),
        "rectisol": MethodSpec(
            "rectisol", "Rectisol (metanol)", "experimental", "physical",
            [P("P_bar", "Pressão", "bar", 5.0, 80.0, 25.0),
             P("L_over_V", "Razão L/V", "", 0.5, 50.0, 5.0),
             P("N_stages", "Nº estágios", "", 1, 40, 10, 0),
             P("height_m", "Altura", "m", 1.0, 60.0, 14.0)],
            _adapt_rectisol, recommended=False),
        "psa": MethodSpec(
            "psa", "PSA", "experimental", "psa",
            [P("P_high_bar", "Pressão adsorção", "bar", 3.0, 50.0, 7.0),
             P("P_low_bar", "Pressão dessorção", "bar", 0.05, 2.0, 0.2),
             P("adsorbent", "Adsorvente", "", 0.0, 0.0, "Zeolite_13X", 0,
               choices=("Zeolite_13X", "ActivatedCarbon"))],
            _adapt_psa, recommended=False),
        "membrane": MethodSpec(
            "membrane", "Membrana (1 estágio)", "operational", "membrane",
            [P("P_feed_bar", "Pressão alimentação", "bar", 3.0, 60.0, 10.0),
             P("P_perm_bar", "Pressão permeado", "bar", 0.05, 5.0, 0.2),
             P("stage_cut", "Corte de estágio", "", 0.05, 0.95, 0.5, 3),
             P("material", "Material", "", 0.0, 0.0, "CelluloseAcetate", 0,
               choices=("CelluloseAcetate", "Polyimide", "Polysulfone", "Silica"))],
            _adapt_membrane),
        "membrane_multi": MethodSpec(
            "membrane_multi", "Membrana multi-estágio", "operational", "membrane",
            [P("P_feed_bar", "Pressão alimentação", "bar", 3.0, 60.0, 15.0),
             P("P_perm_bar", "Pressão permeado", "bar", 0.05, 5.0, 1.0),
             P("material", "Material", "", 0.0, 0.0, "Polyimide", 0,
               choices=("Polyimide", "CelluloseAcetate", "Polysulfone", "Silica"))],
            _adapt_membrane_multi),
    }


METHODS = _method_registry()


def available_methods() -> list[MethodSpec]:
    """Métodos disponíveis para comparação, na ordem de registro."""
    return list(METHODS.values())


def recommended_methods() -> list[str]:
    """Conjunto de métodos recomendados (operacionais e representativos)."""
    return [k for k, m in METHODS.items() if m.recommended]


# --------------------------------------------------------------------------- #
# Configuração persistente
# --------------------------------------------------------------------------- #
DEFAULT_WEIGHTS = {
    "purity_CH4": 0.25, "recovery_CH4": 0.25, "total_kW": 0.20,
    "specific_cost_usd_per_Nm3": 0.20, "water_m3_per_h": 0.10,
}

# Direção de cada métrica no ranking: True = "maior é melhor".
_BENEFIT = {
    "purity_CH4": True, "recovery_CH4": True, "CO2_removal": True,
    "H2S_removal": True, "global_efficiency_pct": True,
    "methane_loss": False, "total_kW": False, "elec_kW": False, "thermal_kW": False,
    "specific_kWh_per_Nm3": False, "water_m3_per_h": False,
    "solvent_flow_mols": False, "specific_cost_usd_per_Nm3": False,
    "opex_usd_yr": False,
}


@dataclass
class ComparisonConfig:
    """Configuração de comparação serializável (salvar/restaurar projeto)."""
    selected: list[str] = field(default_factory=lambda: list(recommended_methods()))
    params: dict = field(default_factory=dict)   # {method: {param: value}}
    mode: str = "standard"                        # "standard" | "optimized"
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    economics: dict = field(default_factory=lambda: dict(
        elec_price=0.10, thermal_price=0.04, water_price=0.5,
        solvent_price=1500.0, hours=8000.0))
    objective: str = "recovery_CH4"               # objetivo do modo otimizado
    feed: dict = field(default_factory=lambda: {"CH4": 0.47, "CO2": 0.53, "flow_mols": 100.0})
    T_K: float = 298.15
    P_feed_bar: float = 1.01325

    def params_for(self, method: str) -> dict:
        """Parâmetros de um método, mesclando defaults com overrides salvos."""
        spec = METHODS.get(method)
        if spec is None:
            return {}
        base = spec.default_params()
        base.update(self.params.get(method, {}))
        return base

    def to_dict(self) -> dict:
        return {"selected": list(self.selected), "params": dict(self.params),
                "mode": self.mode, "weights": dict(self.weights),
                "economics": dict(self.economics), "objective": self.objective,
                "feed": dict(self.feed), "T_K": self.T_K, "P_feed_bar": self.P_feed_bar}

    @classmethod
    def from_dict(cls, d: dict) -> ComparisonConfig:
        d = dict(d or {})
        return cls(
            selected=list(d.get("selected") or recommended_methods()),
            params=dict(d.get("params") or {}),
            mode=d.get("mode", "standard"),
            weights={**DEFAULT_WEIGHTS, **dict(d.get("weights") or {})},
            economics=d.get("economics") or ComparisonConfig().economics,
            objective=d.get("objective", "recovery_CH4"),
            feed=dict(d.get("feed") or {}),
            T_K=float(d.get("T_K", 298.15)),
            P_feed_bar=float(d.get("P_feed_bar", 1.01325)),
        )


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class ComparisonEngine:
    """Roda os métodos selecionados sob uma alimentação comum e padroniza.

    Parâmetros:
        feed: composição do biogás (dict espécie->fração molar, ex. CH4/CO2/H2S).
        flow: vazão de alimentação (mol/s).
        config: :class:`ComparisonConfig` (métodos, parâmetros, modo, premissas).
        T_K, P_feed_bar: condições da alimentação (herdadas da aba principal).

    Uso::
        eng = ComparisonEngine({"CH4":0.47,"CO2":0.52,"H2S":0.01}, flow=100.0,
                               config=ComparisonConfig(selected=["water","mea"]))
        rows = eng.run()
    """

    def __init__(self, feed: dict, flow: float = 100.0,
                 config: ComparisonConfig | None = None,
                 T_K: float = 298.15, P_feed_bar: float = 1.01325):
        self.feed = {k: float(v) for k, v in feed.items()}
        self.flow = float(flow)
        self.config = config or ComparisonConfig()
        self.T_K = float(T_K)
        self.P_feed_bar = float(P_feed_bar)

    # --------------------------- execução principal ------------------------ #
    def run(self, progress: Callable[[str, str, int, int], None] | None = None,
            should_stop: Callable[[], bool] | None = None) -> list[dict]:
        """Roda cada método selecionado; falha um não derruba os demais.

        ``progress(method_key, status, index, total)`` reporta andamento;
        ``status`` ∈ {"running","ok","failed"}. ``should_stop`` interrompe entre
        métodos (botão Stop da GUI).
        """
        selected = [m for m in self.config.selected if m in METHODS]
        rows: list[dict] = []
        n = len(selected)
        for i, key in enumerate(selected):
            if should_stop and should_stop():
                break
            if progress:
                progress(key, "running", i, n)
            spec = METHODS[key]
            params = self._resolved_params(key)
            try:
                raw = spec.adapter(self.feed, self.flow, params)
                row = self._standardize(key, spec, raw)
            except Exception as exc:  # falha isolada -- registra e segue
                row = self._failed_row(key, spec, str(exc))
                if progress:
                    progress(key, "failed", i, n)
                rows.append(row)
                continue
            rows.append(row)
            if progress:
                progress(key, "ok", i, n)
        self.rows = rows
        return rows

    def _resolved_params(self, key: str) -> dict:
        """Modo otimizado: busca em grade simples antes de rodar; senão, defaults."""
        params = self.config.params_for(key)
        if self.config.mode != "optimized":
            return params
        return self._optimize_params(key, params)

    def _optimize_params(self, key: str, base: dict) -> dict:
        """Heurística leve: varre a variável principal da tecnologia em poucos
        pontos e escolhe a de melhor objetivo (viável: purity_CH4 >= 95 quando
        aplicável). Reusa o mesmo adaptador -- sem novo código de processo."""
        spec = METHODS[key]
        grids = {
            "water": ("L_over_V", [40, 80, 120, 160]),
            "mea": ("L_over_V", [10, 20, 30, 40]),
            "dea": ("L_over_V", [10, 20, 30, 40]),
            "mdea": ("L_over_V", [10, 20, 30, 40]),
            "selexol": ("L_over_V", [40, 80, 120]),
            "rectisol": ("L_over_V", [40, 80, 120]),
            "psa": ("P_high_bar", [5, 7, 10, 15]),
            "membrane": ("P_feed_bar", [8, 12, 18, 25]),
            "membrane_multi": ("P_feed_bar", [10, 15, 20, 30]),
        }
        if key not in grids:
            return base
        var, vals = grids[key]
        obj = self.config.objective
        best, best_params = None, base
        for v in vals:
            p = dict(base)
            p[var] = float(v)
            try:
                raw = spec.adapter(self.feed, self.flow, p)
                row = self._standardize(key, spec, raw)
            except Exception:
                continue
            if not row.get("converged"):
                continue
            # viabilidade: pureza mínima quando a métrica existe
            pur = row.get("purity_CH4")
            if pur is not None and pur < 95.0 and obj in ("recovery_CH4", "total_kW"):
                continue
            val = row.get(obj)
            if val is None:
                continue
            if best is None or self._better(val, best, obj):
                best, best_params = val, p
        return best_params

    @staticmethod
    def _better(val, best, obj):
        return val > best if _BENEFIT.get(obj, False) else val < best

    # ----------------------------- padronização ---------------------------- #
    def _standardize(self, key: str, spec: MethodSpec, m: dict) -> dict:
        """Constrói a linha padronizada (KPIs/energia/economia uniformes)."""
        flow = self.flow
        recovery = m.get("recovery_CH4", 0.0) or 0.0
        product_mols = m.get("product_flow_mols", flow * recovery / 100.0)
        bio_nm3h = product_mols * 0.0224 * 3600
        # energia elétrica vs térmica
        elec = (m.get("compression_kW", 0.0) or 0.0) + (m.get("pumping_kW", 0.0) or 0.0)
        thermal = m.get("regeneration_kW", 0.0) or 0.0
        total_kw = m.get("total_kW", elec + thermal)
        spec_kwh = m.get("specific_kWh_per_Nm3")
        if spec_kwh is None and bio_nm3h > 0:
            spec_kwh = total_kw / bio_nm3h
        # consumos
        water_m3h = m.get("water_m3_per_h")
        if water_m3h is None and key == "water":
            water_m3h = (m.get("solvent_flow_mols", 0.0) or 0.0) * 0.018 / 1000.0 * 3600.0
        solvent_mols = m.get("solvent_flow_mols")
        # consumo de solvente (kg/h) para aminas
        solvent_kg_h = 0.0
        if solvent_mols and spec.category == "amine":
            amine = m.get("amine", "MEA")
            mm = get(amine).MM if amine in ("MEA", "DEA", "MDEA") else 0.105
            solvent_kg_h = solvent_mols * mm * 3600.0
        # economia (premissas editáveis)
        econ = self._economics(total_kw, bio_nm3h, water_m3h or 0.0, solvent_kg_h, thermal)
        # qualidade do gás tratado (KPIs)
        lhv = m.get("treated_LHV_MJ_per_Nm3")
        hhv = m.get("treated_HHV_MJ_per_Nm3")
        wobbe = m.get("treated_wobbe_MJ_per_Nm3")
        if lhv is None:  # PSA/membrana: estima a partir de pureza/residual CO2
            pur = (m.get("purity_CH4", 0.0) or 0.0) / 100.0
            res = (m.get("residual_CO2", (1.0 - pur) * 100.0) or 0.0) / 100.0
            tg = {"CH4": max(pur, 1e-6), "CO2": max(res, 0.0)}
            tg = normalize_mixture(tg)
            tp = mixture_properties_general(tg, T=298.15, P=1.01325e5)
            lhv = round(tp.LHV_MJ_per_Nm3, 2)
            hhv = round(tp.HHV_MJ_per_Nm3, 2)
            wobbe = round(tp.wobbe_index_MJ_per_Nm3, 2)
        # eficiência global = recuperação * pureza
        eff = (recovery / 100.0) * ((m.get("purity_CH4", 0.0) or 0.0) / 100.0) * 100.0
        return {
            "method": key,
            "method_label": spec.label,
            "status": spec.status,
            "converged": bool(m.get("converged", True)),
            "message": m.get("message", ""),
            "mass_balance_error": m.get("mass_balance_error"),
            "gpdc_extrapolated": m.get("gpdc_extrapolated"),
            "purity_CH4": m.get("purity_CH4"),
            "recovery_CH4": recovery,
            "CO2_removal": m.get("CO2_removal"),
            "H2S_removal": m.get("H2S_removal"),
            "methane_loss": m.get("methane_loss"),
            "product_flow_nm3h": round(bio_nm3h, 2),
            "water_m3_per_h": round(water_m3h, 2) if water_m3h is not None else None,
            "solvent_flow_mols": solvent_mols,
            "elec_kW": round(elec, 2),
            "thermal_kW": round(thermal, 2),
            "total_kW": round(total_kw, 2),
            "specific_kWh_per_Nm3": round(spec_kwh, 3) if spec_kwh is not None else None,
            "operating_pressure_bar": m.get("operating_pressure_bar"),
            "column_height_m": m.get("height_m"),
            "column_diameter_m": m.get("diameter_m"),
            "global_efficiency_pct": round(eff, 2),
            "opex_usd_yr": econ["opex_usd_yr"],
            "specific_cost_usd_per_Nm3": econ["specific_cost_usd_per_Nm3"],
            "treated_LHV_MJ_per_Nm3": lhv,
            "treated_HHV_MJ_per_Nm3": hhv,
            "treated_wobbe_MJ_per_Nm3": wobbe,
            "treated_H2S_ppm": m.get("treated_H2S_ppm"),
            "_raw": m,
        }

    def _failed_row(self, key: str, spec: MethodSpec, msg: str) -> dict:
        row = {col: None for col, *_ in COLUMNS}
        row.update({
            "method": key, "method_label": spec.label, "status": spec.status,
            "converged": False, "message": msg[:120],
        })
        return row

    def _economics(self, total_kw, bio_nm3h, water_m3h, solvent_kg_h, thermal_kw):
        e = self.config.economics
        hours = e.get("hours", 8000.0)
        opex = (total_kw * hours * e.get("elec_price", 0.10)
                + thermal_kw * hours * e.get("thermal_price", 0.04)
                + water_m3h * hours * e.get("water_price", 0.5)
                + solvent_kg_h / 1000.0 * hours * e.get("solvent_price", 1500.0))
        nm3_yr = bio_nm3h * hours
        spec = opex / nm3_yr if nm3_yr > 0 else 0.0
        return {"opex_usd_yr": round(opex, 0),
                "specific_cost_usd_per_Nm3": round(spec, 4)}

    # ------------------------------- ranking ------------------------------- #
    def best_by(self, rows: list[dict] | None, criterion: str) -> dict | None:
        """Melhor método segundo um critério (maximiza benefícios, minimiza custos)."""
        rows = rows or self.rows
        ok = [r for r in rows if r.get("converged") and r.get(criterion) is not None]
        if not ok:
            return None
        return max(ok, key=lambda r: r[criterion]) if _BENEFIT.get(criterion, False) \
            else min(ok, key=lambda r: r[criterion])

    def weighted_score(self, rows: list[dict] | None,
                       weights: dict | None = None) -> list[dict]:
        """Ranking multi-critério: normaliza cada métrica em [0,1] (direção
        benefício), pondera e soma. Devolve as linhas ordenadas por score decresc."""
        rows = rows or self.rows
        weights = weights or self.config.weights
        # normalização min-max por métrica
        norm = {}
        for crit in weights:
            vals = [r.get(crit) for r in rows if r.get("converged") and r.get(crit) is not None]
            if not vals:
                continue
            lo, hi = min(vals), max(vals)
            norm[crit] = (lo, hi)
        scored = []
        for r in rows:
            if not r.get("converged"):
                r = dict(r)
                r["score"] = None
                scored.append(r)
                continue
            s = 0.0
            for crit, w in weights.items():
                v = r.get(crit)
                if v is None or crit not in norm:
                    continue
                lo, hi = norm[crit]
                if hi == lo:
                    nv = 1.0
                else:
                    nv = (v - lo) / (hi - lo)
                    if not _BENEFIT.get(crit, False):
                        nv = 1.0 - nv
                s += w * nv
            r = dict(r)
            r["score"] = round(s, 4)
            scored.append(r)
        scored.sort(key=lambda r: (r.get("score") is None, -(r.get("score") or 0)))
        return scored

    # ------------------------------- export -------------------------------- #
    def report(self, rows: list[dict] | None) -> dict:
        """Dict estruturado completo (cabeçalho + tabela + KPIs + ranking)."""
        rows = rows or self.rows
        return {
            "title": "BioGasSim -- Method Comparison",
            "feed": {k: v for k, v in self.feed.items()},
            "flow_mols": self.flow,
            "T_K": self.T_K,
            "P_feed_bar": self.P_feed_bar,
            "thermodynamic_model": "Peng-Robinson",
            "mode": self.config.mode,
            "selected": list(self.config.selected),
            "params": self.config.params,
            "economics": self.config.economics,
            "columns": [c[0] for c in COLUMNS],
            "rows": [_public(r) for r in rows],
            "best": {crit: (_b := self.best_by(rows, crit)) and _b["method_label"]
                    for crit in ("purity_CH4", "recovery_CH4", "total_kW",
                                  "specific_cost_usd_per_Nm3", "CO2_removal")},
            "ranking": [_public(r) for r in self.weighted_score(rows)],
        }


def _public(row: dict) -> dict:
    """Cópia da linha sem campos privados (``_raw``)."""
    return {k: v for k, v in row.items() if not k.startswith("_")}


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def export_comparison(report: dict, path: str) -> str:
    """Exporta o relatório de comparação. Formato pela extensão (.csv/.json/.html/.xlsx/.pdf)."""
    import os

    from .Export import export_csv, export_excel, export_json
    rows = report["rows"]
    ext = os.path.splitext(path)[1].lower()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if ext == ".json":
        export_json(report, path)
    elif ext == ".csv":
        export_csv(rows, path)
    elif ext == ".html":
        _export_html_report(report, path)
    elif ext in (".xlsx", ".xls"):
        try:
            export_excel({"comparison": rows, "ranking": report.get("ranking", [])}, path)
        except Exception:
            export_csv(rows, os.path.splitext(path)[0] + ".csv")
    elif ext == ".pdf":
        from .Export import export_pdf_stub
        export_pdf_stub(report, path)
        export_json(report, os.path.splitext(path)[0] + ".json")
    else:
        export_json(report, path)
    return path


def _export_html_report(report: dict, path) -> None:
    """Relatório HTML com cabeçalho (feed/condições) + tabela + ranking."""
    from pathlib import Path
    f = report["feed"]
    feed_lines = "".join(
        f"<tr><td>{s}</td><td>{v*100:.3f} %</td></tr>" for s, v in f.items())
    cols = [c for c, *_ in COLUMNS]
    head = "".join(f"<th>{c}</th>" for c in cols)
    def fmt(v):
        return "" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v))
    body = "".join(
        "<tr>" + "".join(f"<td>{fmt(r.get(c))}</td>" for c in cols) + "</tr>"
        for r in report["rows"])
    rank = "".join(
        f"<li>{r.get('method_label')}: score {r.get('score')}</li>"
        for r in report.get("ranking", []))
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
    <title>{report['title']}</title>
    <style>body{{font-family:sans-serif}} table{{border-collapse:collapse}}
    td,th{{border:1px solid #999;padding:4px}} .ok{{color:#060}} .fail{{color:#b00}}</style>
    </head><body><h1>{report['title']}</h1>
    <h2>Condições de alimentação (herdadas)</h2>
    <table><tr><th>Espécie</th><th>Fração</th></tr>{feed_lines}</table>
    <p>Vazão: {report['flow_mols']} mol/s | T: {report['T_K']-273.15:.1f} °C |
    P: {report['P_feed_bar']} bar | Modelo: {report['thermodynamic_model']} |
    Modo: {report['mode']}</p>
    <h2>Tabela comparativa</h2><table><thead><tr>{head}</tr></thead>
    <tbody>{body}</tbody></table>
    <h2>Ranking (ponderado)</h2><ol>{rank}</ol>
    </body></html>"""
    Path(path).write_text(html, encoding="utf-8")


__all__ = [
    "ComparisonEngine", "ComparisonConfig", "MethodSpec", "ParamSpec",
    "METHODS", "COLUMNS", "DEFAULT_WEIGHTS",
    "available_methods", "recommended_methods",
    "export_comparison",
]
