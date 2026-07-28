"""Regeneração de leito -- ciclo PSA/VPSA (stub com interface).

O ciclo Skarstrom completo (pressurização, adsorção em alta pressão,
blowdown, purga em baixa pressão) requer integração temporal e múltiplos
leitos. Aqui fornecemos a interface e um modelo de produtividade simplificado.
"""
from __future__ import annotations

from dataclasses import dataclass

from .Adsorption import ADSORBENTS


@dataclass
class PSACycle:
    adsorbent: str
    P_high: float          # Pa
    P_low: float           # Pa
    T: float = 298.15
    t_cycle: float = 60.0  # s (tempo de semi-ciclo)

    def purity_estimate(self, y_in: dict) -> dict:
        """Estimativa simplificada de pureza via seletividade de equilíbrio."""
        iso = ADSORBENTS[self.adsorbent]
        # razão de adsorção CO2/CH4 em P_high
        p = sum(y_in.values()) * 0  # não usado
        out = {}
        s = iso["CO2"].q(self.P_high * y_in.get("CO2", 0), self.T) / max(
            iso["CH4"].q(self.P_high * y_in.get("CH4", 0), self.T), 1e-12)
        # pureza de CH4 no produto de alta pressão (raffinate) aumenta com seletividade
        y_co2 = y_in.get("CO2", 0.0)
        y_ch4 = y_in.get("CH4", 0.0)
        # fração CO2 removida ~ 1 - 1/(1 + s)
        rem = 1.0 - 1.0 / (1.0 + 0.5 * s)
        rem = min(max(rem, 0.0), 0.99)
        co2_out = y_co2 * (1 - rem)
        ch4_out = y_ch4  # CH4 segue para o produto (raffinate)
        tot = co2_out + ch4_out
        out["CH4"] = ch4_out / max(tot, 1e-12)
        out["CO2"] = co2_out / max(tot, 1e-12)
        out["CO2_removal"] = rem
        out["message"] = ("Estimativa simplificada de equilíbrio. "
                          "Ciclo PSA dinâmico completo = ROADMAP.")
        return out


__all__ = ["PSACycle"]