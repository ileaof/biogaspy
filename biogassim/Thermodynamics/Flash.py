"""Cálculo de flash multicomponente (isotérmico e adiabático).

Flash isotérmico: Rachford-Rice + K-values da EOS (substituição sucessiva com
aceleração). Flash adiabático: busca em T que satisfaz o balanço de entalpia,
reusando o flash isotérmico.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
from scipy.optimize import brentq

from ..Core.constants import R_J_MOL_K
from ..Properties.components import Component
from .eos import CubicEOS


@dataclass
class FlashResult:
    T: float
    P: float
    beta: float               # fração vapor (mol/mol)
    x: np.ndarray             # líquido
    y: np.ndarray             # vapor
    K: np.ndarray
    converged: bool
    iterations: int


def _rachford_rice(beta: float, z: np.ndarray, K: np.ndarray) -> float:
    return float(np.sum(z * (K - 1.0) / (1.0 + beta * (K - 1.0))))


def _solve_rr(z: np.ndarray, K: np.ndarray) -> float:
    """Resolve Rachford-Rice para β ∈ (0,1)."""
    # limites físicos: se todo K<=1 -> líquido (β=0); todo K>=1 -> vapor (β=1)
    if np.all(K <= 1.0):
        return 0.0
    if np.all(K >= 1.0):
        return 1.0
    try:
        return float(brentq(_rachford_rice, 1e-8, 1.0 - 1e-8, args=(z, K)))
    except ValueError:
        # mistura bifásica instável: tenta intervalo amplo
        return float(brentq(_rachford_rice, 1e-10, 1.0 - 1e-10, args=(z, K)))


def _wilson_K(components: List[Component], T: float, P: float) -> np.ndarray:
    """K inicial de Wilson: K_i = (Pc_i/P) exp(5.373(1+ω_i)(1-Tc_i/T))."""
    Pc = np.array([c.Pc for c in components])
    Tc = np.array([c.Tc for c in components])
    omega = np.array([c.omega for c in components])
    return (Pc / P) * np.exp(5.373 * (1.0 + omega) * (1.0 - Tc / T))


def isothermal_flash(eos: CubicEOS, z: np.ndarray, T: float, P: float,
                     max_iter: int = 80, tol: float = 1e-8) -> FlashResult:
    """Flash isotérmico TP via substituição sucessiva em K."""
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    # detecção de fase única (mistura supercrítica / todo vapor ou todo líquido)
    state = eos.phase_state(T, P, z)
    if state == "vapor":
        return FlashResult(T, P, 1.0, z.copy(), z.copy(), np.ones_like(z), True, 0)
    if state == "liquid":
        return FlashResult(T, P, 0.0, z.copy(), z.copy(), np.ones_like(z), True, 0)
    K = _wilson_K(eos.components, T, P)
    beta = _solve_rr(z, K)
    for it in range(1, max_iter + 1):
        denom = 1.0 + beta * (K - 1.0)
        x = z / denom
        y = K * x
        x = x / x.sum()
        y = y / y.sum()
        K_new = eos.K_values(T, P, x, y)
        if np.any(~np.isfinite(K_new)) or np.any(K_new <= 0):
            # fallback: mantém K anterior
            K_new = np.where(np.isfinite(K_new) & (K_new > 0), K_new, K)
        dK = np.max(np.abs(K_new - K))
        K = K_new
        beta = _solve_rr(z, K)
        if dK < tol:
            denom = 1.0 + beta * (K - 1.0)
            x = z / denom
            y = K * x
            return FlashResult(T, P, beta, x / x.sum(), y / y.sum(), K, True, it)
    denom = 1.0 + beta * (K - 1.0)
    x = z / denom
    y = K * x
    return FlashResult(T, P, beta, x / x.sum(), y / y.sum(), K, False, max_iter)


def _mixture_enthalpy(eos: CubicEOS, components: List[Component],
                      T: float, P: float, z: np.ndarray, phase: str) -> float:
    """Entalpia (J/mol) = ideal + departada da EOS (aproximada)."""
    ideal = sum(zi * c.ideal_enthalpy(T) for zi, c in zip(z, components))
    r = eos.Z_and_phi(T, P, z, phase=phase)
    Z = r.Z
    # departada: H - H^ig = RT(Z - 1) + (T dA/dT - A)/(b sqrt2) ln(...) para PR
    # simplificada: usamos apenas RT(Z-1) como aproximação de fase vapor
    dep = R_J_MOL_K * T * (Z - 1.0)
    return float(ideal + dep)


def adiabatic_flash(eos: CubicEOS, components: List[Component],
                    z: np.ndarray, P: float, T_feed: float,
                    max_iter: int = 60, tol: float = 1e-3) -> FlashResult:
    """Flash adiabático PH: busca T tal que H_produto = H_feed.

    Feed assumido monofásico (vapor) à T_feed, P_feed~P. A busca em T é feita
    por bisseção envolvendo o flash isotérmico.
    """
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    H_feed = _mixture_enthalpy(eos, components, T_feed, P, z, phase="vapor")

    def H_product(T: float) -> float:
        fr = isothermal_flash(eos, z, T, P)
        Hv = _mixture_enthalpy(eos, components, T, P, fr.y, phase="vapor")
        Hl = _mixture_enthalpy(eos, components, T, P, fr.x, phase="liquid")
        return fr.beta * Hv + (1.0 - fr.beta) * Hl

    # intervalo de busca em T
    Tlo, Thi = 200.0, 600.0
    for _ in range(max_iter):
        Tmid = 0.5 * (Tlo + Thi)
        dH = H_product(Tmid) - H_feed
        if abs(dH) < tol * max(1.0, abs(H_feed)):
            return isothermal_flash(eos, z, Tmid, P)
        if dH > 0:
            Thi = Tmid
        else:
            Tlo = Tmid
    return isothermal_flash(eos, z, 0.5 * (Tlo + Thi), P)


__all__ = ["FlashResult", "isothermal_flash", "adiabatic_flash"]