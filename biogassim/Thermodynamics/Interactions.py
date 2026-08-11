"""Parâmetros de interação binária (kij) para equações de estado cúbicas.

Armazena os ``kij`` do modelo Peng-Robinson para os pares de gases relevantes
ao upgrading de biogás (CH4, CO2, H2S, N2, H2O, ...). Estes parâmetros corrigem
a regra de mistura quadrática ``a_ij = sqrt(a_i a_j)(1 - k_ij)`` e **não** devem
ser assumidos nulos -- pares polares/não-polares (CO2-H2S, CH4-H2O) desviam
fortemente de zero.

Fontes: Knapp & Dohrn (industrial PR kij tables), Prausnitz et al., correlations
de Reed-Kopp-Beattie/Matthias; valores típicos de simuladores comerciais
(HYSYS/PROII) para PR. Quando um par não está tabulado, usa-se 0.0 (mistura
aproximadamente geométrica).

O banco é um ``dict`` simétrico indexado por pares ordenados alfabeticamente,
de modo que ``kij_matrix(species)`` monta a matriz NxN para qualquer subconjunto.
"""
from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------------- #
# Banco de kij para Peng-Robinson (adimensional, simétrico).
# Chave: tupla ordenada alfabeticamente (A, B) -> k_AB = k_BA.
# Fontes: Knapp et al. (1991) / correlações de PR em uso industrial.
# --------------------------------------------------------------------------- #
KIJ_PR: dict[tuple[str, str], float] = {
    ("CH4", "CO2"): 0.0919,    # CH4-CO2 ~0.09 (comum em simuladores)
    ("CH4", "H2S"): 0.0825,    # CH4-H2S ~0.08
    ("CH4", "N2"):  0.0250,    # quase ideal
    ("CH4", "H2O"): 0.5000,    # metano-água: forte desvio (imiscibilidade)
    ("CH4", "H2"):  0.0300,
    ("CH4", "CO"):  0.0300,
    ("CH4", "O2"):  0.0200,
    ("CH4", "Ar"):  0.0200,
    ("CH4", "NH3"): 0.2500,
    ("CO2", "H2S"): 0.0974,    # CO2-H2S ~0.085-0.097 (ambos ácidos/polares)
    ("CO2", "N2"):  -0.0170,   # levemente negativo
    ("CO2", "H2O"): 0.1900,    # CO2-água ~0.19
    ("CO2", "H2"):  0.0800,
    ("CO2", "CO"):  0.0600,
    ("CO2", "O2"):  0.0500,
    ("CO2", "Ar"):  0.0500,
    ("CO2", "NH3"): 0.1500,
    ("H2S", "N2"):  0.0900,
    ("H2S", "H2O"): 0.1500,    # H2S-água ~0.15
    ("H2S", "H2"):  0.0800,
    ("H2S", "CO"):  0.0700,
    ("H2S", "O2"):  0.0600,
    ("H2S", "Ar"):  0.0600,
    ("H2S", "NH3"): 0.1700,
    ("N2", "H2O"):  0.5000,
    ("N2", "H2"):   0.0200,
    ("N2", "CO"):   0.0200,
    ("N2", "O2"):   0.0100,
    ("N2", "Ar"):   0.0200,
    ("N2", "NH3"):  0.2000,
    ("H2O", "H2"):  0.5000,
    ("H2O", "CO"):  0.2500,
    ("H2O", "O2"):  0.4000,
    ("H2O", "Ar"):  0.4000,
    ("H2O", "NH3"): 0.2500,
}


def _key(a: str, b: str) -> tuple[str, str]:
    """Chave simétrica canônica (ordem alfabética)."""
    return (a, b) if a <= b else (b, a)


def get_kij(a: str, b: str) -> float:
    """kij para o par (a, b). Simétrico; 0.0 se não tabulado."""
    if a == b:
        return 0.0
    return KIJ_PR.get(_key(a, b), 0.0)


def kij_matrix(species: list[str]) -> np.ndarray:
    """Matriz kij (NxN) para a lista de espécies (na ordem dada).

    Simétrica, diagonal nula. Usada para instanciar ``PengRobinson(..., kij=...)``
    e ``SRK(..., kij=...)``.
    """
    n = len(species)
    k = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            v = get_kij(species[i], species[j])
            k[i, j] = v
            k[j, i] = v
    return k


__all__ = ["KIJ_PR", "get_kij", "kij_matrix"]
