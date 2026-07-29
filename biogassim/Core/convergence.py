"""Critérios e aceleradores de convergência para o solver iterativo."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass
class ConvergenceReport:
    converged: bool
    iterations: int
    residual_norm: float
    message: str = ""

    def __bool__(self) -> bool:  # noqa: D401
        return self.converged


def residual_norm(f: np.ndarray) -> float:
    """Norma L2 do vetor residual, normalizada para robustez."""
    f = np.asarray(f, dtype=float)
    n = max(f.size, 1)
    return float(np.sqrt(np.sum(f * f) / n))


def relative_tolerance(x_new: np.ndarray, x_old: np.ndarray) -> float:
    """Mudança relativa máxima entre iterações (medida de convergência)."""
    x_new = np.asarray(x_new, dtype=float)
    x_old = np.asarray(x_old, dtype=float)
    denom = np.maximum(np.abs(x_new), 1.0e-12)
    return float(np.max(np.abs(x_new - x_old) / denom))


def converged(res: np.ndarray, tol: float = 1.0e-8) -> bool:
    return residual_norm(res) <= tol


def wegstein(
    g: Callable[[np.ndarray], np.ndarray],
    x0: np.ndarray,
    max_iter: int = 100,
    tol: float = 1.0e-8,
    relax_min: float = -5.0,
    relax_max: float = 5.0,
) -> tuple[np.ndarray, ConvergenceReport]:
    """Aceleração de Wegstein para ponto fixo ``x = g(x)``.

    Útil para problemas de reciclo / especificação de fluxo onde a iteração
    funcional é estável mas lenta.
    """
    x = np.array(x0, dtype=float)
    x_prev = g(x.copy())
    if relative_tolerance(x_prev, x) < tol:
        return x_prev, ConvergenceReport(True, 1, residual_norm(g(x_prev) - x_prev))
    g_prev = g(x_prev.copy())
    for k in range(2, max_iter + 1):
        denom = x_prev - x
        with np.errstate(divide="ignore", invalid="ignore"):
            q = np.where(
                np.abs(denom) > 1.0e-14,
                (g_prev - x_prev) / denom,
                0.0,
            )
            a = 1.0 - q
            a = np.clip(a, relax_min, relax_max)
            w = q / a
            w = np.clip(w, relax_min, relax_max)
        x_new = w * g_prev + (1.0 - w) * x_prev
        if relative_tolerance(x_new, x_prev) < tol:
            return x_new, ConvergenceReport(True, k, residual_norm(g(x_new) - x_new))
        x = x_prev
        x_prev = x_new
        g_prev = g(x_prev.copy())
    return x_prev, ConvergenceReport(False, max_iter, residual_norm(g(x_prev) - x_prev))


__all__ = [
    "ConvergenceReport", "residual_norm", "relative_tolerance",
    "converged", "wegstein",
]
