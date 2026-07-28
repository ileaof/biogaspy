"""Pacote Solvents: interface base e solventes físicos/químicos."""
from .base import Solvent
from .Water import WaterSolvent
from .MEA import MEASolvent
from .KentEisenberg import KentEisenberg
from .DEA import DEASolvent
from .MDEA import MDEASolvent
from .Selexol import SelexolSolvent
from .Rectisol import RectisolSolvent

__all__ = [
    "Solvent",
    "WaterSolvent", "MEASolvent", "KentEisenberg",
    "DEASolvent", "MDEASolvent",
    "SelexolSolvent", "RectisolSolvent",
]