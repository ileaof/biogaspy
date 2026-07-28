"""Geração de gráficos (matplotlib) para pós-processamento.

Usa backend ``Agg`` para funcionar sem display. Todas as funções salvam PNG.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _ensure_dir(path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def plot_column_profiles(result, species_names: List[str], path) -> None:
    """Perfis de composição (vapor e líquido) e temperatura ao longo da coluna."""
    p = _ensure_dir(path)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    stages = np.arange(1, result.N_stages + 1)
    # vapor
    for i, sp in enumerate(species_names):
        axes[0].plot(stages, result.y_profile[i, :], "-o", label=sp)
    axes[0].set_title("Perfil vapor (y)")
    axes[0].set_xlabel("Estágio (1=topo)")
    axes[0].set_ylabel("Fração molar")
    axes[0].legend()
    # líquido
    for i, sp in enumerate(species_names):
        axes[1].plot(stages, result.x_profile[i, :], "-s", label=sp)
    axes[1].set_title("Perfil líquido (x)")
    axes[1].set_xlabel("Estágio")
    axes[1].set_ylabel("Fração molar")
    axes[1].legend()
    # temperatura
    axes[2].plot(stages, result.T_profile, "-d", color="firebrick")
    axes[2].set_title("Perfil de temperatura")
    axes[2].set_xlabel("Estágio")
    axes[2].set_ylabel("T (K)")
    fig.tight_layout()
    fig.savefig(p, dpi=120)
    plt.close(fig)


def plot_equilibrium_curve(K_co2, path, label: str = "CO2") -> None:
    """Curva de equilíbrio y = K·x esquemática (apenas ilustrativa)."""
    p = _ensure_dir(path)
    x = np.linspace(0, 0.05, 50)
    y = K_co2 * x
    fig, ax = plt.subplots(figsize=(5, 4.5))
    ax.plot(x, y, label=f"y = {K_co2:.1f}·x ({label})")
    ax.plot([0, 0.05], [0, 0.05], "--", color="gray", label="y = x")
    ax.set_xlabel("x (líquido)")
    ax.set_ylabel("y (vapor)")
    ax.set_title("Curva de equilíbrio")
    ax.legend()
    fig.tight_layout()
    fig.savefig(p, dpi=120)
    plt.close(fig)


def plot_comparison(table: List[Dict], x_key: str, y_keys: List[str],
                    path, title: str = "Comparação entre tecnologias") -> None:
    """Gráfico de barras comparando tecnologias."""
    p = _ensure_dir(path)
    names = [row[x_key] for row in table]
    n = len(names)
    width = 0.8 / max(len(y_keys), 1)
    fig, ax = plt.subplots(figsize=(10, 5))
    for k, key in enumerate(y_keys):
        vals = [float(row.get(key, 0) or 0) for row in table]
        ax.bar(np.arange(n) + k * width, vals, width, label=key)
    ax.set_xticks(np.arange(n) + width * (len(y_keys) - 1) / 2)
    ax.set_xticklabels(names, rotation=20)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(p, dpi=120)
    plt.close(fig)


def plot_pxy(T: float, P: float, eos, species: List[str], path) -> None:
    """Diagrama P-x-y esquemático para binário (ilustrativo)."""
    p = _ensure_dir(path)
    if len(species) != 2:
        return
    x1 = np.linspace(0.001, 0.999, 50)
    # pressão de bolha/orvalho aproximada via Lei de Raoult modificada (φ=1)
    from ..Properties.components import get
    Psat = np.array([np.exp(5.373 * (1 + get(s).omega) * (1 - get(s).Tc / T)) * get(s).Pc
                     for s in species])
    Pbubble = x1 * Psat[0] + (1 - x1) * Psat[1]
    # dew: 1/P = x1/Psat0 + (1-x1)/Psat1
    Pdew = 1.0 / (x1 / Psat[0] + (1 - x1) / Psat[1])
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(x1, Pbubble / 1e5, label="Bolha")
    ax.plot(x1, Pdew / 1e5, label="Orvalho")
    ax.set_xlabel(f"x1, y1 ({species[0]})")
    ax.set_ylabel("P (bar)")
    ax.set_title(f"P-x-y a {T-273.15:.0f} °C")
    ax.legend()
    fig.tight_layout()
    fig.savefig(p, dpi=120)
    plt.close(fig)


def plot_sweep(result, path, ylabel: str = "Métrica (%)", title: str = None) -> None:
    """Plota métricas de uma varredura 1-D (SweepResult)."""
    p = _ensure_dir(path)
    x = np.asarray(result.values, dtype=float)
    fig, ax = plt.subplots(figsize=(8, 5))
    for attr, label in [("purity_CH4", "Pureza CH4"),
                        ("recovery_CH4", "Recuperação CH4"),
                        ("CO2_removal", "Remoção CO2")]:
        y = np.asarray(getattr(result, attr), dtype=float) * 100.0
        ax.plot(x, y, "-o", label=label)
    ax.set_xlabel(result.parameter)
    ax.set_ylabel(ylabel)
    ax.set_title(title or f"Sensibilidade: {result.parameter}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(p, dpi=120)
    plt.close(fig)


def plot_sweep_grid(grid: dict, metric: str, path, title: str = None) -> None:
    """Heatmap de uma varredura 2-D (saída de sweep_grid)."""
    p = _ensure_dir(path)
    M = np.asarray(grid[metric], dtype=float)
    vx = grid["values_x"]; vy = grid["values_y"]
    fig, ax = plt.subplots(figsize=(7, 5))
    data = M * 100.0 if metric != "converged" else M
    im = ax.imshow(data, origin="lower", aspect="auto",
                   extent=[vx[0], vx[-1], vy[0], vy[-1]], cmap="viridis")
    ax.set_xlabel(grid["param_x"])
    ax.set_ylabel(grid["param_y"])
    ax.set_title(title or f"{metric} vs ({grid['param_x']}, {grid['param_y']})")
    fig.colorbar(im, ax=ax, label=f"{metric} (%)")
    fig.tight_layout()
    fig.savefig(p, dpi=120)
    plt.close(fig)


__all__ = ["plot_column_profiles", "plot_equilibrium_curve",
           "plot_comparison", "plot_pxy", "plot_sweep", "plot_sweep_grid"]