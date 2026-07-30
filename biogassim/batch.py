"""Simulação em lote: avalia muitas composições de alimentação de uma vez.

Lê um arquivo de composições (CSV) — uma linha por alimentação, colunas com os
nomes das espécies (CH4, CO2, N2, ...) — e computa, para cada uma, as
propriedades da mistura (massa molar, Z, densidade, LHV/HHV, Índice de Wobbe,
densidade relativa). Colunas de metadados opcionais: ``name``, ``T_K``,
``P_bar``, ``basis`` (mole/mass/volume/...), ``technology``.

Se uma tecnologia de upgrading for indicada (``technology`` por linha ou o
argumento global), roda também a simulação de absorção sobre a **subcomposição
CH4/CO2** (renormalizada) e anexa pureza/recuperação/remoção/energia. Espécies
não-CH4/CO2 (N2, O2, H2, Ar, ...) ainda não são absorvidas pelo solver — entram
como diluentes e são reportadas nas propriedades, mas não no balanço da coluna
(ver ROADMAP: absorção multicomponente).
"""
from __future__ import annotations

from .Properties import DEFAULT_GASES, mixture_properties_general, to_mole_fractions
from .Properties.components import all_components

_KNOWN_SPECIES = set(all_components())
_META_COLS = {"name", "t_k", "p_bar", "basis", "technology", "flow_mols"}


def _species_columns(columns) -> list[str]:
    return [c for c in columns if c in _KNOWN_SPECIES]


def _cell(row, key, default=None):
    """Valor de uma coluna opcional, tolerante a ausência/NaN."""
    if key not in row:
        return default
    v = row[key]
    try:
        import math
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return default
    except TypeError:
        pass
    return v


def run_batch(feeds, T: float = 298.15, P_bar: float = 1.01325, basis: str = "mole",
              technology: str | None = None, flow: float = 100.0) -> list[dict]:
    """Avalia todas as composições de ``feeds`` (caminho CSV ou lista de dicts)."""
    import pandas as pd

    df = pd.read_csv(feeds) if isinstance(feeds, str) else pd.DataFrame(list(feeds))
    df.columns = [str(c).strip() for c in df.columns]
    lower = {c.lower(): c for c in df.columns}                 # metadados case-insensitive
    species_cols = _species_columns(df.columns)
    if not species_cols:
        raise ValueError(
            f"Nenhuma coluna de espécie reconhecida em {list(df.columns)}. "
            f"Use colunas como {DEFAULT_GASES}."
        )

    rows = []
    for i, r in df.iterrows():
        rd = r.to_dict()
        name = _cell(rd, lower.get("name", "name"), f"feed_{i + 1}")
        comp = {s: float(rd[s]) for s in species_cols
                if _cell(rd, s) is not None and float(rd[s]) != 0.0}
        out = {"name": str(name)}
        try:
            rT = float(_cell(rd, lower.get("t_k", "T_K"), T))
            rP = float(_cell(rd, lower.get("p_bar", "P_bar"), P_bar))
            rb = str(_cell(rd, lower.get("basis", "basis"), basis))
            x = to_mole_fractions(comp, rb)
            props = mixture_properties_general(comp, T=rT, P=rP * 1e5, basis=rb)
            out.update({f"x_{s}": round(x.get(s, 0.0), 4) for s in species_cols})
            out.update({
                "MM_g_per_mol": round(props.molar_mass_gmol, 3),
                "Z": round(props.Z, 4),
                "density_kg_per_m3": round(props.density, 4),
                "LHV_MJ_per_Nm3": round(props.LHV_MJ_per_Nm3, 3),
                "HHV_MJ_per_Nm3": round(props.HHV_MJ_per_Nm3, 3),
                "wobbe_MJ_per_Nm3": round(props.wobbe_index_MJ_per_Nm3, 3),
                "specific_gravity": round(props.specific_gravity, 4),
            })
            tech = _cell(rd, lower.get("technology", "technology"), technology)
            if tech and "CH4" in x and "CO2" in x:
                out.update(_upgrade(x, tech, flow))
            out["status"] = "ok"
        except Exception as exc:                               # composição inviável
            out["status"] = f"erro: {str(exc)[:70]}"
        rows.append(out)

    # uniformiza as chaves (união preservando a ordem) p/ export CSV robusto
    allkeys: list[str] = []
    for r in rows:
        allkeys.extend(k for k in r if k not in allkeys)
    return [{k: r.get(k, "") for k in allkeys} for r in rows]


def _upgrade(x: dict, technology: str, flow: float) -> dict:
    """Roda o upgrading do feed. Água usa a composição completa (absorve H2S/NH3
    além de CO2); MEA usa a subcomposição CH4/CO2 (H2S reativo em amina = roadmap).
    """
    from . import cases
    if x.get("CH4", 0.0) + x.get("CO2", 0.0) <= 0:
        return {}
    if str(technology) == "water":
        feed = {**x, "flow_mols": flow}
    else:
        denom = x["CH4"] + x["CO2"]
        feed = {"CH4": x["CH4"] / denom, "CO2": x["CO2"] / denom, "flow_mols": flow}
    m = cases.run_case(cases.Case(name="batch", technology=str(technology), feed=feed))["metrics"]
    out = {
        "upg_purity_CH4": m.get("purity_CH4"),
        "upg_recovery_CH4": m.get("recovery_CH4"),
        "upg_CO2_removal": m.get("CO2_removal"),
        "upg_total_kW": m.get("total_kW"),
        "inert_pct": round((1.0 - x.get("CH4", 0.0) - x.get("CO2", 0.0)) * 100, 2),
    }
    for s in ("H2S", "NH3"):
        if f"{s}_removal" in m:
            out[f"upg_{s}_removal"] = m[f"{s}_removal"]
    return out


__all__ = ["run_batch"]
