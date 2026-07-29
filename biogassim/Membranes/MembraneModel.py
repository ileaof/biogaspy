"""Modelo de membrana -- fluxo solução-difusão (1 estágio).

Fluxo de cada espécie: J_i = (P_i/t) (p_feed_i - p_perm_i), com P_i
permeabilidade. Resolve o balanço em um estágio (cross-flow simplificado)
para estimar pureza e recuperação. Configurações multi-estágio (reciclo) são
extensão futura.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .Permeability import MEMBRANES


@dataclass
class MembraneResult:
    permeate: dict[str, float]    # frações molares no permeado
    retentate: dict[str, float]   # frações no retentado (biometano)
    permeate_flow: float          # mol/s
    retentate_flow: float
    purity_CH4: float
    recovery_CH4: float
    CO2_removal: float
    area: float                   # m²
    message: str = ""


def single_stage(material: str, feed_species: list[str], z_feed: np.ndarray,
                 feed_flow: float, T: float, P_feed: float, P_permeate: float,
                 area: float = 50.0, stage_cut: float = 0.5) -> MembraneResult:
    """Membrana de 1 estágio (cross-flow, modelo simplificado de mistura).

    Resolve o balanço por componente para um corte de estágio ``θ`` = permeado/feed.
    """
    m = MEMBRANES[material]
    z = np.asarray(z_feed, dtype=float)
    z = z / z.sum()
    # pressões parciais
    p_f = z * P_feed
    # permeabilidades em mol/(m·s·Pa)
    perm = np.array([m.perm_si(s) for s in feed_species])
    # fluxo relativo de cada espécie (proporcional a P_i * Δp)
    # Δp aprox = p_f - p_perm (p_perm estimado pelo próprio permeado -> iteração simples)
    y_perm = z.copy()
    for _ in range(30):
        p_perm = y_perm * P_permeate
        flux = perm * (p_f - p_perm)
        flux = np.clip(flux, 0.0, None)
        s = flux.sum()
        if s <= 0:
            break
        y_perm_new = flux / s
        if np.max(np.abs(y_perm_new - y_perm)) < 1e-8:
            y_perm = y_perm_new
            break
        y_perm = 0.5 * y_perm_new + 0.5 * y_perm
    # corte de estágio: define vazão do permeado
    perm_flow = feed_flow * stage_cut
    ret_flow = feed_flow - perm_flow
    # composição do retentado por balanço
    z_perm = y_perm
    z_ret = (z * feed_flow - z_perm * perm_flow) / max(ret_flow, 1e-12)
    z_ret = np.clip(z_ret, 0.0, None)
    z_ret = z_ret / z_ret.sum()
    # área estimada a partir do fluxo de CO2 (checagem de consistência)
    # J_total ~ perm_flow/(area); usamos apenas como saída
    res = {"permeate": dict(zip(feed_species, z_perm)),
           "retentate": dict(zip(feed_species, z_ret)),
           "permeate_flow": perm_flow, "retentate_flow": ret_flow,
           "area": area, "message": "Modelo solução-difusão 1 estágio (cross-flow simplificado)."}
    sp = feed_species
    i_ch4 = sp.index("CH4") if "CH4" in sp else None
    i_co2 = sp.index("CO2") if "CO2" in sp else None
    res["purity_CH4"] = float(z_ret[i_ch4]) if i_ch4 is not None else 0.0
    if i_ch4 is not None:
        res["recovery_CH4"] = float(z_ret[i_ch4] * ret_flow / (z[i_ch4] * feed_flow))
    else:
        res["recovery_CH4"] = 0.0
    if i_co2 is not None:
        res["CO2_removal"] = 1.0 - float(z_ret[i_co2] * ret_flow / (z[i_co2] * feed_flow))
    else:
        res["CO2_removal"] = 0.0
    return MembraneResult(**res)


__all__ = ["single_stage", "MembraneResult"]
