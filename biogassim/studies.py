"""Estudos paramétricos multivariável (superfícies de resposta) e otimização.

Reusa o motor de casos (:func:`biogassim.cases.run_case`) para varrer qualquer
combinação de variáveis — **composição** (``CH4``) e/ou **operacionais**
(``P_bar``, ``L_over_V``, ``N_stages``, ``height_m``, ``flow_mols``) — coletando
o conjunto completo de métricas (pureza, recuperação, remoção de CO₂, perda de
metano, energia, dimensionamento, perda de carga, inundação, custo).

* :func:`sweep_1d` / :func:`sweep_2d` — geram tabelas / superfícies de resposta.
* :func:`optimize` — busca em grade a melhor condição sob restrições.
* :func:`plot_surface` — curvas (1-D) ou heatmap (2-D) para mapas de desempenho.
"""
from __future__ import annotations

from itertools import product

from . import cases

# Variáveis varríveis e onde entram no caso.
_FEED_VARS = {"CH4"}
_FLOW_VARS = {"flow", "flow_mols"}
_OP_VARS = {"P_bar", "T_C", "L_over_V", "N_stages", "height_m"}
VARIABLES = sorted(_FEED_VARS | {"flow_mols"} | _OP_VARS)

_STUDY_METRICS = [
    "purity_CH4", "recovery_CH4", "CO2_removal", "methane_loss",
    "total_kW", "specific_kWh_per_Nm3", "diameter_m", "height_m",
    "pressure_drop_Pa", "flooding_pct", "specific_cost_usd_per_Nm3",
    "solvent_flow_mols", "converged",
]

_OPS = {
    ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b, "<": lambda a, b: a < b, "==": lambda a, b: a == b,
}


def _run_point(technology: str, assignments: dict, flow: float,
               base_ch4: float = 0.47) -> dict:
    """Roda um ponto (uma combinação de variáveis) e devolve as métricas."""
    feed = {"CH4": base_ch4, "CO2": 1.0 - base_ch4, "flow_mols": flow}
    operating: dict = {}
    for var, val in assignments.items():
        if var in _FEED_VARS:
            feed["CH4"] = float(val)
            feed["CO2"] = 1.0 - float(val)
        elif var in _FLOW_VARS:
            feed["flow_mols"] = float(val)
        elif var in _OP_VARS:
            operating[var] = int(round(val)) if var == "N_stages" else float(val)
        else:
            raise ValueError(f"Variável desconhecida: '{var}'. Use {VARIABLES}.")
    case = cases.Case(name="study", technology=technology, feed=feed, operating=operating)
    try:
        m = cases.run_case(case)["metrics"]
        return {k: m.get(k) for k in _STUDY_METRICS}
    except Exception as exc:
        row = {k: None for k in _STUDY_METRICS}
        row["converged"] = False
        row["error"] = str(exc)[:70]
        return row


def sweep_1d(technology: str, var: str, values, flow: float = 100.0) -> list[dict]:
    """Varredura 1-D: métricas vs. ``var`` sobre ``values``."""
    technology = cases._valid_tech(technology)
    rows = []
    for v in values:
        row = {var: v}
        row.update(_run_point(technology, {var: v}, flow))
        rows.append(row)
    return rows


def sweep_2d(technology: str, var_x: str, values_x, var_y: str, values_y,
             flow: float = 100.0) -> list[dict]:
    """Superfície de resposta 2-D: métricas vs. ``var_x`` × ``var_y``."""
    technology = cases._valid_tech(technology)
    rows = []
    for vy in values_y:
        for vx in values_x:
            row = {var_x: vx, var_y: vy}
            row.update(_run_point(technology, {var_x: vx, var_y: vy}, flow))
            rows.append(row)
    return rows


def _feasible(metrics: dict, constraints: dict | None) -> bool:
    if not constraints:
        return True
    for key, spec in constraints.items():
        op, val = spec
        mv = metrics.get(key)
        if mv is None or op not in _OPS or not _OPS[op](mv, float(val)):
            return False
    return True


def optimize(technology: str, objective: str, variables: dict,
             constraints: dict | None = None, goal: str = "minimize",
             flow: float = 100.0) -> dict:
    """Busca em grade a condição ótima.

    ``variables``: ``{nome: (inicio, fim, passo)}`` (1 ou mais variáveis).
    ``objective``: métrica a otimizar (ex.: ``specific_kWh_per_Nm3``).
    ``constraints``: ``{metrica: (op, valor)}`` (ex.: ``{"purity_CH4": (">=", 96)}``).
    ``goal``: ``minimize`` ou ``maximize``.
    """
    technology = cases._valid_tech(technology)
    if not variables:
        raise ValueError("Informe ao menos uma variável.")
    names = list(variables)
    grids = {n: cases.frange(*variables[n]) for n in names}
    combos = [dict(zip(names, vals)) for vals in product(*(grids[n] for n in names))]
    minimize = goal.lower() != "maximize"

    rows, feasible = [], []
    for assign in combos:
        m = _run_point(technology, assign, flow)
        rows.append({**assign, **m})
        if not m.get("converged"):
            continue
        obj = m.get(objective)
        if obj is None:
            continue
        if _feasible(m, constraints):
            feasible.append((float(obj), assign, m))

    if not feasible:
        return {"best": None, "n_evaluated": len(rows), "n_feasible": 0,
                "message": "Nenhum ponto viável (verifique as restrições).", "rows": rows}
    feasible.sort(key=lambda t: t[0], reverse=not minimize)
    obj, assign, metrics = feasible[0]
    return {
        "best": {"variables": assign, "objective": objective, "goal": goal,
                 "value": obj, "metrics": metrics},
        "n_evaluated": len(rows), "n_feasible": len(feasible), "rows": rows,
    }


def plot_surface(rows: list[dict], var_x: str, metric: str, path: str,
                 var_y: str | None = None) -> bool:
    """Gráfico do estudo: curva (1-D) ou heatmap (2-D). Devolve False se sem matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:  # pragma: no cover
        return False

    fig, ax = plt.subplots(figsize=(6, 4.2))
    if var_y is None:
        xs = [r[var_x] for r in rows if r.get(metric) is not None]
        ys = [r[metric] for r in rows if r.get(metric) is not None]
        ax.plot(xs, ys, "-o", markersize=4)
        ax.set_xlabel(var_x)
        ax.set_ylabel(metric)
        ax.grid(True, alpha=0.3)
    else:
        xvals = sorted({r[var_x] for r in rows})
        yvals = sorted({r[var_y] for r in rows})
        grid = np.full((len(yvals), len(xvals)), np.nan)
        idx = {(r[var_x], r[var_y]): r for r in rows}
        for iy, vy in enumerate(yvals):
            for ix, vx in enumerate(xvals):
                v = idx.get((vx, vy), {}).get(metric)
                if v is not None:
                    grid[iy, ix] = v
        im = ax.imshow(grid, origin="lower", aspect="auto", cmap="viridis",
                       extent=[min(xvals), max(xvals), min(yvals), max(yvals)])
        fig.colorbar(im, ax=ax, label=metric)
        ax.set_xlabel(var_x)
        ax.set_ylabel(var_y)
    ax.set_title(f"{metric} vs {var_x}" + (f" × {var_y}" if var_y else ""))
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return True


__all__ = ["sweep_1d", "sweep_2d", "optimize", "plot_surface", "VARIABLES"]
