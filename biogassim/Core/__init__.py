"""Pacote Core do BioGasSim: constantes, unidades, solver e convergência."""
from .constants import (
    G_STD,
    MM,
    P_STD_PA,
    R_CAL_MOL_K,
    R_J_MOL_K,
    R_KPA_M3_MOL_K,
    R_L_BAR_MOL_K,
    T_STD_K,
)
from .convergence import ConvergenceReport, wegstein
from .solver import SolveResult, broyden, newton_raphson, solve_sparse
from .units import Quantity, convert

__all__ = [
    "R_J_MOL_K", "R_KPA_M3_MOL_K", "R_L_BAR_MOL_K", "R_CAL_MOL_K",
    "T_STD_K", "P_STD_PA", "G_STD", "MM",
    "Quantity", "convert",
    "newton_raphson", "broyden", "solve_sparse", "SolveResult",
    "wegstein", "ConvergenceReport",
]
