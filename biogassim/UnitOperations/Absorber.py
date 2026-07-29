"""Absorvedor de pratos/recheio -- modelo de estágios de equilíbrio.

Implementa o método da matriz tridiagonal sobre fluxos molares por componente
(Thiele-Geddes / método theta com atualização de vazões totais). O equilíbrio
gás-líquido é fornecido por um objeto ``Solvent`` (lei de Henry para lavagem
física; equilíbrio efetivo para aminas). Inclui balanço de energia por estágio
opcional (default: isotérmico, mais robusto) e cálculo de transferência de
massa/hidráulica para dimensionamento (HTU/NTU, KLa, eficiência).

Convenção de estágios: 1 = topo (entra solvente, sai gás purificado), N = base
(entra biogás, sai líquido carregado).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..Core.solver import newton_raphson
from ..Hydraulics import (
    column_diameter,
    flooding_velocity,
    get_packing,
    operating_velocity,
    wet_pressure_drop,
)
from ..MassTransfer import (
    NTU_absorber,
    stage_efficiency,
)
from .base import Stream, UnitResult


@dataclass
class AbsorberSpec:
    N_stages: int = 10
    packing: str = "Pall_50"
    diameter: float | None = None       # m (se None, calculado)
    height: float | None = None        # m
    mode: str = "isothermal"              # "isothermal" | "adiabatic"
    T_op: float | None = None          # K (modo isotérmico); se None usa T do gás
    pressure: float | None = None       # Pa (topo); perda de carga aplicada por estágio
    max_iter: int = 120
    tol: float = 1.0e-7
    method: str = "newton"                # "newton" (global, robusto) | "ss" (substituição sucessiva)


@dataclass
class AbsorberResult(UnitResult):
    N_stages: int = 0
    L_profile: np.ndarray = field(default_factory=lambda: np.array([]))   # mol/s por estágio (líquido que desce)
    V_profile: np.ndarray = field(default_factory=lambda: np.array([]))   # mol/s por estágio (vapor que sobe)
    x_profile: np.ndarray = field(default_factory=lambda: np.array([]))   # (N, ncomp)
    y_profile: np.ndarray = field(default_factory=lambda: np.array([]))
    T_profile: np.ndarray = field(default_factory=lambda: np.array([]))
    K_profile: np.ndarray = field(default_factory=lambda: np.array([]))
    gas_out: Stream | None = None
    liquid_out: Stream | None = None
    # dimensionamento / transferência de massa
    diameter: float = 0.0
    height: float = 0.0
    HTU: float = 0.0
    NTU: float = 0.0
    KLa: float = 0.0
    stage_efficiency: float = 0.0
    pressure_drop: float = 0.0
    # métricas de processo
    methane_recovery: float = 0.0
    methane_loss: float = 0.0
    CO2_removal: float = 0.0
    purity_CH4: float = 0.0
    residual_CO2: float = 0.0


class Absorber:
    """Absorvedor de estágios de equilíbrio."""

    def __init__(self, gas_in: Stream, solvent_in: Stream, solvent,
                 spec: AbsorberSpec):
        if gas_in.species != solvent_in.species:
            raise ValueError("Gas e solvente devem ter a mesma lista de espécies.")
        self.gas_in = gas_in
        self.solvent_in = solvent_in
        self.solvent = solvent            # objeto Solvent (fornece K, calor, propriedades)
        self.spec = spec
        self.species = gas_in.species
        self.ncomp = len(self.species)
        self.N = spec.N_stages
        # índices
        self.solvent_idx = self.species.index(solvent.name) if solvent.name in self.species else None
        self.gas_species_idx = [i for i, s in enumerate(self.species) if s != solvent.name]
        # espécies voláteis (absorvidas, K>0) vs não-voláteis (K=0, fluxo fixo = magro)
        self._vol_idx = [i for i, s in enumerate(self.species) if solvent.is_absorbed(s)]
        self._nonvol_idx = [i for i, s in enumerate(self.species) if not solvent.is_absorbed(s)]
        # alguns solventes (ex.: MEA em modo Kent-Eisenberg) precisam do
        # contexto de espécies para resolver índices internos.
        if hasattr(solvent, "set_species_context"):
            solvent.set_species_context(self.species)

    # ------------------------------------------------------------------ #
    def _K_matrix(self, T_profile: np.ndarray, P_profile: np.ndarray,
                  x_profile: np.ndarray) -> np.ndarray:
        """K_{i,j} para cada componente i e estágio j.

        Espécies fora de ``solvent.absorbed_species`` são não-voláteis (K=0).
        Para solventes reativos (amina), o carregamento α = x_CO2/x_amina é
        calculado e repassado ao solvente.
        """
        K = np.zeros((self.ncomp, self.N))
        amine_idx = (self.species.index(self.solvent.amine_name)
                     if self.solvent.amine_name and self.solvent.amine_name in self.species
                     else None)
        co2_idx = self._co2_idx() if self._has_co2() else None
        for j in range(self.N):
            xj = x_profile[:, j]
            loading = 0.0
            if co2_idx is not None and amine_idx is not None:
                xmea = max(xj[amine_idx], 1e-12)
                loading = float(xj[co2_idx] / xmea)
            for i in range(self.ncomp):
                sp = self.species[i]
                if not self.solvent.is_absorbed(sp):
                    K[i, j] = 0.0
                else:
                    K[i, j] = self.solvent.K_value(sp, T_profile[j], P_profile[j],
                                                   xj, loading=loading)
        return K

    def _has_co2(self) -> bool:
        return "CO2" in self.species

    def _co2_idx(self) -> int:
        return self.species.index("CO2")

    def _solve_component_tridiag(self, l_lean: np.ndarray, v_feed: np.ndarray,
                                 R: np.ndarray) -> np.ndarray:
        """Resolve o sistema tridiagonal por componente.

        ``R`` é (ncomp, N): R_{i,j} = V_j K_{i,j} / L_j.
        Retorna ``l`` (ncomp, N): fluxo molar líquido por componente e estágio.
        """
        N = self.N
        l = np.zeros((self.ncomp, N))
        for i in range(self.ncomp):
            # diagonal principal B_j = -(1 + R_{i,j}); lower A=1, upper C=R_{i,j+1}
            main = -(1.0 + R[i, :])
            lower = np.ones(N)            # coef de l_{j-1}
            upper = np.zeros(N)           # coef de l_{j+1}
            rhs = np.zeros(N)
            upper[:-1] = R[i, 1:N]        # C_j = R_{i,j+1} para j=1..N-1
            # boundary
            rhs[0] = -l_lean[i]           # estágio 1: l_lean entra
            rhs[-1] = -v_feed[i]          # estágio N: v_feed entra
            l[i, :] = _thomas(lower, main, upper, rhs)
        return l

    # ------------------------------------------------------------------ #
    def solve(self) -> AbsorberResult:
        s = self.spec
        N = self.N
        T = np.full(N, s.T_op or self.gas_in.T)
        P_top = s.pressure or self.gas_in.P
        P = np.full(N, P_top)
        res = AbsorberResult(converged=False, iterations=0, N_stages=N)

        if s.method == "ss":
            state = self._ss_core(T, P, max_iter=s.max_iter, tol=s.tol, relax=0.5, polish=True)
            res.converged = state["converged"]
            res.iterations = state["iters"]
            res.message = state.get("message", "")
            return self._finalize(res, state, s)

        # --- método padrão: Newton global ---
        if s.mode == "adiabatic":
            state, ok, iters = self._solve_adiabatic(T, P)
            res.converged = ok
            res.iterations = iters
            if not ok:
                res.message = "Laço MESH<->energia não convergiu (resultado aproximado)."
            return self._finalize(res, state, s)

        state = self._solve_mesh(T, P)
        res.converged = state["converged"]
        res.iterations = state["iters"]
        if not state["converged"]:
            res.message = "Newton não convergiu (resultado aproximado)."
        return self._finalize(res, state, s)

    # ------------------------------------------------------------------ #
    def _solve_mesh(self, T, P) -> dict:
        """Resolve o MESH (balanço por componente + equilíbrio) a T fixo:
        aquecimento por substituição sucessiva (isotérmico) seguido de
        Newton-Raphson sobre o resíduo consistente."""
        s = self.spec
        warm = self._ss_core(T, P, max_iter=min(s.max_iter, 40),
                             tol=max(s.tol, 1.0e-4), relax=0.7, polish=False, fix_T=True)
        l_warm = warm["l"]
        T_w, P_w = warm["T"], warm["P"]
        if self._vol_idx:
            l_vol0 = np.array([l_warm[i, :] for i in self._vol_idx]).ravel()
            sol = newton_raphson(lambda x: self._newton_residual(x, T_w, P_w),
                                 l_vol0, max_iter=s.max_iter, tol=s.tol, damp=1.0)
            l, L, V, x, K, y, v = self._flows_from_l_vol(sol.x, T_w, P_w)
            conv = sol.converged
            niter = sol.report.iterations
        else:
            l, v, L, V, x, y, K = (warm[k] for k in ("l", "v", "L", "V", "x", "y", "K"))
            conv, niter = True, 0
        return dict(l=l, v=v, L=L, V=V, x=x, y=y, K=K, T=T_w, P=P_w,
                    iters=warm["iters"] + niter, converged=conv)

    def _solve_adiabatic(self, T, P, max_outer: int = 40, tol_T: float = 0.05):
        """Laço externo MESH<->energia para o modo adiabático.

        Em cada iteração: (1) resolve o MESH a T fixo (Newton global);
        (2) resolve o balanço de entalpia por estágio (sistema tridiagonal
        em T) com o calor de absorção liberado -> novo perfil T; repete até
        T convergir (amortecido)."""
        T = T.copy()
        total_iters = 0
        state = self._solve_mesh(T, P)
        for _outer in range(1, max_outer + 1):
            total_iters += state["iters"]
            T_new = self._energy_tridiag(state, T)
            dT = float(np.max(np.abs(T_new - T)))
            T = 0.5 * T + 0.5 * T_new           # amortecimento
            state = self._solve_mesh(T, P)
            if dT < tol_T:
                total_iters += state["iters"]
                return state, True, total_iters
        total_iters += state["iters"]
        return state, False, total_iters

    # ------------------------------------------------------------------ #
    def _ss_core(self, T, P, max_iter, tol, relax=0.5, polish=True, fix_T=False) -> dict:
        """Núcleo de substituição sucessiva (matriz tridiagonal por componente).

        Retorna o estado completo (l, v, L, V, x, y, K, T, P) e flags de
        convergência. Usado tanto como método ``ss`` quanto como aquecimento
        para o Newton global. ``fix_T=True`` mantém T constante (sem balanço
        de energia) -- usado no laço externo MESH<->energia do modo adiabático.
        """
        N = self.N
        V0 = self.gas_in.flow
        L0 = self.solvent_in.flow
        V = np.full(N, V0)
        L = np.full(N, L0)
        x = np.tile(self.solvent_in.z, (N, 1)).T
        K = self._K_matrix(T, P, x)
        l_prev = None
        l = None
        d_prev = np.inf
        iters = 0
        converged = False
        for it in range(1, max_iter + 1):
            iters = it
            R = np.zeros((self.ncomp, N))
            for j in range(N):
                Lj = max(L[j], 1e-9)
                for i in range(self.ncomp):
                    R[i, j] = V[j] * K[i, j] / Lj
            l_lean = self.solvent_in.z * L0
            v_feed = self.gas_in.z * V0
            l_new = self._solve_component_tridiag(l_lean, v_feed, R)
            l_new = np.clip(l_new, 0.0, None)
            if l is None:
                l = l_new.copy()
            else:
                delta = l_new - l
                step_norm = float(np.max(np.abs(delta)))
                max_step = 2.0 * max(float(np.max(np.abs(l))), 1.0)
                if step_norm > max_step and step_norm > 0:
                    delta = delta * (max_step / step_norm)
                l = l + relax * delta
            v = R * l
            L = l.sum(axis=0)
            V = v.sum(axis=0)
            x = l / np.maximum(L, 1e-12)
            y_new = v / np.maximum(V, 1e-12)
            if self.spec.mode == "adiabatic" and not fix_T:
                T = self._energy_balance(l, v, x, y_new, L, V, T, P)
            K = self._K_matrix(T, P, x)
            if l_prev is not None:
                d = np.max(np.abs(l - l_prev)) / max(np.max(np.abs(l_prev)), 1e-12)
                if d < tol:
                    converged = True
                    break
                if d > d_prev * 1.5 and relax > 0.1:
                    relax = max(relax * 0.5, 0.1)
                d_prev = d
            l_prev = l.copy()

        # passo de polimento (sem amortecimento) para fechar balanço de massa
        if polish:
            R = np.zeros((self.ncomp, N))
            for j in range(N):
                Lj = max(L[j], 1e-9)
                for i in range(self.ncomp):
                    R[i, j] = V[j] * K[i, j] / Lj
            l_lean = self.solvent_in.z * L0
            v_feed = self.gas_in.z * V0
            l = np.clip(self._solve_component_tridiag(l_lean, v_feed, R), 0.0, None)
            v = R * l
            L = l.sum(axis=0)
            V = v.sum(axis=0)
            x = l / np.maximum(L, 1e-12)
            y_new = v / np.maximum(V, 1e-12)
            K = self._K_matrix(T, P, x)

        return dict(l=l, v=v, L=L, V=V, x=x, y=y_new, K=K, T=T, P=P,
                    iters=iters, converged=converged,
                    message="" if converged else "Iteração máxima atingida (resultado aproximado).")

    # ------------------------------------------------------------------ #
    def _flows_from_l_vol(self, l_vol_flat, T, P):
        """Reconstrói os perfis completos a partir dos fluxos das espécies
        voláteis. Espécies não-voláteis têm fluxo fixo = magro (K=0). As
        vazões totais V_j vêm do balanço de massa total por estágio:
            V_j = V_feed + L_{j-1} - L_N   (L_0 = solvente magro)
        de modo que o balanço total fecha por construção (sem singularidade).
        """
        nv = len(self._vol_idx)
        l_vol = np.clip(np.asarray(l_vol_flat, dtype=float).reshape(nv, self.N), 0.0, None)
        l = np.empty((self.ncomp, self.N))
        l_lean = self.solvent_in.z * self.solvent_in.flow
        for i in self._nonvol_idx:
            l[i, :] = l_lean[i]
        for k, i in enumerate(self._vol_idx):
            l[i, :] = l_vol[k, :]
        L = l.sum(axis=0)
        L0 = self.solvent_in.flow
        Vfeed = self.gas_in.flow
        L_prev = np.concatenate(([L0], L[:-1]))
        V = np.maximum(Vfeed + L_prev - L[-1], 1e-9)
        x = l / np.maximum(L, 1e-12)
        K = self._K_matrix(T, P, x)
        y = K * x
        v = y * V[None, :]
        return l, L, V, x, K, y, v

    def _newton_residual(self, l_vol_flat, T, P) -> np.ndarray:
        """Resíduo MESH consistente para as espécies voláteis.

        F_{i,j} = v_{i,j+1} + l_{i,j-1} - v_{i,j} - l_{i,j} = 0,
        com l_{i,0}=l_lean e v_{i,N+1}=v_feed (fronteiras). As espécies
        não-voláteis (K=0) têm fluxo constante = magro e não aparecem como
        incógnitas, eliminando a dependência linear (singularidade) que
        surgiria se o balanço de todas as espécies fosse incluído.
        """
        l, L, V, x, K, y, v = self._flows_from_l_vol(l_vol_flat, T, P)
        l_lean = self.solvent_in.z * self.solvent_in.flow
        v_feed = self.gas_in.z * self.gas_in.flow
        nv = len(self._vol_idx)
        F = np.empty((nv, self.N))
        for k, i in enumerate(self._vol_idx):
            li = l[i, :]
            vi = v[i, :]
            lprev = np.empty(self.N)
            lprev[0] = l_lean[i]
            lprev[1:] = li[:-1]
            vnext = np.empty(self.N)
            vnext[-1] = v_feed[i]
            vnext[:-1] = vi[1:]
            F[k, :] = vnext + lprev - vi - li
        return F.ravel()

    # ------------------------------------------------------------------ #
    def _cp_vapor(self, y, T) -> np.ndarray:
        """Cp da fase vapor por estágio (J/(mol·K)) -- mistura ideal gás."""
        N = self.N
        cp = np.zeros(N)
        for j in range(N):
            c = 0.0
            for i in range(self.ncomp):
                if y[i, j] > 0:
                    c += y[i, j] * self._comp_cp(self.species[i], T[j])
            cp[j] = c if c > 0 else 35.0   # fallback
        return cp

    def _comp_cp(self, name: str, T: float) -> float:
        from ..Properties.components import get as get_comp
        return get_comp(name).cp(T)

    def _energy_tridiag(self, state: dict, T: np.ndarray) -> np.ndarray:
        """Balanço de entalpia por estágio -- resolve o perfil de temperatura.

        Para cada estágio j (T_ref = 0):
            V_{j+1} cp_v T_{j+1} + L_{j-1} cp_l T_{j-1}
              - (V_j cp_v + L_j cp_l) T_j + Q_j = 0
        onde Q_j = somatório (espécie absorvida no estágio j)·(-ΔH_abs) é o
        calor liberado pela absorção (exotérmica -> fonte de calor). Sistema
        tridiagonal em T_1..T_N, resolvido pelo algoritmo de Thomas.

        Fronteiras: L_0 entra a T_lean (solvente magro); V_{N+1} entra a
        T_gas (biogás) -- ambos conhecidos, vão para o lado direito.
        """
        N = self.N
        v = state["v"]; L = state["L"]; V = state["V"]
        y = state["y"]
        cp_v = self._cp_vapor(y, T)
        cp_l = np.array([self.solvent.cp_liquid(T[j]) for j in range(N)])
        # calor de absorção liberado por estágio (Q_j > 0)
        v_feed = self.gas_in.z * self.gas_in.flow
        Q = np.zeros(N)
        for i in self._vol_idx:
            sp = self.species[i]
            Habs = self.solvent.heat_of_absorption(sp)
            for j in range(N):
                v_in = v[i, j + 1] if j + 1 < N else v_feed[i]
                v_out = v[i, j]
                absorbed = max(v_in - v_out, 0.0)
                Q[j] += absorbed * Habs
        # montagem do tridiagonal
        lower = np.zeros(N)
        main = np.zeros(N)
        upper = np.zeros(N)
        rhs = -Q.copy()
        T_lean = self.solvent_in.T
        T_gas = self.gas_in.T
        L0 = self.solvent_in.flow
        Vfeed = self.gas_in.flow
        for j in range(N):
            main[j] = -(V[j] * cp_v[j] + L[j] * cp_l[j])
            if j > 0:
                lower[j] = L[j - 1] * cp_l[j - 1]
            if j < N - 1:
                upper[j] = V[j + 1] * cp_v[j + 1]
        # fronteira topo (estágio 1): L_0 cp_l T_lean -> RHS
        rhs[0] -= L0 * cp_l[0] * T_lean
        # fronteira base (estágio N): V_{N+1} cp_v T_gas -> RHS
        rhs[-1] -= Vfeed * cp_v[-1] * T_gas
        return _thomas(lower, main, upper, rhs)

    # ------------------------------------------------------------------ #
    def _finalize(self, res: AbsorberResult, state: dict, s: AbsorberSpec) -> AbsorberResult:
        """Constrói correntes de saída, perfis, métricas e dimensionamento."""
        L = state["L"]; V = state["V"]
        x = state["x"]; y = state["y"]; K = state["K"]
        T = state["T"]; P = state["P"]
        # correntes de saída
        y_top = y[:, 0]
        V_top = V[0]
        gas_out = Stream(list(self.species), float(V_top), y_top / max(y_top.sum(), 1e-12),
                         float(T[0]), float(P[0]), phase="vapor")
        x_bot = x[:, -1]
        L_bot = L[-1]
        liquid_out = Stream(list(self.species), float(L_bot), x_bot / max(x_bot.sum(), 1e-12),
                            float(T[-1]), float(P[-1]), phase="liquid")
        res.L_profile = L
        res.V_profile = V
        res.x_profile = x
        res.y_profile = y
        res.T_profile = T
        res.K_profile = K
        res.gas_out = gas_out
        res.liquid_out = liquid_out
        self._compute_metrics(res)
        self._design_and_masstransfer(res, T, P, L, V, x, y, K)
        return res

    # ------------------------------------------------------------------ #
    def _energy_balance(self, l, v, x, y, L, V, T, P) -> np.ndarray:
        """Atualiza temperatura por estágio via balanço de energia (CMO simplificado).

        Para cada estágio, a absorção de CO2 libera calor -> T sobe. Usa Cp
        médio da fase líquida e calor de absorção do solvente.
        """
        N = self.N
        T_new = T.copy()
        # calor acumulado por estágio: aproximado via fluxo absorvido vs gás
        for j in range(N):
            # CO2 absorvido no estágio = (v entra) - (v sai) -> usa vizinhos
            if self._has_co2():
                i = self._co2_idx()
                # diferença entre vapor que entra e sai neste estágio
                v_in = v[i, j + 1] if j + 1 < N else self.gas_in.z[i] * self.gas_in.flow
                v_out = v[i, j]
                absorbed = max(v_in - v_out, 0.0)
                H_abs = self.solvent.heat_of_absorption("CO2")
                # capacidade térmica da fase líquida (J/K) -- Cp_liq * L (aprox)
                cp_liq = self.solvent.cp_liquid(T[j])  # J/(mol·K) aproximado
                NL = max(L[j], 1e-9)
                dT = (absorbed * H_abs) / (NL * cp_liq + 1e-9)
                T_new[j] = T[j] + 0.5 * dT   # amortecido
        return T_new

    # ------------------------------------------------------------------ #
    def _compute_metrics(self, res: AbsorberResult) -> None:
        gi, go = self.gas_in, res.gas_out
        if "CH4" in self.species:
            i = self.species.index("CH4")
            ch4_in = gi.flow * gi.z[i]
            ch4_out = go.flow * go.z[i]
            res.methane_recovery = ch4_out / max(ch4_in, 1e-12)
            res.methane_loss = 1.0 - res.methane_recovery
            res.purity_CH4 = float(go.z[i])
        if "CO2" in self.species:
            i = self.species.index("CO2")
            co2_in = gi.flow * gi.z[i]
            co2_out = go.flow * go.z[i]
            res.CO2_removal = 1.0 - co2_out / max(co2_in, 1e-12)
            res.residual_CO2 = float(go.z[i])

    # ------------------------------------------------------------------ #
    def _design_and_masstransfer(self, res, T, P, L, V, x, y, K):
        s = self.spec
        packing = get_packing(s.packing)
        # densidades e viscosidades (fase gás -- mistura CH4/CO2 aprox; líquido -- solvente)
        rho_g = self.gas_in.P * np.mean([self._mm(c) for c in self.species]) / (8.314 * np.mean(T))
        rho_l = self.solvent.density(np.mean(T))
        mu_l = self.solvent.viscosity(np.mean(T))
        L_mass = L.mean() * self.solvent.molar_mass_liquid()
        G_mass = V.mean() * np.mean([self._mm(c) for c in self.species])
        L_over_G = L_mass / max(G_mass, 1e-9)
        u_flood = flooding_velocity(rho_g, rho_l, mu_l, packing, L_over_G)
        u_op = operating_velocity(u_flood, 0.7)
        if s.diameter is None:
            D = column_diameter(G_mass, rho_g, u_op)
        else:
            D = s.diameter
            u_op = G_mass / (rho_g * np.pi * D**2 / 4) if D > 0 else u_op
        res.diameter = D
        # perda de carga
        u_l = L_mass / (rho_l * np.pi * D**2 / 4) if D > 0 else 0.0
        res.pressure_drop = wet_pressure_drop(rho_l, rho_g, u_op, u_l, packing) * (s.height or 0.0)
        # NTU/HTU para CO2 (componente chave)
        if self._has_co2() and s.height:
            ic = self._co2_idx()
            y_in = self.gas_in.z[ic]            # base
            y_out = res.gas_out.z[ic]          # topo
            # equilíbrio na base e no topo (x -> y_eq = K x)
            y_eq_in = float(K[ic, -1] * x[ic, -1])
            y_eq_out = float(K[ic, 0] * x[ic, 0])
            res.NTU = NTU_absorber(y_in, y_out, y_eq_in, y_eq_out)
            res.HTU = s.height / res.NTU if res.NTU and np.isfinite(res.NTU) else 0.0
            # KLa global aproximado: KLa = G/area * NTU/Z (inf no pinch -> 0)
            area = np.pi * D**2 / 4
            if s.height and res.NTU and np.isfinite(res.NTU):
                res.KLa = (V.mean() / max(area, 1e-9)) * (res.NTU / s.height)
            else:
                res.KLa = 0.0
            res.height = s.height
            # eficiência de estágio (média)
            m = float(np.mean(K[ic, :]))
            res.stage_efficiency = stage_efficiency(m, L.mean(), V.mean(), 1.0, packing.specific_area,
                                                     s.height / max(self.N, 1))
        elif s.height:
            res.height = s.height

    def _mm(self, name: str) -> float:
        from ..Properties.components import get as get_comp
        return get_comp(name).MM


def _thomas(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Algoritmo de Thomas para sistema tridiagonal. a=lower, b=diag, c=upper."""
    n = d.size
    cp = np.zeros(n)
    dp = np.zeros(n)
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for k in range(1, n):
        m = b[k] - a[k] * cp[k - 1]
        if abs(m) < 1e-18:
            m = 1e-18 if m >= 0 else -1e-18
        cp[k] = c[k] / m
        dp[k] = (d[k] - a[k] * dp[k - 1]) / m
    x = np.zeros(n)
    x[-1] = dp[-1]
    for k in range(n - 2, -1, -1):
        x[k] = dp[k] - cp[k] * x[k + 1]
    return x


__all__ = ["Absorber", "AbsorberSpec", "AbsorberResult"]
