"""Pacote Core do BioGasSim: constantes, unidades, solver e convergência."""
from .constants import (
    R_J_MOL_K, R_KPA_M3_MOL_K, R_L_BAR_MOL_K, R_CAL_MOL_K,
    T_STD_K, P_STD_PA, G_STD, MM,
)
from .units import Quantity, convert
from .solver import newton_raphson, broyden, solve_sparse, SolveResult
from .convergence import wegstein, ConvergenceReport

__all__ = [
    "R_J_MOL_K", "R_KPA_M3_MOL_K", "R_L_BAR_MOL_K", "R_CAL_MOL_K",
    "T_STD_K", "P_STD_PA", "G_STD", "MM",
    "Quantity", "convert",
    "newton_raphson", "broyden", "solve_sparse", "SolveResult",
    "wegstein", "ConvergenceReport",
]