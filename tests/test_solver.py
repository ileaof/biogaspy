"""Testes do solver numérico (Newton, Broyden)."""
import numpy as np

from biogassim.Core.solver import newton_raphson, broyden


def test_newton_linear():
    """Sistema linear simples 2x2."""
    A = np.array([[2.0, 1.0], [1.0, 3.0]])
    b = np.array([3.0, 4.0])
    res = newton_raphson(lambda x: A @ x - b, np.array([0.0, 0.0]))
    assert res.converged
    assert np.allclose(res.x, np.linalg.solve(A, b), atol=1e-6)


def test_newton_nonlinear():
    """Raiz de F(x) = x^2 - 2 (raiz positiva = sqrt(2))."""
    F = lambda x: np.array([x[0] ** 2 - 2.0])
    res = newton_raphson(F, np.array([1.0]))
    assert res.converged
    assert abs(res.x[0] - np.sqrt(2.0)) < 1e-6


def test_broyden_linear():
    A = np.array([[4.0, 1.0], [1.0, 3.0]])
    b = np.array([1.0, 2.0])
    res = broyden(lambda x: A @ x - b, np.array([0.0, 0.0]))
    assert res.converged
    assert np.allclose(res.x, np.linalg.solve(A, b), atol=1e-5)


def test_wegstein_fixed_point():
    from biogassim.Core.convergence import wegstein
    # contração bem-comportada: x = 0.5 x + 1  ->  x* = 2
    g = lambda x: np.array([0.5 * x[0] + 1.0])
    x, rep = wegstein(g, np.array([0.0]))
    assert rep.converged
    assert abs(x[0] - 2.0) < 1e-6