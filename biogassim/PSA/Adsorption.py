"""Adsorção -- isoteras e modelo de leito fixo (PSA).

Implementa isoteras de Langmuir/Toth e um modelo simplificado de leito fixo
para estimativa preliminar de PSA. O ciclo PSA/VPSA completo (Skarstrom,
múltiplos leitos, pressurização, blowdown) é deixado como extensão futura
(ver ROADMAP).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Langmuir:
    """Isotera de Langmuir: q = qmax * b * p / (1 + b * p)."""
    qmax: float          # mol/kg
    b: float             # 1/Pa
    qmax_units: str = "mol/kg"

    def q(self, p: float, T: float = 298.15) -> float:
        # dependência T: b = b0 exp(-dH/RT) (adsorção exotérmica -> b cai com T)
        return float(self.qmax * self.b * p / (1.0 + self.b * p))


@dataclass
class Toth:
    """Isotera de Toth (heterogênea): q = qmax * b p / (1 + (b p)^t)^(1/t)."""
    qmax: float
    b: float
    t: float = 0.8

    def q(self, p: float, T: float = 298.15) -> float:
        bp = self.b * p
        return float(self.qmax * bp / (1.0 + bp ** self.t) ** (1.0 / self.t))


# Parâmetros de adsorção típicos (CO2 e CH4 em zeólita 13X e carvão ativado).
# Valores de referência; validar antes de projeto.
ADSORBENTS: dict[str, dict[str, Langmuir]] = {
    "Zeolite_13X": {
        "CO2": Langmuir(4.5, 1.2e-5),
        "CH4": Langmuir(2.5, 3.0e-7),
        "N2":  Langmuir(2.0, 1.0e-7),
    },
    "ActivatedCarbon": {
        "CO2": Langmuir(3.8, 8.0e-6),
        "CH4": Langmuir(2.0, 1.2e-6),
        "N2":  Langmuir(1.5, 5.0e-7),
    },
}


def selectivity(adsorbent: str, species_a: str, species_b: str,
                p: float, T: float = 298.15) -> float:
    """Seletividade α = (q_a/p_a)/(q_b/p_b) ~ (qmax_a b_a)/(qmax_b b_b) em baixa p."""
    iso = ADSORBENTS[adsorbent]
    qa = iso[species_a].q(p, T)
    qb = iso[species_b].q(p, T)
    return float((qa / p) / (qb / p)) if p > 0 else float("inf")


@dataclass
class FixedBedResult:
    breakthrough_time: float = 0.0
    capacity: float = 0.0
    message: str = ""


def fixed_bed_simple(adsorbent: str, y_in: dict, P: float, T: float,
                     bed_mass: float, flow: float) -> FixedBedResult:
    """Modelo simplificado de leito fixo: tempo de ruptura por capacidade de equilíbrio.

    ``y_in``: frações molares; ``bed_mass``: massa de adsorvente (kg);
    ``flow``: vazão total (mol/s). Estima o tempo até saturação do CO2.
    """
    iso = ADSORBENTS[adsorbent]
    p_co2 = y_in.get("CO2", 0.0) * P
    q_co2 = iso["CO2"].q(p_co2, T)             # mol/kg
    capacity = q_co2 * bed_mass                 # mol
    co2_in = flow * y_in.get("CO2", 0.0)
    t_break = capacity / max(co2_in, 1e-12)
    return FixedBedResult(breakthrough_time=t_break, capacity=capacity,
                          message="Modelo de equilíbrio (sem difusão/ciclo PSA completo).")


__all__ = ["Langmuir", "Toth", "ADSORBENTS", "selectivity", "FixedBedResult",
           "fixed_bed_simple"]
