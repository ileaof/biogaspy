"""Compressor isentrópico com eficiência."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import Stream, UnitResult
from ..Core.constants import R_J_MOL_K
from ..Properties.components import get as get_comp
from ..Properties.Mixtures import molar_weight


@dataclass
class CompressorResult(UnitResult):
    out: Stream = None
    work: float = 0.0          # W (potência), J/s
    work_kj_kmol: float = 0.0  # kJ/kmol


def compress(stream: Stream, P_out: float, eta: float = 0.75,
             k: float = 1.31) -> CompressorResult:
    """Compressão politrópica/isentrópica simplificada (gás ideal, k médio).

    ``k`` = cp/cv da mistura (default ~1.31 para CH4/CO2). Retorna trabalho e
    corrente de saída com T_out e P_out.
    """
    P_in = stream.P
    r = P_out / P_in
    T_out_is = stream.T * r ** ((k - 1.0) / k)
    T_out = stream.T + (T_out_is - stream.T) / eta
    mm = molar_weight([get_comp(s) for s in stream.species], stream.z)
    work_kj_kmol = (k / (k - 1.0)) * R_J_MOL_K * (T_out_is - stream.T) / eta / 1000.0
    work = work_kj_kmol * 1000.0 * stream.flow   # J/s
    out = Stream(list(stream.species), stream.flow, stream.z.copy(),
                 float(T_out), float(P_out), phase="vapor")
    return CompressorResult(converged=True, iterations=0, out=out,
                            work=work, work_kj_kmol=work_kj_kmol)


__all__ = ["compress", "CompressorResult"]