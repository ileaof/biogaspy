"""Banco de dados de recheios (random e estruturados).

Cada recheio traz, além da área específica ``a``, fração de vazio ``ε`` e fator
de recheio (úmido) ``Fp`` (1/m), as constantes de fricção ``C1, C2, C3`` do modelo
de Stichlmair-Bravo-Fair (1989) para o fator de atrito de partícula única
``Ψ0 = C1/Re + C2/√Re + C3`` -- usadas em ``PressureDrop``.

Fatores ``Fp`` e constantes ``C*`` são valores típicos de literatura (Billet,
*Packed Towers*; Kister, *Distillation Design*; Stichlmair et al. 1989 para
estruturados). Validar contra dados de fornecedor antes de projeto final.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Packing:
    name: str
    type: str                # "random" | "structured" | "sheet"
    specific_area: float     # a, m²/m³
    void_fraction: float     # ε
    packing_factor: float    # Fp (úmido), 1/m
    nominal_size: float = 0.05      # m
    # constantes de Stichlmair do fator de atrito Ψ0 = C1/Re + C2/√Re + C3
    C1: float = 4.0
    C2: float = 2.0
    C3: float = 0.4


PACKINGS: Dict[str, Packing] = {
    # -- random: Raschig / Pall / Intalox (Billet, Kister) --
    "Raschig_25":  Packing("Raschig ring 25mm",  "random", 190.0, 0.73, 500.0, 0.025, 8.0, 4.0, 0.50),
    "Raschig_50":  Packing("Raschig ring 50mm",  "random",  95.0, 0.78, 210.0, 0.050, 8.0, 4.0, 0.50),
    "Pall_25":     Packing("Pall ring 25mm",      "random", 215.0, 0.94, 180.0, 0.025, 4.0, 2.0, 0.40),
    "Pall_38":     Packing("Pall ring 38mm",      "random", 130.0, 0.95,  98.0, 0.038, 4.0, 2.0, 0.40),
    "Pall_50":     Packing("Pall ring 50mm",      "random", 110.0, 0.96,  66.0, 0.050, 4.0, 2.0, 0.40),
    "Intalox_25":  Packing("IMTP 25",             "random", 205.0, 0.96, 135.0, 0.025, 3.5, 2.0, 0.35),
    "Intalox_50":  Packing("IMTP 50",             "random", 112.0, 0.97,  55.0, 0.050, 3.5, 2.0, 0.35),
    "Hilflow_50":  Packing("Hiflow ring 50mm",    "random", 110.0, 0.96,  50.0, 0.050, 3.0, 1.8, 0.35),
    # -- structured: Mellapak / Sulzer (Stichlmair et al. 1989; Sulzer data) --
    "Mellapak_125Y":  Packing("Mellapak 125Y",  "structured", 125.0, 0.98, 30.0, 0.020, 5.0, 3.0, 0.45),
    "Mellapak_250Y":  Packing("Mellapak 250Y",  "structured", 250.0, 0.97, 75.0, 0.020, 5.0, 3.0, 0.45),
    "Mellapak_350Y":  Packing("Mellapak 350Y",  "structured", 350.0, 0.96, 110.0, 0.018, 5.0, 3.0, 0.45),
    "Mellapak_250X":  Packing("Mellapak 250X",  "structured", 250.0, 0.97, 65.0, 0.020, 5.0, 3.0, 0.45),
    "Sulzer_BX":      Packing("Sulzer BX",      "structured", 500.0, 0.95, 210.0, 0.012, 5.0, 3.0, 0.40),
}


def get(name: str) -> Packing:
    if name not in PACKINGS:
        raise KeyError(f"Recheio '{name}' não cadastrado. Opções: {list(PACKINGS)}")
    return PACKINGS[name]


__all__ = ["Packing", "PACKINGS", "get"]