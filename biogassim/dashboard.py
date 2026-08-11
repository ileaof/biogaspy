"""Dashboard de resultados -- formatação textual das métricas de upgrading.

Produz o bloco de saída no estilo do requisito (feed / upgraded / performance /
safety), reusável pelo CLI (``run``, ``report``) e exportável. Opera sobre o
dict de métricas devolvido por :func:`biogassim.cases.run_case`.
"""
from __future__ import annotations

from . import safety

_SEP = "-" * 52


def _pct(frac: float | None) -> str:
    if frac is None:
        return "  -"
    return f"{float(frac) * 100:6.2f} %" if float(frac) <= 1.0 else f"{float(frac):6.2f} %"


def _pct100(val: float | None) -> str:
    if val is None:
        return "  -"
    return f"{float(val):6.2f} %"


def format_dashboard(m: dict) -> str:
    """Bloco de resultados no formato feed / upgraded / performance / safety."""
    lines: list[str] = []

    # ---- FEED GAS ----
    lines.append(_SEP)
    lines.append("FEED GAS")
    lines.append(_SEP)
    feed = {s: m.get(f"x_{s}") for s in ("CH4", "CO2", "H2S", "N2", "NH3")
            if m.get(f"x_{s}") is not None}
    for s, v in feed.items():
        lines.append(f"{s:<8}{_pct(v)}")

    # ---- UPGRADED GAS ----
    lines.append(_SEP)
    lines.append("UPGRADED GAS")
    lines.append(_SEP)
    lines.append(f"{'CH4':<8}{_pct100(m.get('treated_CH4_pct') or _rescale(m, 'CH4'))}")
    lines.append(f"{'CO2':<8}{_pct100(m.get('treated_CO2_pct') or _rescale(m, 'CO2'))}")
    if m.get("treated_H2S_pct") is not None:
        h2s = float(m["treated_H2S_pct"])
        lines.append(f"{'H2S':<8}{h2s:6.4f} %  ({float(m.get('treated_H2S_ppm', 0)):,.1f} ppm)")

    # ---- PERFORMANCE ----
    lines.append(_SEP)
    lines.append("PERFORMANCE")
    lines.append(_SEP)
    lines.append(f"{'CH4 Recovery':<22}{_pct100(m.get('recovery_CH4'))}")
    lines.append(f"{'CO2 Removal':<22}{_pct100(m.get('CO2_removal'))}")
    if m.get("H2S_removal") is not None:
        lines.append(f"{'H2S Removal':<22}{_pct100(m.get('H2S_removal'))}")
    if m.get("water_m3_per_h") is not None:
        kg = float(m["water_m3_per_h"]) * 1000.0
        lines.append(f"{'Water Consumption':<22}{float(m['water_m3_per_h']):7.1f} m3/h ({kg:.0f} kg/h)")
    if m.get("specific_kWh_per_Nm3") is not None:
        lines.append(f"{'Energy Consumption':<22}{float(m['specific_kWh_per_Nm3']):7.3f} kWh/Nm3")

    # ---- GAS QUALITY ----
    lines.append(_SEP)
    lines.append("GAS QUALITY (treated)")
    lines.append(_SEP)
    for k, lbl in (("treated_LHV_MJ_per_Nm3", "LHV"),
                   ("treated_HHV_MJ_per_Nm3", "HHV"),
                   ("treated_wobbe_MJ_per_Nm3", "Wobbe Index"),
                   ("treated_density_kg_per_Nm3", "Density"),
                   ("treated_specific_gravity", "Relative Density")):
        if m.get(k) is not None:
            lines.append(f"{lbl:<22}{float(m[k]):8.3f}")

    # ---- SAFETY (H2S) ----
    feed_h2s = m.get("x_H2S")
    if safety.h2s_present(feed_h2s):
        lines.append(_SEP)
        lines.append("SAFETY -- H2S")
        lines.append(_SEP)
        for w in safety.h2s_warnings(feed_h2s, m.get("treated_H2S_ppm", 0.0),
                                     m.get("liquid_H2S_loading_mol_per_mol")):
            lines.append(w)
        suit = safety.engine_suitable(m.get("treated_H2S_ppm", 0.0))
        lines.append(f"  Engine-suitable (H2S <= {safety.max_h2s_treated_ppm():.1f} ppm): "
                     f"{'YES' if suit else 'NO'}")
    lines.append(_SEP)
    return "\n".join(lines)


def _rescale(m, s) -> float | None:
    """Cai para purity_CH4 se treated_CH4_pct nao existir (compat binario)."""
    if s == "CH4":
        return m.get("purity_CH4")
    if s == "CO2":
        return m.get("residual_CO2")
    return None


__all__ = ["format_dashboard"]
