"""Secador de gás (leito de tam Sieves/molecular sieve) para o gás tratado.

Remove H2O do gás de topo até a especificação do ponto de uso (motor/gasoduto:
60-200 mg/Nm³). Modelagem: remoção estequiométrica de H2O (o leito satura e
regenera por TSA -- Temperature Swing Adsorption), sem mistura de fase.

Energia: duty de regeneração térmica proporcional à água removida
(~4-6 MJ/kg H2O típico p/ tam com TSA; Mersmann/Gandhi TS&A). A potência é
reportada como carga térmica (kW térmicos).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import Stream, UnitResult

# ~4.5 MJ/kg de H2O removida: calor de dessorção (~4.2) + eficiência do ciclo
# de regeneração (perdas no aquecimento do leito e do gás de descarga).
REGEN_SPECIFIC_KJ_PER_KG = 4500.0

MM_H2O = 0.018015


@dataclass
class DryerResult(UnitResult):
    out: Stream = None
    water_removed_kg_h: float = 0.0
    regen_duty_kW: float = 0.0          # térmico
    dew_point_out_K: float = float("nan")


def dry_gas(stream: Stream, target_mg_per_nm3: float,
            regen_specific_kj_per_kg: float = REGEN_SPECIFIC_KJ_PER_KG) -> DryerResult:
    """Seca ``stream`` (vapor contendo H2O) até ``target_mg_per_nm3`` (base úmida).

    O leito retém a água: a saída tem a mesma vazão molar total (gás seco +
    H2O residual -- vazão total varia pouco) e composição com ``y_H2O``
    reduzida. Se o gás já está abaixo da especificação, sai inalterado
    (convergiu, sem duty).
    """
    from ..Properties.Moisture import y_from_water_content

    sp = list(stream.species)
    if "H2O" not in sp:
        return DryerResult(converged=True, iterations=0, out=stream.copy(),
                           water_removed_kg_h=0.0, regen_duty_kW=0.0)
    i_h2o = sp.index("H2O")
    y_in = float(stream.z[i_h2o])
    c = min(y_from_water_content(target_mg_per_nm3), y_in)    # y_H2O na SAÍDA
    n_h2o_in = y_in * stream.flow                # mol/s de água na entrada
    n_dry = stream.flow * (1.0 - y_in)           # mol/s de gás seco (fixo)
    # especificação na base úmida da SAÍDA: y_out = c -> n_out = n_dry/(1-c)
    n_out_total = n_dry / max(1.0 - c, 1e-12)
    z_out = stream.z.copy()
    s_dry = max(1.0 - y_in, 1e-12)
    z_out = np.array([z / s_dry * (1.0 - c) for z in z_out])
    z_out[i_h2o] = c
    n_removed = max(n_h2o_in - c * n_out_total, 0.0)
    out = Stream(sp, float(n_out_total), z_out, float(stream.T),
                 float(stream.P), phase="vapor")
    kg_h = n_removed * MM_H2O * 3600.0
    duty_kw = kg_h / 3600.0 * regen_specific_kj_per_kg   # (kg/s)·(kJ/kg) = kW
    from ..Properties.Moisture import dew_point_H2O
    dp = dew_point_H2O(z_out[i_h2o], stream.P)
    return DryerResult(converged=True, iterations=0, out=out,
                       water_removed_kg_h=float(kg_h),
                       regen_duty_kW=float(duty_kw), dew_point_out_K=float(dp))


__all__ = ["dry_gas", "DryerResult", "REGEN_SPECIFIC_KJ_PER_KG"]
