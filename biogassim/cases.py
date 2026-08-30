"""Casos de simulação: modelo, I/O em JSON, validação e execução paramétrica.

Um *caso* descreve uma simulação de upgrading de biogás CH4-CO2: a composição e
vazão da alimentação, a tecnologia e as condições operacionais. Este módulo é a
espinha dorsal da CLI (``new``/``run``/``set``/``sweep``): cria/carrega/valida
casos, executa-os com composição **variável** e gera estudos paramétricos ao
varrer a fração de CH4.

Milestone 1 cobre as tecnologias de absorção binária CH4-CO2 ``water`` e ``mea``.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from .Examples import MEA, WaterScrubbing
from .Optimization import Economics
from .Properties import (
    mixture_properties_general,
    normalize_composition,
    normalize_mixture,
)

TECHNOLOGIES = {"water": WaterScrubbing, "mea": MEA}

DEFAULT_OPERATING = {
    "water": {"P_bar": 20.0, "L_over_V": 100.0, "N_stages": 12, "height_m": 15.0},
    "mea": {"P_bar": 2.0, "L_over_V": 20.0, "N_stages": 8, "height_m": 12.0},
}


@dataclass
class Case:
    """Um caso de simulação CH4-CO2."""
    name: str = "case"
    technology: str = "water"
    feed: dict = field(default_factory=lambda: {"CH4": 0.47, "CO2": 0.53,
                                                "flow_mols": 100.0})
    operating: dict = field(default_factory=dict)
    # config de comparação de métodos (opcional; ver biogassim.comparison)
    comparison: dict | None = None


def _valid_tech(t: str) -> str:
    t = str(t).lower()
    if t not in TECHNOLOGIES:
        raise ValueError(f"Tecnologia '{t}' inválida. Use: {', '.join(TECHNOLOGIES)}.")
    return t


def default_case(name: str = "case", technology: str = "water") -> Case:
    technology = _valid_tech(technology)
    return Case(name=name, technology=technology,
                feed={"CH4": 0.47, "CO2": 0.53, "flow_mols": 100.0},
                operating=dict(DEFAULT_OPERATING[technology]))


def validate_case(case: Case) -> Case:
    """Normaliza a composição e valida tecnologia/vazão/operacionais (in-place).

    Aceita feed binário CH4/CO2 (com fração complementar automática) ou
    multi-espécie (CH4/CO2/N2/H2S/...), normalizado para frações molares.
    """
    case.technology = _valid_tech(case.technology)
    flow = float(case.feed.get("flow_mols", 100.0))
    if flow <= 0:
        raise ValueError("flow_mols deve ser > 0.")
    gas = {k: float(v) for k, v in case.feed.items() if k != "flow_mols"}
    if not gas:
        gas = {"CH4": 0.47, "CO2": 0.53}
    if set(gas) <= {"CH4", "CO2"}:            # binário: completa a fração faltante
        x_ch4, x_co2 = normalize_composition(gas.get("CH4"), gas.get("CO2"))
        gas = {"CH4": x_ch4, "CO2": x_co2}
    else:                                     # multi-espécie: normaliza tudo
        gas = normalize_mixture(gas)
    case.feed = {**gas, "flow_mols": flow}
    op = {**DEFAULT_OPERATING[case.technology], **(case.operating or {})}
    if (op["N_stages"] < 1 or op["P_bar"] <= 0 or op["height_m"] <= 0
            or op["L_over_V"] <= 0):
        raise ValueError("Parâmetros operacionais devem ser positivos.")
    case.operating = op
    return case


def save_case(case: Case, path: str) -> str:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(case), f, indent=2, ensure_ascii=False)
    return path


def load_case(path: str) -> Case:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    case = Case(name=data.get("name", "case"),
                technology=data.get("technology", "water"),
                feed=dict(data.get("feed", {})),
                operating=dict(data.get("operating", {})),
                comparison=data.get("comparison"))
    return validate_case(case)


def new_project(path: str, name: str | None = None, technology: str = "water") -> str:
    """Cria um diretório de projeto com ``case.json`` padrão e pasta ``results/``."""
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, "results"), exist_ok=True)
    name = name or os.path.basename(os.path.normpath(path)) or "case"
    case_path = os.path.join(path, "case.json")
    save_case(default_case(name=name, technology=technology), case_path)
    return case_path


def _treated_gas_quality(m: dict, result, P_bar: float) -> dict:
    """Composição e propriedades do gás purificado (topo da coluna) + carregamento
    líquido de H2S.

    Reporta, a partir do resultado do absorvedor:
      * frações molares do gás tratado (excluindo H2O) -- CH4, CO2, H2S, ...;
      * concentração de H2S no gás tratado (mol% e ppm);
      * propriedades do gás tratado: LHV, HHV, Wobbe, densidade, densidade
        relativa, Z (Peng-Robinson multicomponente);
      * carregamento de H2S no líquido: fração molar x_H2S e mol H2S / mol água.
    """
    if result is None or result.gas_out is None:
        return m
    sp = list(result.gas_out.species)
    y = result.gas_out.z
    # composição do gás tratado sem H2O (renormalizada) -- é o que se entrega
    treated = {s: float(y[i]) for i, s in enumerate(sp) if s != "H2O" and float(y[i]) > 0.0}
    if treated:
        tot = sum(treated.values())
        treated = {s: v / tot for s, v in treated.items()}
        tp = mixture_properties_general(treated, T=298.15, P=P_bar * 1e5)
        m["treated_CH4_pct"] = round(treated.get("CH4", 0.0) * 100, 3)
        m["treated_CO2_pct"] = round(treated.get("CO2", 0.0) * 100, 3)
        h2s_t = treated.get("H2S", 0.0)
        m["treated_H2S_pct"] = round(h2s_t * 100, 4)
        m["treated_H2S_ppm"] = round(h2s_t * 1e6, 1)
        m["treated_LHV_MJ_per_Nm3"] = round(tp.LHV_MJ_per_Nm3, 2)
        m["treated_HHV_MJ_per_Nm3"] = round(tp.HHV_MJ_per_Nm3, 2)
        m["treated_wobbe_MJ_per_Nm3"] = round(tp.wobbe_index_MJ_per_Nm3, 2)
        m["treated_density_kg_per_Nm3"] = round(tp.density_normal, 4)
        m["treated_specific_gravity"] = round(tp.specific_gravity, 4)
        m["treated_Z"] = round(tp.Z, 5)
        # umidade do gás tratado ANTES do secador: conteúdo em mg/Nm³ (base
        # úmida) e ponto de orvalho de H2O a P de entrega. Limites de motor/
        # gasoduto: 60-200 mg/Nm³ -> exige secador (leito de tam) (auditoria
        # §19: o ponto de orvalho é condição de entrega, não opcional).
        if "H2O" in sp:
            y_w = float(y[sp.index("H2O")])
            if y_w > 1e-12:
                from .Properties.Moisture import dew_point_H2O, water_content_mg_per_nm3
                m["treated_H2O_mg_per_Nm3"] = round(water_content_mg_per_nm3(y_w), 1)
                m["treated_dew_point_C"] = round(dew_point_H2O(y_w, P_bar * 1e5)
                                                 - 273.15, 1)
    # carregamento de H2S na fase líquida (saída de fundo)
    if result.liquid_out is not None and "H2S" in sp and "H2O" in sp:
        xl = result.liquid_out.z
        i_h2s = sp.index("H2S")
        i_h2o = sp.index("H2O")
        x_h2s = float(xl[i_h2s])
        x_h2o = max(float(xl[i_h2o]), 1e-12)
        m["liquid_H2S_molfrac"] = round(x_h2s, 6)
        m["liquid_H2S_loading_mol_per_mol"] = round(x_h2s / x_h2o, 5)
    return m


def run_case(case: Case, save: bool = False, outdir: str | None = None) -> dict:
    """Executa um caso (composição variável) e devolve métricas completas."""
    case = validate_case(case)
    gas = {k: v for k, v in case.feed.items() if k != "flow_mols"}
    x_ch4, x_co2 = gas.get("CH4", 0.0), gas.get("CO2", 0.0)
    op = case.operating
    mod = TECHNOLOGIES[case.technology]

    # água absorve multi-gás (CO2, H2S, NH3, ...); MEA (reativo) fica em CH4/CO2
    # (absorção reativa de H2S/NH3 em amina = roadmap).
    if case.technology == "water":
        composition = dict(gas)
    else:
        denom = x_ch4 + x_co2
        composition = ({"CH4": x_ch4 / denom, "CO2": x_co2 / denom}
                       if denom > 0 else {"CH4": x_ch4, "CO2": x_co2})

    regen = bool((case.operating or {}).get("regen", case.technology == "water"))
    out = mod.run_case(P_bar=op["P_bar"], L_over_V=op["L_over_V"],
                       N_stages=int(op["N_stages"]), height=op["height_m"],
                       flow=case.feed["flow_mols"], save=False,
                       composition=composition,
                       **({"regen": regen} if case.technology == "water" else {}))
    m = dict(out["metrics"])

    # contexto de composição + propriedades do gás de alimentação (multi-espécie)
    props = mixture_properties_general(gas, T=298.15, P=op["P_bar"] * 1e5)
    m["x_CH4"] = round(x_ch4, 4)
    m["x_CO2"] = round(x_co2, 4)
    if "H2S" in gas:
        m["x_H2S"] = round(gas["H2S"], 5)
    m["feed_LHV_MJ_per_Nm3"] = round(props.LHV_MJ_per_Nm3, 2)
    m["feed_wobbe_MJ_per_Nm3"] = round(props.wobbe_index_MJ_per_Nm3, 2)

    # ---- qualidade do gás purificado (treated) + carregamento líquido de H2S ---- #
    # o absorvedor resolve todas as espécies; reportamos a composição real do
    # gás de topo (excluindo H2O) e suas propriedades (LHV/HHV/Wobbe/densidade/SG).
    result = out["result"]
    m = _treated_gas_quality(m, result, op["P_bar"])

    # consumo de solvente / água: circulação (L/V) ≠ consumo (makeup/purge)
    solvent_flow = op["L_over_V"] * case.feed["flow_mols"]           # mol/s
    m["solvent_flow_mols"] = round(solvent_flow, 2)
    if case.technology == "water":
        m["water_circulation_m3_per_h"] = round(solvent_flow * 0.018 / 1000.0 * 3600.0, 2)
        # com regeneração, o consumo real de água fresca é o makeup (purge);
        # sem regeneração a água seria consumida toda (modelo once-through)
        if regen:
            m["water_m3_per_h"] = round(m.get("water_m3_per_h",
                                              0.02 * solvent_flow * 0.018 / 1000.0 * 3600.0), 2)
        else:
            m["water_m3_per_h"] = round(solvent_flow * 0.018 / 1000.0 * 3600.0, 2)

    # economia (água cobrada é o CONSUMO/makeup, nunca a circulação)
    bio_nm3h = result.gas_out.flow * 0.0224 * 3600 if result.gas_out else 0.0
    co2_kg_h = case.feed["flow_mols"] * x_co2 * (m.get("CO2_removal", 0) / 100.0) * 0.044 * 3600
    econ = Economics.from_process(total_kw=m.get("total_kW", 0.0),
                                  biometane_nm3h=bio_nm3h,
                                  water_m3h=m.get("water_m3_per_h", 0.0) or 0.0,
                                  co2_avoided_kg_h=co2_kg_h)
    m["opex_usd_yr"] = round(econ.opex_usd_yr, 0)
    m["specific_cost_usd_per_Nm3"] = round(econ.specific_cost_usd_per_nm3, 4)
    m["co2_avoided_t_per_yr"] = round(econ.co2_avoided_t_per_yr, 1)

    if save and outdir:
        from .Export import export_json
        os.makedirs(outdir, exist_ok=True)
        export_json(m, os.path.join(outdir, f"{case.name}_results.json"))
    return {"result": result, "metrics": m}


# --------------------------- estudo paramétrico ---------------------------- #
_SWEEP_KEYS = ["purity_CH4", "recovery_CH4", "CO2_removal", "methane_loss",
               "solvent_flow_mols", "water_m3_per_h", "total_kW",
               "specific_kWh_per_Nm3", "diameter_m", "height_m",
               "pressure_drop_Pa", "flooding_pct", "specific_cost_usd_per_Nm3",
               "converged"]
_H2S_SWEEP_KEYS = _SWEEP_KEYS + ["H2S_removal", "treated_H2S_pct", "treated_H2S_ppm",
                                 "treated_wobbe_MJ_per_Nm3", "liquid_H2S_loading_mol_per_mol"]


def frange(start: float, stop: float, step: float) -> list[float]:
    """Intervalo inclusivo de floats (start:stop:step), robusto a erro de ponto flutuante."""
    if step <= 0:
        raise ValueError("step deve ser > 0.")
    n = int(round((stop - start) / step))
    return [round(start + i * step, 10) for i in range(n + 1)]


def sweep_composition(technology: str = "water", ch4_values=None,
                      operating: dict | None = None, flow: float = 100.0,
                      name: str = "sweep") -> list[dict]:
    """Varre a fração de CH4 e coleta todas as métricas de desempenho por composição."""
    technology = _valid_tech(technology)
    if ch4_values is None:
        ch4_values = frange(0.20, 0.95, 0.05)
    rows = []
    for x in ch4_values:
        case = Case(name=name, technology=technology,
                    feed={"CH4": float(x), "CO2": 1.0 - float(x), "flow_mols": flow},
                    operating=dict(operating) if operating else {})
        row = {"feed_CH4_pct": round(float(x) * 100, 1)}
        try:
            m = run_case(case)["metrics"]
            row.update({k: m.get(k) for k in _SWEEP_KEYS})
        except Exception as exc:                     # composição inviável -> reporta
            row.update({k: None for k in _SWEEP_KEYS})
            row["converged"] = False
            row["error"] = str(exc)[:80]
        rows.append(row)
    return rows


def sweep_h2s(technology: str = "water", h2s_values=None,
               ch4_co2_ratio: float = 0.47, operating: dict | None = None,
               flow: float = 100.0, name: str = "sweep_h2s") -> list[dict]:
    """Varre a fração de H2S no feed (0..5 mol% típico) mantendo a razão
    CH4:CO2 constante.

    ``ch4_co2_ratio`` é a fração de CH4 *dentro da parcela (1 - H2S)* (ex.: 0.47
    significa CH4 = 47% e CO2 = 53% da parte não-H2S). Para cada H2S = h::

        CH4 = (1 - h) * r,  CO2 = (1 - h) * (1 - r),  H2S = h

    Coleta remoção/efficiência de H2S, recuperação de CH4, remoção de CO2,
    consumo de água/energia, altura e qualidade do gás tratado (§13).
    """
    technology = _valid_tech(technology)
    if technology != "water":
        raise ValueError("sweep_h2s disponível apenas para 'water' "
                         "(absorção reativa de H2S em amina = roadmap).")
    if h2s_values is None:
        h2s_values = frange(0.0, 0.05, 0.005)
    r = float(ch4_co2_ratio)
    rows = []
    for h in h2s_values:
        h = max(min(float(h), 1.0), 0.0)
        feed = {"CH4": (1.0 - h) * r, "CO2": (1.0 - h) * (1.0 - r),
                "H2S": h, "flow_mols": flow}
        case = Case(name=name, technology=technology, feed=feed,
                    operating=dict(operating) if operating else {})
        row = {"feed_H2S_pct": round(h * 100, 3)}
        try:
            m = run_case(case)["metrics"]
            row.update({k: m.get(k) for k in _H2S_SWEEP_KEYS})
        except Exception as exc:
            row.update({k: None for k in _H2S_SWEEP_KEYS})
            row["converged"] = False
            row["error"] = str(exc)[:80]
        rows.append(row)
    return rows


__all__ = [
    "Case", "TECHNOLOGIES", "DEFAULT_OPERATING",
    "default_case", "validate_case", "save_case", "load_case", "new_project",
    "run_case", "sweep_composition", "sweep_h2s", "frange",
]
