"""Loop de regeneração do solvente físico (água): flashes + reciclo + purge.

Água rica sai da base do absorvedor a ``P_abs`` e é regenerada por
depressurização em dois estágios (arquitetura padrão de water scrubbing):

  1. **Flash 1 (média pressão, ~1/2 de P_abs):** libera o gás dissolvido; a
     fração rica em CH4 (pouco solúvel) sai no topo e é *recomprimida e
     reciclada* para a entrada do absorvedor -- reduz a perda de CH4.
  2. **Flash 2 (≈ atmosférica):** vent de CO2 (majoritário).
  3. **Purge/makeup:** fração ``purge_frac`` da água magra é purgada (controle
     de sais/microbiologia) e repostas por água fresca.
  4. **Bomba do reciclo:** água magra da pressão do flash 2 até ``P_abs``.

O equilíbrio dos flashes usa **Henry-flash** (Rachford-Rice com K_i = H_i/P para
os gases dissolvidos e K_H2O = P_sat/P), mais robusto e fisicamente correto que
uma EOS cúbica para gases diluídos em água: K_CO2 ≈ 1500 a 1 atm -- tudo
desorbe; K_H2O ≈ 0.023 -- água fica líquida.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..Properties.Moisture import water_p_sat
from ..Thermodynamics.Henry import HENRY_WATER
from .base import Stream, UnitResult
from .Compressor import compress
from .Pump import pump

# fração de purge típica de water scrubbing (controle de microbiologia/sais)
DEFAULT_PURGE_FRAC = 0.02


@dataclass
class RegenResult(UnitResult):
    lean_out: Stream = None              # água magra re-pressurizada a P_abs
    flash1_gas: Stream = None            # reciclo (gás do flash 1, a P_flash1)
    recycle: Stream | None = None        # reciclo recomprimido a P_abs
    vent: Stream = None                  # vent do CO2 (flash 2)
    purge: Stream = None                 # água purgada (kg/h de perda)
    makeup_mols: float = 0.0             # mol/s de água fresca necessária
    recycle_compression_kW: float = 0.0
    lean_pump_kW: float = 0.0
    ch4_recovered_mols: float = 0.0      # mol/s de CH4 devolvido ao processo
    co2_released_mols: float = 0.0       # mol/s de CO2 liberado (flash 1 + 2)
    flash_details: dict = field(default_factory=dict)


def _henry_k(species: str, T: float, P: float) -> float:
    """K_i do flash de Henry: gases via HENRY_WATER, água via Psat/P."""
    if species == "H2O":
        return water_p_sat(T) / P
    hp = HENRY_WATER.get(species)
    if hp is None:
        return float(np.inf)             # não-condensável: vai todo pro vapor
    return hp.H(T) / P


def _flash_henry(stream: Stream, T: float, P: float) -> tuple[Stream, Stream, float]:
    """Flash TP com K de Henry/Rachford-Rice (gases diluídos em solvente).

    Retorna (vapor, líquido, beta). Converge sempre (β via bisseção em [0,1];
    todos K>1 → β→1, todos K<1 → β→0).
    """
    sp = list(stream.species)
    z = np.asarray(stream.z, dtype=float)
    K = np.array([_henry_k(s, T, P) for s in sp])
    has_gas = np.any(K > 1.0 + 1e-12)

    def rr(beta):
        if beta <= 0.0:
            beta = 1e-12
        if beta >= 1.0:
            beta = 1.0 - 1e-12
        return float(np.sum(z * (K - 1.0) / (1.0 + beta * (K - 1.0))))

    lo, hi = 1e-12, 1.0 - 1e-12
    if not has_gas or rr(lo) <= 0.0:
        beta = 0.0                       # não há gás suficiente
    elif rr(hi) >= 0.0:
        beta = 1.0
    else:
        for _ in range(100):             # bisseção (robusta, ~1e-12 de precisão)
            mid = 0.5 * (lo + hi)
            if rr(mid) > 0.0:
                lo = mid
            else:
                hi = mid
            beta = 0.5 * (lo + hi)
    if beta <= 0.0:
        vapor = Stream(sp, 0.0, np.zeros(len(sp)), float(T), float(P), "vapor")
        liquid = Stream(sp, float(stream.flow), z, float(T), float(P), "liquid")
        return vapor, liquid, 0.0
    denom = 1.0 + beta * (K - 1.0)
    y = z * K / denom
    x = z / denom
    vapor = Stream(sp, float(stream.flow * beta), y, float(T), float(P), "vapor")
    liquid = Stream(sp, float(stream.flow * (1.0 - beta)), x, float(T), float(P), "liquid")
    return vapor, liquid, float(beta)


def regen_water(rich: Stream, P_abs: float, P_flash1: float = 5.0e5,
                P_flash2: float = 1.0e5, T_flash: float = 293.15,
                purge_frac: float = DEFAULT_PURGE_FRAC,
                eta_pump: float = 0.7, eta_comp: float = 0.75,
                strip_air: bool = True) -> RegenResult:
    """Regenera água rica por dois flashes + recuperação do CH4 + purge + bomba.

    Arquitetura Wellmann (padrão de water scrubbing): o gás do flash 1
    (enriquecido em CH4 -- K_CH4/K_CO2 >> 1 favorece a liberação seletiva)
    é recomprimido e devolvido à ALIMENTAÇÃO do absorvedor pelo chamador
    (loop de ponto fixo; ver ``Examples.WaterScrubbing``). O flash 2 libera
    o CO2 remanescente (``vent``); o CH4 que vai com o vent é perda
    (reportado em ``flash_details``). A água magra é bombeada de ``P_flash2``
    a ``P_abs`` (``lean_out``) e o ``purge``/makeup fecha o balanço de água
    (makeup = purge + água evaporada nos gases de flash, para que o loop
    fechado mantenha a vazão de solvente).

    ``strip_air=True``: a coluna de dessorção opera com varredura de ar
    (padrão industrial), de modo que a água magra sai em equilíbrio com ar --
    y_CO2 ~ 0 -- e não com o próprio gás desorvido. Sem isso, o x_CO2 residual
    do flash simples (x = P_flash2/H_CO2 ~ 7e-4) fixa o topo do absorvedor em
    ~5% de CO2; com ar, o lean sai praticamente sem gás dissolvido. Os gases
    remanescentes no líquido vão para o ``vent``.

    Selecione ``P_flash1`` ~ 0.5-0.7 · P_abs: mais alto = gás de reciclo mais
    rico em CH4 (mais CH4 devolvido, menos diluição do feed), mais baixo =
    mais gás (e CH4) recuperado no flash.
    """
    # 1) flash 1 (média pressão): gás enriquecido em CH4 -> reciclo/feed
    v1, l1, b1 = _flash_henry(rich, T_flash, P_flash1)
    # 2) flash 2 (atmosférico): vent de CO2
    v2, l2, b2 = _flash_henry(l1, T_flash, P_flash2)

    if strip_air and l2.flow > 0 and len(l2.species) > 1:
        # coluna de dessorção com ar: os gases remanescentes no líquido
        # desorvem (equilíbrio com ar -> x_gas ~ 0) e vão para o vent.
        i_h2o_l2 = list(l2.species).index("H2O")
        extra = np.array([l2.flow * l2.z[i] for i in range(len(l2.species))])
        n_extra = float(sum(extra[i] for i in range(len(l2.species)) if i != i_h2o_l2))
        if n_extra > 1e-12:
            z_extra = np.zeros(len(l2.species))
            for i in range(len(l2.species)):
                if i != i_h2o_l2:
                    z_extra[i] = extra[i] / n_extra
            tot = v2.flow + n_extra
            z_v2 = (v2.z * v2.flow + z_extra * n_extra) / max(tot, 1e-30)
            v2 = Stream(list(v2.species), float(tot), z_v2, float(T_flash),
                        float(P_flash2), phase="vapor")
            z_lean = np.zeros(len(l2.species))
            z_lean[i_h2o_l2] = 1.0
            n_lean = float(l2.flow) * float(l2.z[i_h2o_l2])   # água que ficou
            l2 = Stream(list(l2.species), n_lean, z_lean, float(T_flash),
                        float(P_flash2), phase="liquid")

    n_liq = l2.flow
    n_purge = n_liq * float(np.clip(purge_frac, 0.0, 1.0))
    n_recirc = n_liq - n_purge

    # 3) purge (água a P_flash2) e makeup equivalente: o makeup repõe o purge
    #    MAIS a água evaporada nos gases de flash (balanço de água em regime
    #    permanente; sem isso o solvente recirculado encolhe a cada passe).
    purge = Stream(list(l2.species), float(n_purge), l2.z.copy(),
                   float(T_flash), float(P_flash2), phase="liquid")
    i_h2o = list(rich.species).index("H2O") if "H2O" in rich.species else -1
    evap_mols = 0.0
    if i_h2o >= 0:
        w_rich = float(rich.flow) * float(rich.z[i_h2o])
        w_l2 = float(l2.flow) * float(l2.z[i_h2o])
        evap_mols = max(w_rich - w_l2, 0.0)
    #    (a corrente de makeup em si é construída pelo chamador, no lado do
    #    laço fechado; aqui reportamos apenas a vazão equivalente)
    makeup_mols = float(n_purge + evap_mols)

    # 4) bomba do recirculado (sem o purge): P_flash2 -> P_abs
    recirc_stream = Stream(list(l2.species), float(n_recirc), l2.z.copy(),
                           float(T_flash), float(P_flash2), phase="liquid")
    pu = pump(recirc_stream, P_abs, eta=eta_pump) if n_recirc > 0 else None
    lean = Stream(list(l2.species), float(n_recirc), l2.z.copy(),
                  float(pu.out.T if pu else T_flash), float(P_abs), phase="liquid")
    lean_pump_kW = float(pu.work / 1000.0) if pu else 0.0

    # 5) recompressão do gás do flash 1 -> linha de produto
    comp_kw = 0.0
    recycle = None
    ch4_recovered = 0.0
    i_ch4_vent = v2.species.index("CH4") if "CH4" in v2.species else -1
    ch4_in_vent = float(v2.flow * v2.z[i_ch4_vent]) if i_ch4_vent >= 0 else 0.0
    if v1.flow > 1e-12:
        i_ch4 = v1.species.index("CH4") if "CH4" in v1.species else -1
        ch4_recovered = float(v1.flow * v1.z[i_ch4]) if i_ch4 >= 0 else 0.0
        c = compress(v1, P_abs, eta=eta_comp)
        recycle = c.out
        comp_kw = c.work / 1000.0

    # balanços
    co2_total = 0.0
    for v in (v1, v2):
        if "CO2" in v.species:
            co2_total += float(v.flow * v.z[v.species.index("CO2")])

    return RegenResult(
        converged=True, iterations=2,
        lean_out=lean, flash1_gas=v1, recycle=recycle, vent=v2, purge=purge,
        makeup_mols=makeup_mols,
        recycle_compression_kW=float(comp_kw),
        lean_pump_kW=float(lean_pump_kW),
        ch4_recovered_mols=ch4_recovered,
        co2_released_mols=co2_total,
        flash_details={
            "flash1_beta": float(b1), "flash2_beta": float(b2),
            "flash1_gas_mols": float(v1.flow), "flash2_gas_mols": float(v2.flow),
            "flash1_gas_CH4_pct": float(v1.z[v1.species.index("CH4")] * 100)
            if "CH4" in v1.species else 0.0,
            "ch4_lost_in_vent_mols": float(ch4_in_vent),
            "water_evaporated_mols": float(evap_mols),
        },
    )


__all__ = ["regen_water", "RegenResult", "_flash_henry", "_henry_k",
           "DEFAULT_PURGE_FRAC"]
