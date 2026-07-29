"""Stripper (regeneração de solvente).

Reusa o motor de estágios do Absorbedor: a configuração é a mesma (líquido
entra no topo, gás entra na base), porém a alta temperatura torna as constantes
de equilíbrio grandes -> o CO2 desorve para a fase vapor (gás ácido no topo,
solvente magro na base). O ``steam`` (vapor de água) é usado como gás de
arraste na base.
"""
from __future__ import annotations

from .Absorber import Absorber, AbsorberResult, AbsorberSpec
from .base import Stream


def strip(loaded_solvent: Stream, solvent, steam: Stream, N_stages: int = 8,
          T_stripper: float = 393.15, P: float = 1.8e5,
          packing: str = "Pall_50") -> AbsorberResult:
    """Regenera solvente carregado.

    ``loaded_solvent``: corrente líquida rica em CO2 (topo).
    ``steam``: vapor de água na base (gás de arraste).
    """
    spec = AbsorberSpec(N_stages=N_stages, packing=packing, mode="isothermal",
                        T_op=T_stripper, pressure=P)
    col = Absorber(steam, loaded_solvent, solvent, spec)
    return col.solve()


__all__ = ["strip"]
