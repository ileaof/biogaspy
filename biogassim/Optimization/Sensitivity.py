"""Estudo paramétrico (sensibilidade) reusando o solver da coluna.

Como o Absorvedor agora usa Newton global (converge em toda a faixa de L/V,
P e T), varreduras paramétricas são robustas -- antes, a substituição
sucessiva divergia perto do pinch, tornando estudos de sensibilidade
inviáveis.

API:
    sweep(...)        -- varre UM parâmetro (1-D) sobre uma lista de valores.
    sweep_grid(...)   -- varre DOIS parâmetros (grade 2-D) para heatmaps.

Parâmetros suportados: ``"pressure"``, ``"T_op"``, ``"N_stages"``,
``"height"``, ``"L_over_V"``. Métricas coletadas: pureza CH4, recuperação
CH4, remoção CO2, carregamento rico (se houver amina), convergência.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from ..UnitOperations import Absorber, AbsorberSpec
from ..UnitOperations.base import Stream


@dataclass
class SweepResult:
    parameter: str
    values: List[float]
    purity_CH4: List[float] = field(default_factory=list)      # fração (0-1)
    recovery_CH4: List[float] = field(default_factory=list)
    CO2_removal: List[float] = field(default_factory=list)
    rich_loading: List[float] = field(default_factory=list)
    converged: List[bool] = field(default_factory=list)

    def to_rows(self) -> List[Dict]:
        rows = []
        for k, v in enumerate(self.values):
            rows.append({
                self.parameter: v,
                "purity_CH4_pct": round(self.purity_CH4[k] * 100, 3),
                "recovery_CH4_pct": round(self.recovery_CH4[k] * 100, 3),
                "CO2_removal_pct": round(self.CO2_removal[k] * 100, 3),
                "rich_loading": round(self.rich_loading[k], 4),
                "converged": bool(self.converged[k]),
            })
        return rows

    @property
    def n_converged(self) -> int:
        return int(sum(self.converged))


# --------------------------------------------------------------------------- #
def _metrics(result, solvent, species) -> tuple:
    if not result.converged:
        # ponto não convergido: solvente possivelmente sobrecarregado
        # (rich loading > α_max) -- métricas não têm significado físico.
        rich = float("nan")
        amine = getattr(solvent, "amine_name", "")
        if amine and amine in species and "CO2" in species:
            i = species.index("CO2"); j = species.index(amine)
            rich = float(result.liquid_out.z[i] / max(result.liquid_out.z[j], 1e-12))
        return (float("nan"), float("nan"), float("nan"), rich, False)
    rich = float("nan")
    amine = getattr(solvent, "amine_name", "")
    if amine and amine in species and "CO2" in species:
        i = species.index("CO2")
        j = species.index(amine)
        rich = float(result.liquid_out.z[i] / max(result.liquid_out.z[j], 1e-12))
    return (float(result.purity_CH4), float(result.methane_recovery),
            float(result.CO2_removal), rich, bool(result.converged))


def _streams_at_P(gas_in: Stream, solvent_in: Stream, P: float) -> tuple:
    g = Stream(list(gas_in.species), gas_in.flow, gas_in.z.copy(), gas_in.T, P, "vapor")
    s = Stream(list(solvent_in.species), solvent_in.flow, solvent_in.z.copy(),
               solvent_in.T, P, "liquid")
    return g, s


def _apply_param(spec, gas_in, solvent_in, parameter, value):
    """Aplica um valor a um parâmetro, devolvendo (spec, gas, solvent)."""
    g, s = gas_in, solvent_in
    if parameter == "pressure":
        spec.pressure = float(value)
        g, s = _streams_at_P(gas_in, solvent_in, float(value))
    elif parameter == "T_op":
        spec.T_op = float(value)
    elif parameter == "N_stages":
        spec.N_stages = int(round(value))
    elif parameter == "height":
        spec.height = float(value)
    elif parameter == "L_over_V":
        s = Stream(list(solvent_in.species), float(value) * gas_in.flow,
                   solvent_in.z.copy(), solvent_in.T, solvent_in.P, "liquid")
    else:
        raise ValueError(f"Parâmetro desconhecido: {parameter}")
    return spec, g, s


def sweep(gas_in: Stream, solvent_in: Stream, solvent,
          base_spec: AbsorberSpec, parameter: str,
          values: Sequence[float]) -> SweepResult:
    """Varre um parâmetro do Absorvedor sobre ``values`` e coleta métricas."""
    res = SweepResult(parameter=parameter, values=list(values))
    for v in values:
        spec = AbsorberSpec(N_stages=base_spec.N_stages, packing=base_spec.packing,
                            diameter=base_spec.diameter, height=base_spec.height,
                            mode=base_spec.mode, T_op=base_spec.T_op,
                            pressure=base_spec.pressure, max_iter=base_spec.max_iter,
                            tol=base_spec.tol, method=base_spec.method)
        spec, g, s = _apply_param(spec, gas_in, solvent_in, parameter, v)
        try:
            r = Absorber(g, s, solvent, spec).solve()
            m = _metrics(r, solvent, gas_in.species)
        except Exception:
            m = (float("nan"), float("nan"), float("nan"), float("nan"), False)
        res.purity_CH4.append(m[0]); res.recovery_CH4.append(m[1])
        res.CO2_removal.append(m[2]); res.rich_loading.append(m[3])
        res.converged.append(m[4])
    return res


def sweep_grid(gas_in: Stream, solvent_in: Stream, solvent,
               base_spec: AbsorberSpec, param_x: str, values_x: Sequence[float],
               param_y: str, values_y: Sequence[float]) -> Dict[str, np.ndarray]:
    """Varredura 2-D (grade) de dois parâmetros -> matrizes para heatmap.

    Retorna dicionário com matrizes (len(values_y), len(values_x)) de
    purity_CH4, recovery_CH4, CO2_removal e converged.
    """
    nx, ny = len(values_x), len(values_y)
    purity = np.full((ny, nx), np.nan)
    recov = np.full((ny, nx), np.nan)
    rem = np.full((ny, nx), np.nan)
    conv = np.zeros((ny, nx), dtype=bool)
    for iy, vy in enumerate(values_y):
        for ix, vx in enumerate(values_x):
            spec = AbsorberSpec(N_stages=base_spec.N_stages, packing=base_spec.packing,
                                diameter=base_spec.diameter, height=base_spec.height,
                                mode=base_spec.mode, T_op=base_spec.T_op,
                                pressure=base_spec.pressure, max_iter=base_spec.max_iter,
                                tol=base_spec.tol, method=base_spec.method)
            # aplica param_y na base
            spec, g, s = _apply_param(spec, gas_in, solvent_in, param_y, vy)
            # aplica param_x por cima (a partir do estado já ajustado)
            spec, g, s = _apply_param(spec, g, s, param_x, vx)
            try:
                r = Absorber(g, s, solvent, spec).solve()
                m = _metrics(r, solvent, gas_in.species)
            except Exception:
                m = (np.nan, np.nan, np.nan, np.nan, False)
            purity[iy, ix] = m[0]; recov[iy, ix] = m[1]
            rem[iy, ix] = m[2]; conv[iy, ix] = m[4]
    return {"values_x": np.asarray(values_x), "values_y": np.asarray(values_y),
            "param_x": param_x, "param_y": param_y,
            "purity_CH4": purity, "recovery_CH4": recov,
            "CO2_removal": rem, "converged": conv}


# --------------------------------------------------------------------------- #
# API legada (mantida para compatibilidade)
@dataclass
class SensitivityPoint:
    param_value: float
    purity_CH4: float
    recovery_CH4: float
    CO2_removal: float
    converged: bool


def sweep_LG(gas_in: Stream, solvent_in_factory: Callable[[float], Stream],
             solvent, pressures: Optional[List[float]] = None,
             L_over_V: Optional[List[float]] = None, N_stages: int = 8,
             height: float = 12.0, T_op: float = 298.15) -> Dict[str, List[SensitivityPoint]]:
    """Varre L/G e pressão para o absorvedor (API legada)."""
    lvs = L_over_V or [5, 10, 20, 50, 100]
    Ps = pressures or [1e5, 5e5, 10e5, 20e5]
    base = AbsorberSpec(N_stages=N_stages, T_op=T_op, pressure=Ps[0],
                        height=height, max_iter=400)
    by_LV = []
    for lv in lvs:
        s = solvent_in_factory(lv * gas_in.flow)
        r = sweep(gas_in, s, solvent, base, "L_over_V", [lv])
        by_LV.append(SensitivityPoint(lv, r.purity_CH4[0], r.recovery_CH4[0],
                                      r.CO2_removal[0], r.converged[0]))
    by_P = []
    s0 = solvent_in_factory(lvs[0] * gas_in.flow)
    for P in Ps:
        r = sweep(gas_in, s0, solvent, base, "pressure", [P])
        by_P.append(SensitivityPoint(P / 1e5, r.purity_CH4[0], r.recovery_CH4[0],
                                     r.CO2_removal[0], r.converged[0]))
    return {"by_LV": by_LV, "by_P": by_P}


__all__ = ["sweep", "sweep_grid", "SweepResult", "sweep_LG", "SensitivityPoint"]