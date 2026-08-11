"""Unidades auxiliares: Cooler, Pump, HeatExchanger, Flash drum, Stripper."""
from __future__ import annotations

from dataclasses import dataclass

from ..Properties.components import get as get_comp
from ..Properties.Mixtures import molar_weight
from ..Thermodynamics.Flash import isothermal_flash
from ..Thermodynamics.Interactions import kij_matrix
from ..Thermodynamics.PengRobinson import PengRobinson
from .base import Stream, UnitResult


@dataclass
class CoolerResult(UnitResult):
    out: Stream = None
    duty: float = 0.0   # W (negativo = remove calor)


def cooler(stream: Stream, T_out: float, P_out: float = None) -> CoolerResult:
    """Resfriador/isotérmico: T_out fixa, duty via Cp ideal."""
    P_out = P_out or stream.P
    cp_mix = sum(zi * get_comp(s).cp(stream.T) for zi, s in zip(stream.z, stream.species))
    duty = stream.flow * cp_mix * (T_out - stream.T)
    out = Stream(list(stream.species), stream.flow, stream.z.copy(),
                 float(T_out), float(P_out), phase=stream.phase)
    return CoolerResult(converged=True, iterations=0, out=out, duty=duty)


@dataclass
class PumpResult(UnitResult):
    out: Stream = None
    work: float = 0.0


def pump(stream: Stream, P_out: float, eta: float = 0.7) -> PumpResult:
    """Bomba de líquido: W = V_dot ΔP / η."""
    mm = molar_weight([get_comp(s) for s in stream.species], stream.z)
    rho = mm / (get_comp(stream.species[0]).MM / 1000.0)  # aproximado por MM médio -> densidade
    rho = 1000.0  # líquido ~água (placeholder; solvente define rho)
    Vdot = stream.flow * mm / rho
    work = Vdot * (P_out - stream.P) / eta
    out = Stream(list(stream.species), stream.flow, stream.z.copy(),
                 float(stream.T), float(P_out), phase="liquid")
    return PumpResult(converged=True, iterations=0, out=out, work=work)


@dataclass
class FlashResult(UnitResult):
    vapor: Stream = None
    liquid: Stream = None
    beta: float = 0.0


def flash_drum(stream: Stream, T: float, P: float) -> FlashResult:
    """Flash isotérmico TP usando EOS PR."""
    comps = [get_comp(s) for s in stream.species]
    eos = PengRobinson(comps, kij=kij_matrix(list(stream.species)))
    fr = isothermal_flash(eos, stream.z, T, P)
    vapor = Stream(list(stream.species), float(stream.flow * fr.beta), fr.y,
                   float(T), float(P), phase="vapor")
    liquid = Stream(list(stream.species), float(stream.flow * (1 - fr.beta)), fr.x,
                    float(T), float(P), phase="liquid")
    return FlashResult(converged=fr.converged, iterations=fr.iterations,
                       vapor=vapor, liquid=liquid, beta=fr.beta)


def heat_exchanger(hot_in: Stream, cold_in: Stream, T_hot_out: float) -> tuple:
    """Trocador contra-corrente simples (apenas T quente fixa)."""
    hot_cp = sum(zi * get_comp(s).cp(hot_in.T) for zi, s in zip(hot_in.z, hot_in.species))
    Q = hot_in.flow * hot_cp * (hot_in.T - T_hot_out)
    cold_cp = sum(zi * get_comp(s).cp(cold_in.T) for zi, s in zip(cold_in.z, cold_in.species))
    T_cold_out = cold_in.T + Q / (cold_in.flow * cold_cp)
    hot_out = Stream(list(hot_in.species), hot_in.flow, hot_in.z.copy(),
                     float(T_hot_out), float(hot_in.P), phase=hot_in.phase)
    cold_out = Stream(list(cold_in.species), cold_in.flow, cold_in.z.copy(),
                     float(T_cold_out), float(cold_in.P), phase=cold_in.phase)
    return hot_out, cold_out, Q


__all__ = ["cooler", "CoolerResult", "pump", "PumpResult",
           "flash_drum", "FlashResult", "heat_exchanger"]
