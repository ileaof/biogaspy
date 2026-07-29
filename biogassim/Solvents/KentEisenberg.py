"""Modelo de equilíbrio Kent-Eisenberg para sistemas amina-CO2-H2O.

Implementação generalizada do modelo de especiação de Kent & Eisenberg (1976),
válida para aminas primárias (MEA), secundárias (DEA) e terciárias (MDEA).
Resolve as equações de equilíbrio (protonação da amina, formação de carbamato
quando aplicável, hidratação do CO2, dissociação do bicarbonato/carbonato e
autoionização da água) junto com os balanços de massa e de cargas para obter a
pressão parcial de CO2 em função do carregamento α e da temperatura.

Para amina terciária (MDEA) usa-se ``log_beta2 = 0`` (sem carbamato): o CO2 é
absorvido apenas como bicarbonato/carbonato, via protonação da amina que catalisa
a hidratação do CO2.

Formulação em constantes de estabilidade aparentes (L/mol) com dependência T
via van't Hoff:
    ln K(T) = ln K_ref + (dH/R) (1/T_ref - 1/T)
Para MEA, β2 é calibrado contra Jou, Mather & Otto (1982) / Aronu et al. (2011).
DEA e MDEA usam pKa e constantes de carbamato de literatura; pCO2(α) absoluto
ainda não calibrado contra VLE de DEA/MDEA -- validar antes de projeto.

Espécies: amina (livre), aminaH+, carbamato- (se β2>0), CO2 (livre), HCO3-,
CO3²-, H+, OH-.
Equilíbrios:
    β1 = [aminaH+]  / ([amina][H+])      (protonação, L/mol)
    β2 = [carbamato]/ ([amina][CO2])     (carbamato, L/mol; 0 p/ MDEA)
    K4 = [H+][HCO3-] / [CO2]             (hidratação, mol/L)
    K5 = [H+][CO3²-] / [HCO3-]           (2a dissociação, mol/L)
    K6 = [H+][OH-]                       (Kw)
    K7 = [CO2] / p_CO2                   (Henry, mol/(L.atm))
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

R = 8.314                      # J/(mol.K)
T_REF = 298.15                 # K


@dataclass
class KentEisenberg:
    """Modelo Kent-Eisenberg genérico para amina-H2O-CO2.

    Defaults reproduzem p_CO2 vs α de Jou, Mather & Otto (1982) / Aronu (2011)
    para MEA 30% mássico dentro de ~25% (ver tests/test_validation.py). Para
    DEA/MDEA instanciar com as constantes próprias (ver ``DEA.py``/``MDEA.py``).
    """
    amine: str = "MEA"
    log_beta1: float = 10.50           # protonação (aparente, calibrado)
    log_beta2: float = 4.95            # carbamato (aparente, L/mol); 0 p/ MDEA
    dH1: float = -35000.0              # J/mol (protonação exotérmica)
    dH2: float = -60000.0              # J/mol (carbamato exotérmico)
    pK4: float = 6.35                  # carbônico pK1
    pK5: float = 10.33                 # carbônico pK2
    pKw: float = 14.0
    K7_ref: float = 0.034             # mol/(L.atm) Henry CO2 a 25°C
    dH4: float = 8000.0
    dH5: float = 14000.0
    dH6: float = 55000.0
    dH7: float = -20000.0             # solubilidade física exotérmica

    # ------------------------------------------------------------------ #
    def _K(self, T: float) -> tuple[float, float, float, float, float, float]:
        vH = lambda dH: (dH / R) * (1.0 / T_REF - 1.0 / T)
        beta1 = 10.0 ** self.log_beta1 * np.exp(vH(self.dH1))
        beta2 = (10.0 ** self.log_beta2 * np.exp(vH(self.dH2))
                 if self.log_beta2 > 0 else 0.0)
        K4 = 10.0 ** (-self.pK4) * np.exp(vH(self.dH4))
        K5 = 10.0 ** (-self.pK5) * np.exp(vH(self.dH5))
        K6 = 10.0 ** (-self.pKw) * np.exp(vH(self.dH6))
        K7 = self.K7_ref * np.exp(vH(self.dH7))
        return beta1, beta2, K4, K5, K6, K7

    def _residual(self, ln_x, alpha, T, m, Ks):
        """Resíduo (F_co2, F_charge) nas incógnitas ln_x = (ln h, ln A).

        Escala logarítmica garante h, A > 0 e melhora o condicionamento.
        """
        beta1, beta2, K4, K5, K6, K7 = Ks
        h = np.exp(ln_x[0])
        A = np.exp(ln_x[1])
        c = alpha * m
        denom = 1.0 + beta1 * h + beta2 * A
        M = m / denom                       # [amina] livre
        amineH = beta1 * M * h
        carbamate = beta2 * M * A
        hco3 = K4 * A / h
        co3 = K4 * K5 * A / h ** 2
        oh = K6 / h
        F_co2 = A + hco3 + co3 + carbamate - c
        F_charge = h + amineH - oh - carbamate - hco3 - 2.0 * co3
        return np.array([F_co2, F_charge])

    def solve_speciation(self, alpha: float, T: float, m: float,
                         max_iter: int = 100, tol: float = 1e-12) -> dict:
        """Resolve a especiação para carregamento alpha, T (K) e amina total m
        (mol/L). Retorna dicionário com concentrações e p_CO2."""
        Ks = self._K(T)
        ln_x = np.array([np.log(1e-8), np.log(max(alpha * m * 1e-3, 1e-10))])
        F = self._residual(ln_x, alpha, T, m, Ks)
        for _ in range(max_iter):
            if np.linalg.norm(F) <= tol:
                break
            eps = 1e-6
            J = np.zeros((2, 2))
            for k in range(2):
                xp = ln_x.copy()
                xp[k] += eps * max(1.0, abs(ln_x[k]))
                Fp = self._residual(xp, alpha, T, m, Ks)
                J[:, k] = (Fp - F) / (eps * max(1.0, abs(ln_x[k])))
            try:
                dln = np.linalg.solve(J, -F)
            except np.linalg.LinAlgError:
                dln = -F
            dln = np.clip(dln, -2.0, 2.0)
            ln_x = ln_x + dln
            F = self._residual(ln_x, alpha, T, m, Ks)
        beta1, beta2, K4, K5, K6, K7 = Ks
        h = np.exp(ln_x[0])
        A = np.exp(ln_x[1])
        denom = 1.0 + beta1 * h + beta2 * A
        M = m / denom
        spec = {
            "amine": self.amine, "Amine": M,
            "AmineH": beta1 * M * h, "Carbamate": beta2 * M * A,
            "H": h, "OH": K6 / h,
            "CO2_free": A, "HCO3": K4 * A / h, "CO3": K4 * K5 * A / h ** 2,
            "pCO2_atm": A / K7, "converged": np.linalg.norm(F) <= tol * 100,
        }
        spec["pCO2_Pa"] = spec["pCO2_atm"] * 101325.0
        return spec

    def pCO2(self, alpha: float, T: float, m: float) -> float:
        """Pressão parcial de CO2 (Pa) para carregamento alpha a T e m."""
        if alpha <= 0:
            return 0.0
        return float(self.solve_speciation(alpha, T, m)["pCO2_Pa"])


__all__ = ["KentEisenberg"]
