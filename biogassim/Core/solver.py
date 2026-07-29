"""Solver numérico do BioGasSim.

Implementa métodos iterativos clássicos (Newton-Raphson com damping, Broyden,
GMRES sobre sistemas esparsos) com controle automático de convergência. O solver
é desacoplado das equações: as unidades de processo fornecem ``residual(x)`` e
``jacobian(x)`` (quando disponível).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy import sparse  # noqa: F401  (exposto para reuso)
from scipy.sparse.linalg import LinearOperator, gmres

from .convergence import ConvergenceReport, relative_tolerance, residual_norm


@dataclass
class SolveResult:
    x: np.ndarray
    report: ConvergenceReport

    @property
    def converged(self) -> bool:
        return self.report.converged


def newton_raphson(
    residual: Callable[[np.ndarray], np.ndarray],
    x0: np.ndarray,
    jacobian: Callable[[np.ndarray], np.ndarray] | None = None,
    max_iter: int = 80,
    tol: float = 1.0e-9,
    damp: float = 1.0,
    verbose: bool = False,
) -> SolveResult:
    """Newton-Raphson com damping fixo e diferenciação numérica de fallback.

    ``residual(x)`` devolve ``F(x)`` cuja raiz se busca. ``jacobian`` é opcional;
    se ausente, usa-se diferenças finitas por coluna (custo N+1 avaliações).
    """
    x = np.array(x0, dtype=float)
    for k in range(1, max_iter + 1):
        F = np.asarray(residual(x), dtype=float)
        if residual_norm(F) <= tol:
            return SolveResult(x, ConvergenceReport(True, k - 1, residual_norm(F), "Newton"))
        if jacobian is not None:
            J = np.asarray(jacobian(x), dtype=float)
        else:
            J = _numerical_jacobian(residual, x, F)
        try:
            dx = np.linalg.solve(J, -F)
        except np.linalg.LinAlgError:
            dx = np.linalg.lstsq(J, -F, rcond=None)[0]
        dx = _bound_step(dx, x, max_step=10.0)
        x_new = x + damp * dx
        if verbose:
            print(f"[Newton] iter {k}: |F|={residual_norm(F):.3e} step={np.linalg.norm(dx):.3e}")
        if relative_tolerance(x_new, x) < tol and residual_norm(np.asarray(residual(x_new))) <= max(tol, 1e-7):
            return SolveResult(x_new, ConvergenceReport(True, k, residual_norm(residual(x_new)), "Newton"))
        x = x_new
    F = np.asarray(residual(x), dtype=float)
    return SolveResult(x, ConvergenceReport(False, max_iter, residual_norm(F), "Newton (não convergiu)"))


def broyden(
    residual: Callable[[np.ndarray], np.ndarray],
    x0: np.ndarray,
    J0: np.ndarray | None = None,
    max_iter: int = 120,
    tol: float = 1.0e-8,
) -> SolveResult:
    """Método de Broyden (quase-Newton) de boa rank-1.

    Evita reavaliação da Jacobiana a cada passo -- útil quando ``residual`` é
    custoso e a Jacobiana analítica não está disponível.
    """
    x = np.array(x0, dtype=float)
    F = np.asarray(residual(x), dtype=float)
    if J0 is not None:
        J = np.array(J0, dtype=float)
    else:
        J = _numerical_jacobian(residual, x, F)
    if residual_norm(F) <= tol:
        return SolveResult(x, ConvergenceReport(True, 0, residual_norm(F), "Broyden"))
    for k in range(1, max_iter + 1):
        try:
            dx = np.linalg.solve(J, -F)
        except np.linalg.LinAlgError:
            dx = -F
        dx = _bound_step(dx, x, max_step=10.0)
        x_new = x + dx
        F_new = np.asarray(residual(x_new), dtype=float)
        dF = (F_new - F).reshape(-1, 1)
        dx_col = dx.reshape(-1, 1)
        # atualização rank-1 de Broyden (good)
        denom = float(dx_col.ravel() @ dF.ravel())
        if abs(denom) > 1.0e-14:
            J = J + ((dx_col - dF) @ dx_col.T) / denom
        if residual_norm(F_new) <= tol:
            return SolveResult(x_new, ConvergenceReport(True, k, residual_norm(F_new), "Broyden"))
        if relative_tolerance(x_new, x) < tol:
            return SolveResult(x_new, ConvergenceReport(True, k, residual_norm(F_new), "Broyden"))
        x = x_new
        F = F_new
    return SolveResult(x, ConvergenceReport(False, max_iter, residual_norm(F), "Broyden (não convergiu)"))


def solve_sparse(
    matvec: Callable[[np.ndarray], np.ndarray],
    b: np.ndarray,
    n: int | None = None,
    tol: float = 1.0e-8,
    max_iter: int = 500,
) -> np.ndarray:
    """Resolve ``A x = b`` com GMRES usando apenas ``matvec`` (operador linear)."""
    b = np.asarray(b, dtype=float)
    if n is None:
        n = b.size
    A = LinearOperator((n, n), matvec=matvec, dtype=float)
    x, info = gmres(A, b, rtol=tol, maxiter=max_iter)
    if info != 0:
        raise RuntimeError(f"GMRES não convergiu (info={info})")
    return x


def _numerical_jacobian(
    residual: Callable[[np.ndarray], np.ndarray],
    x: np.ndarray,
    F0: np.ndarray | None = None,
    eps: float = 1.0e-6,
) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    n = x.size
    if F0 is None:
        F0 = np.asarray(residual(x), dtype=float)
    J = np.zeros((F0.size, n))
    for j in range(n):
        h = eps * max(1.0, abs(x[j]))
        x_pert = x.copy()
        x_pert[j] += h
        Fp = np.asarray(residual(x_pert), dtype=float)
        J[:, j] = (Fp - F0) / h
    return J


def _bound_step(dx: np.ndarray, x: np.ndarray, max_step: float = 10.0) -> np.ndarray:
    """Limita o passo para evitar divergência em iterações iniciais."""
    norm = float(np.linalg.norm(dx))
    if norm > max_step and norm > 0:
        return dx * (max_step / norm)
    return dx


__all__ = [
    "SolveResult", "newton_raphson", "broyden", "solve_sparse",
]
