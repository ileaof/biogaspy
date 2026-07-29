"""Modelo de membrana -- solução-difusão (modelo de mistura completa).

Cada espécie permeia por ``N_i = Q_i · A · (x_i·P_feed - y_i·P_perm)``, onde
``Q_i = P_i / t`` é a **permeância** (permeabilidade / espessura da camada
seletiva), ``x_i`` a fração no lado do retentado e ``y_i`` no permeado. Um
estágio é resolvido pelo modelo de *mistura completa* (complete-mixing): dado
o feed, as pressões e a **área**, resolve-se o corte de estágio ``θ`` e as
composições de permeado/retentado de forma consistente com o balanço por
componente -- em vez de tomar ``θ`` como um dado fixo.

Configurações implementadas:

* :func:`single_stage`      -- um estágio.
    - modo *rating*  (``area`` dado)      -> resolve ``θ``.
    - modo *design*  (``stage_cut`` dado) -> resolve a **área** requerida.
* :func:`two_stage_recycle` -- dois estágios com reciclo do permeado, a
    configuração padrão para biometano: o retentado do estágio 1 é o produto
    (biometano), o permeado é reprocessado no estágio 2, cujo retentado (rico
    em CH₄) retorna à alimentação. O reciclo é resolvido por Wegstein.
* :func:`series_stages`     -- N estágios em série no retentado (sem reciclo):
    o retentado de cada estágio alimenta o próximo; os permeados são o rejeito.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..Core.convergence import wegstein
from .Permeability import MEMBRANES

DEFAULT_THICKNESS_UM = 1.0


@dataclass
class MembraneResult:
    """Resultado de um estágio de membrana."""
    permeate: dict[str, float]    # frações molares no permeado
    retentate: dict[str, float]   # frações no retentado (biometano)
    permeate_flow: float          # mol/s
    retentate_flow: float         # mol/s
    purity_CH4: float
    recovery_CH4: float
    CO2_removal: float
    area: float                   # m²
    stage_cut: float = 0.0        # θ = permeado/feed (resolvido)
    message: str = ""


@dataclass
class MembraneSystemResult:
    """Resultado de um sistema multi-estágio de membranas."""
    product: dict[str, float]     # composição do biometano (produto)
    offgas: dict[str, float]      # composição do gás de rejeito
    product_flow: float           # mol/s
    offgas_flow: float            # mol/s
    purity_CH4: float
    recovery_CH4: float
    CO2_removal: float
    total_area: float             # m² (soma dos estágios)
    stages: list = field(default_factory=list)   # MembraneResult por estágio
    recycle_flow: float = 0.0     # mol/s (0 se não houver reciclo)
    mass_balance_error: float = 0.0
    converged: bool = True
    iterations: int = 0
    message: str = ""


# --------------------------------------------------------------------------- #
# Núcleo: um estágio pelo modelo de mistura completa
# --------------------------------------------------------------------------- #
def _complete_mixing(z, F, P_f, P_p, Q, A):
    """Resolve um estágio de mistura completa (forma fechada + raiz 1-D em θ).

    Dado feed (fração ``z``, vazão ``F``), pressões ``P_f``/``P_p``, permeâncias
    ``Q`` e área ``A``, devolve ``(θ, y, x)`` com ``Σy = Σx = 1``.

    Para um dado ``θ``, o balanço por componente ``θ·F·y_i = a_i(x_i P_f -
    y_i P_p)`` com ``x_i = (z_i - θ y_i)/(1-θ)`` e ``a_i = Q_i·A`` resolve-se em
    forma **fechada**::

        y_i(θ) = a_i·P_f·z_i / [ θ·F·(1-θ) + a_i·(P_p + θ·(P_f - P_p)) ]

    O corte físico ``θ`` é a raiz de ``S(θ) = Σ y_i(θ) = 1`` (normalização do
    permeado ⇔ balanço global). ``S`` cai de ``P_f/P_p`` (θ→0) e o termo
    ``θF(1-θ)`` a puxa abaixo de 1 para áreas finitas, dando a raiz física; se
    ``S`` não cruza 1 (área enorme), ``θ→1`` (quase tudo permeia).
    """
    z = np.asarray(z, dtype=float)
    Q = np.asarray(Q, dtype=float)
    a = Q * A

    def y_of(theta):
        D = theta * F * (1.0 - theta) + a * (P_p + theta * (P_f - P_p))
        return a * P_f * z / np.maximum(D, 1e-300)

    if P_f <= P_p:                                # sem força motriz
        return 0.0, z.copy(), z.copy()

    grid = np.linspace(1e-6, 1.0 - 1e-6, 80)
    f = np.array([float(y_of(t).sum()) - 1.0 for t in grid])
    theta = None
    for k in range(grid.size - 1):               # primeira travessia + -> -
        if f[k] >= 0.0 and f[k + 1] < 0.0:
            lo, hi = grid[k], grid[k + 1]
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                fm = float(y_of(mid).sum()) - 1.0
                if abs(fm) < 1e-13 or (hi - lo) < 1e-14:
                    break
                lo, hi = (mid, hi) if fm > 0.0 else (lo, mid)
            theta = 0.5 * (lo + hi)
            break
    if theta is None:                            # sem travessia: quase-nada / quase-tudo
        theta = grid[0] if f[0] < 0.0 else grid[-1]

    y = y_of(theta)
    sy = float(y.sum())
    y = y / sy if sy > 0 else z.copy()
    x = (z - theta * y) / (1.0 - theta)
    x = np.clip(x, 0.0, None)
    sx = float(x.sum())
    x = x / sx if sx > 0 else z.copy()
    return float(theta), y, x


def _area_for_cut(z, F, P_f, P_p, Q, target_theta, tol=1e-4):
    """Bissecção na área para atingir um corte de estágio alvo (modo design)."""
    target = min(max(target_theta, 1e-6), 1.0 - 1e-6)

    def theta_of(A):
        th, _, _ = _complete_mixing(z, F, P_f, P_p, Q, A)
        return th

    lo, hi = 0.0, 1.0
    for _ in range(400):                         # cresce hi até cobrir o alvo
        if theta_of(hi) >= target:
            break
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        th = theta_of(mid)
        if abs(th - target) < tol:
            return mid
        if th < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _assemble_stage(species, z, F, theta, y, x, area, mode) -> MembraneResult:
    perm_flow = theta * F
    ret_flow = (1.0 - theta) * F
    res = MembraneResult(
        permeate=dict(zip(species, (float(v) for v in y))),
        retentate=dict(zip(species, (float(v) for v in x))),
        permeate_flow=float(perm_flow),
        retentate_flow=float(ret_flow),
        purity_CH4=0.0, recovery_CH4=0.0, CO2_removal=0.0,
        area=float(area), stage_cut=float(theta),
        message=f"Mistura completa (modo {mode}).",
    )
    if "CH4" in species:
        i = species.index("CH4")
        res.purity_CH4 = float(x[i])
        res.recovery_CH4 = float(x[i] * ret_flow / max(z[i] * F, 1e-12))
    if "CO2" in species:
        j = species.index("CO2")
        res.CO2_removal = 1.0 - float(x[j] * ret_flow / max(z[j] * F, 1e-12))
    return res


def single_stage(material: str, feed_species: list[str], z_feed: np.ndarray,
                 feed_flow: float, T: float, P_feed: float, P_permeate: float,
                 area: float | None = None, stage_cut: float | None = None,
                 thickness_um: float = DEFAULT_THICKNESS_UM) -> MembraneResult:
    """Membrana de um estágio (mistura completa, solução-difusão).

    Forneça ``area`` (modo *rating*: resolve ``θ``) **ou** ``stage_cut`` (modo
    *design*: resolve a área requerida para esse corte). Se nenhum for dado,
    projeta-se para ``θ = 0.5``. Se ambos forem dados, ``area`` prevalece.
    """
    m = MEMBRANES[material]
    z = np.asarray(z_feed, dtype=float)
    z = z / z.sum()
    Q = np.array([m.permeance_si(s, thickness_um) for s in feed_species])

    if area is None and stage_cut is None:
        stage_cut = 0.5
    if area is not None:
        theta, y, x = _complete_mixing(z, feed_flow, P_feed, P_permeate, Q, area)
        return _assemble_stage(feed_species, z, feed_flow, theta, y, x, area, "rating")
    A = _area_for_cut(z, feed_flow, P_feed, P_permeate, Q, stage_cut)
    theta, y, x = _complete_mixing(z, feed_flow, P_feed, P_permeate, Q, A)
    return _assemble_stage(feed_species, z, feed_flow, theta, y, x, A, "design")


# --------------------------------------------------------------------------- #
# Multi-estágio
# --------------------------------------------------------------------------- #
def _stage(material, species, zin, Fin, T, P_hi, P_lo, area, cut, thickness_um):
    """Um estágio por área (rating) ou por corte (design)."""
    if area is not None:
        return single_stage(material, species, zin, Fin, T, P_hi, P_lo,
                            area=area, thickness_um=thickness_um)
    return single_stage(material, species, zin, Fin, T, P_hi, P_lo,
                        stage_cut=cut, thickness_um=thickness_um)


def _flows(stage_result, species, key):
    """Vazões molares por componente (mol/s) do permeado/retentado do estágio."""
    frac = stage_result.permeate if key == "permeate" else stage_result.retentate
    flow = stage_result.permeate_flow if key == "permeate" else stage_result.retentate_flow
    return np.array([frac[s] for s in species]) * flow


def two_stage_recycle(material: str, feed_species: list[str], z_feed: np.ndarray,
                      feed_flow: float, T: float, P_feed: float, P_permeate: float,
                      area1: float | None = None, area2: float | None = None,
                      cut1: float = 0.4, cut2: float = 0.5,
                      thickness_um: float = DEFAULT_THICKNESS_UM,
                      max_iter: int = 80, tol: float = 1e-9) -> MembraneSystemResult:
    """Dois estágios com reciclo do permeado (configuração padrão de biometano).

    Topologia (produto = retentado do estágio 1):

    ``feed + reciclo -> [Estágio 1] -> retentado = PRODUTO``
    ``                                 permeado -> [Estágio 2] -> permeado = REJEITO``
    ``                                              retentado = RECICLO (volta ao feed)``

    O reciclo recupera o CH₄ que escapou no permeado do estágio 1, elevando a
    recuperação global. Resolvido por ponto-fixo (Wegstein) sobre as vazões
    molares por componente do reciclo. As pressões assumem que o permeado do
    estágio 1 é **recomprimido** a ``P_feed`` antes do estágio 2.
    """
    species = list(feed_species)
    z0 = np.asarray(z_feed, dtype=float)
    z0 = z0 / z0.sum()
    f0 = z0 * float(feed_flow)               # vazões por componente do feed fresco

    # Dimensiona a área de cada estágio UMA vez (do feed fresco e dos cortes-alvo)
    # e a mantém fixa: hardware fixo, corte variável -- fisicamente correto, e o
    # laço de reciclo roda em modo rating (rápido).
    if area1 is None:
        area1 = single_stage(material, species, z0, float(feed_flow), T,
                             P_feed, P_permeate, stage_cut=cut1,
                             thickness_um=thickness_um).area
    if area2 is None:
        s1_0 = single_stage(material, species, z0, float(feed_flow), T,
                            P_feed, P_permeate, area=area1, thickness_um=thickness_um)
        p1_0 = _flows(s1_0, species, "permeate")
        zp1_0 = p1_0 / max(float(p1_0.sum()), 1e-12)
        area2 = single_stage(material, species, zp1_0, float(p1_0.sum()), T,
                            P_feed, P_permeate, stage_cut=cut2,
                            thickness_um=thickness_um).area

    def run(rec_comp):
        rec_comp = np.clip(np.asarray(rec_comp, dtype=float), 0.0, None)
        fm = f0 + rec_comp                   # mistura feed fresco + reciclo
        Fm = float(fm.sum())
        zm = fm / Fm
        s1 = single_stage(material, species, zm, Fm, T, P_feed, P_permeate,
                         area=area1, thickness_um=thickness_um)
        p1 = _flows(s1, species, "permeate")
        zp1 = p1 / max(float(p1.sum()), 1e-12)
        s2 = single_stage(material, species, zp1, float(p1.sum()), T, P_feed,
                         P_permeate, area=area2, thickness_um=thickness_um)
        return s1, s2

    def g_vec(x):
        _, s2 = run(x)
        return _flows(s2, species, "retentate")

    rec, report = wegstein(g_vec, np.zeros(len(species)), max_iter=max_iter, tol=tol)
    rec = np.clip(rec, 0.0, None)
    converged, iters = report.converged, report.iterations
    if not converged:                        # fallback: Picard amortecido
        rec = np.zeros(len(species))
        for i in range(400):
            new = np.clip(g_vec(rec), 0.0, None)
            if np.max(np.abs(new - rec)) < tol * (1.0 + np.max(np.abs(new))):
                rec, converged, iters = new, True, iters + i + 1
                break
            rec = 0.5 * rec + 0.5 * new

    s1, s2 = run(rec)
    prod = _flows(s1, species, "retentate")
    off = _flows(s2, species, "permeate")
    return _assemble_system(species, f0, prod, off, [s1, s2],
                            recycle_flow=float(rec.sum()),
                            converged=converged, iterations=iters,
                            message="Dois estágios com reciclo do permeado.")


def series_stages(material: str, feed_species: list[str], z_feed: np.ndarray,
                  feed_flow: float, T: float, P_feed: float, P_permeate: float,
                  areas: list[float] | None = None, cuts: list[float] | None = None,
                  n_stages: int = 2,
                  thickness_um: float = DEFAULT_THICKNESS_UM) -> MembraneSystemResult:
    """N estágios em série no retentado (cascata sem reciclo).

    O retentado de cada estágio alimenta o próximo (concentrando CH₄ a cada
    passo); os permeados de todos os estágios formam o rejeito combinado.
    Especifique ``areas`` (rating) ou ``cuts`` (design) por estágio; o
    comprimento da lista define o número de estágios.
    """
    species = list(feed_species)
    z = np.asarray(z_feed, dtype=float)
    z = z / z.sum()
    f0 = z * float(feed_flow)

    if areas is None and cuts is None:
        cuts = [0.3] * n_stages
    n = len(areas) if areas is not None else len(cuts)

    Fin, zin = float(feed_flow), z
    stages, offgas = [], np.zeros(len(species))
    for k in range(n):
        a = areas[k] if areas is not None else None
        c = cuts[k] if cuts is not None else None
        s = _stage(material, species, zin, Fin, T, P_feed, P_permeate, a, c, thickness_um)
        stages.append(s)
        offgas += _flows(s, species, "permeate")
        Fin = s.retentate_flow
        zin = np.array([s.retentate[sp] for sp in species])

    prod = _flows(stages[-1], species, "retentate")
    return _assemble_system(species, f0, prod, offgas, stages,
                            recycle_flow=0.0, converged=True, iterations=n,
                            message=f"{n} estágios em série no retentado (sem reciclo).")


def _assemble_system(species, f0, prod, offgas, stages, recycle_flow,
                     converged, iterations, message) -> MembraneSystemResult:
    Fprod = float(prod.sum())
    Foff = float(offgas.sum())
    zprod = prod / max(Fprod, 1e-12)
    zoff = offgas / max(Foff, 1e-12)
    F0 = float(f0.sum())
    res = MembraneSystemResult(
        product=dict(zip(species, (float(v) for v in zprod))),
        offgas=dict(zip(species, (float(v) for v in zoff))),
        product_flow=Fprod, offgas_flow=Foff,
        purity_CH4=0.0, recovery_CH4=0.0, CO2_removal=0.0,
        total_area=float(sum(s.area for s in stages)),
        stages=stages, recycle_flow=float(recycle_flow),
        mass_balance_error=abs(F0 - (Fprod + Foff)) / max(F0, 1e-12),
        converged=converged, iterations=int(iterations), message=message,
    )
    if "CH4" in species:
        i = species.index("CH4")
        res.purity_CH4 = float(zprod[i])
        res.recovery_CH4 = float(prod[i] / max(f0[i], 1e-12))
    if "CO2" in species:
        j = species.index("CO2")
        res.CO2_removal = 1.0 - float(prod[j] / max(f0[j], 1e-12))
    return res


__all__ = [
    "MembraneResult", "MembraneSystemResult",
    "single_stage", "two_stage_recycle", "series_stages",
    "DEFAULT_THICKNESS_UM",
]
