"""Pacote Solvents: interface base e solventes físicos/químicos."""
from .base import Solvent
from .DEA import DEASolvent
from .KentEisenberg import KentEisenberg
from .MDEA import MDEASolvent
from .MEA import MEASolvent
from .Rectisol import RectisolSolvent
from .Selexol import SelexolSolvent
from .Water import WaterSolvent

__all__ = [
    "Solvent",
    "WaterSolvent", "MEASolvent", "KentEisenberg",
    "DEASolvent", "MDEASolvent",
    "SelexolSolvent", "RectisolSolvent",
]
