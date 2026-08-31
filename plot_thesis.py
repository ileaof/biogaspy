#!/usr/bin/env python3
"""Plota cada coluna do CSV da varredura (biogassim sweep) em função da composição.

Lê um arquivo gerado por ``biogassim sweep CH4=... --out thesis.csv`` e gera um
gráfico por métrica (coluna) contra a fração de CH4 do feed, além de um painel
combinado. Colunas vazias/não numéricas (ex.: água no caso MEA) são ignoradas.

Uso:
    python plot_thesis.py                       # lê thesis.csv, salva em figs/
    python plot_thesis.py thesis_mea/thesis.csv # outro arquivo
    python plot_thesis.py thesis.csv --outdir graficos --show
    python plot_thesis.py h2s.csv --x feed_H2S_pct   # CSV de varredura de H2S
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys

import matplotlib

# Garante que a ajuda e as mensagens (com acentos: função, resolução, água)
# saiam legíveis mesmo em consoles Windows cuja codepage não é UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Rótulo (nome legível, unidade) por coluna conhecida. Colunas fora deste mapa
# são plotadas mesmo assim, usando o próprio nome como título.
LABELS: dict[str, tuple[str, str]] = {
    "purity_CH4": ("Pureza de CH₄", "%"),
    "recovery_CH4": ("Recuperação de CH₄", "%"),
    "CO2_removal": ("Remoção de CO₂", "%"),
    "methane_loss": ("Perda de metano", "%"),
    "solvent_flow_mols": ("Vazão de solvente", "mol/s"),
    "water_m3_per_h": ("Consumo de água", "m³/h"),
    "total_kW": ("Potência total", "kW"),
    "specific_kWh_per_Nm3": ("Energia específica", "kWh/Nm³"),
    "diameter_m": ("Diâmetro da coluna", "m"),
    "height_m": ("Altura da coluna", "m"),
    "pressure_drop_Pa": ("Perda de carga", "Pa"),
    "flooding_pct": ("Margem de inundação", "%"),
    "specific_cost_usd_per_Nm3": ("Custo específico", "USD/Nm³"),
    "H2S_removal": ("Remoção de H₂S", "%"),
    "treated_H2S_pct": ("H₂S no gás tratado", "%"),
    "treated_H2S_ppm": ("H₂S no gás tratado", "ppm"),
    "treated_wobbe_MJ_per_Nm3": ("Índice de Wobbe (tratado)", "MJ/Nm³"),
    "liquid_H2S_loading_mol_per_mol": ("Carga de H₂S no líquido", "mol/mol"),
}
X_LABELS: dict[str, str] = {
    "feed_CH4_pct": "Fração de CH₄ no feed (%)",
    "feed_H2S_pct": "Fração de H₂S no feed (%)",
}
# Colunas que nunca viram gráfico (metadados / status).
SKIP = {"converged", "error", "name", "technology"}


def _to_float(v: str) -> float:
    """Converte célula do CSV em float; vazio/não numérico -> NaN."""
    if v is None:
        return math.nan
    s = v.strip()
    if s == "" or s.lower() in {"none", "nan"}:
        return math.nan
    try:
        return float(s)
    except ValueError:
        return math.nan


def read_csv(path: str) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = reader.fieldnames or []
    if not rows:
        raise SystemExit(f"'{path}' não tem linhas de dados.")
    return cols, rows


def pretty(col: str) -> tuple[str, str]:
    name, unit = LABELS.get(col, (col, ""))
    return name, unit


def plot_all(path: str, x_col: str | None, outdir: str,
             show: bool, dpi: int, combined: bool) -> None:
    import matplotlib.pyplot as plt  # importado após escolher o backend

    cols, rows = read_csv(path)

    # Coluna do eixo x (composição): explícita, ou a primeira que começa com "feed".
    if x_col is None:
        x_col = next((c for c in cols if c.startswith("feed")), cols[0])
    if x_col not in cols:
        feeds = [c for c in cols if c.startswith("feed")]
        dica = (f"\nEste CSV é uma varredura de '{feeds[0]}' — omita --x que a "
                f"coluna é detectada sozinha." if feeds else "")
        raise SystemExit(f"Coluna de composição '{x_col}' não existe neste CSV.{dica}\n"
                         f"Colunas disponíveis: {', '.join(cols)}")
    x = [_to_float(r[x_col]) for r in rows]

    # Colunas plotáveis: numéricas, não vazias, exceto x e metadados.
    ycols = []
    for c in cols:
        if c == x_col or c in SKIP:
            continue
        vals = [_to_float(r[c]) for r in rows]
        if any(not math.isnan(v) for v in vals):     # tem ao menos um número
            ycols.append((c, vals))
    if not ycols:
        raise SystemExit("Nenhuma coluna numérica para plotar.")

    os.makedirs(outdir, exist_ok=True)
    xlabel = X_LABELS.get(x_col, x_col)
    base = os.path.splitext(os.path.basename(path))[0]

    # Um gráfico por métrica.
    saved = []
    for col, vals in ycols:
        name, unit = pretty(col)
        ylabel = f"{name} [{unit}]" if unit else name
        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.plot(x, vals, "o-", color="#1f6feb", linewidth=1.8, markersize=5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(f"{name} vs. composição")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        out = os.path.join(outdir, f"{base}_{col}.png")
        fig.savefig(out, dpi=dpi)
        plt.close(fig)
        saved.append(out)

    # Painel combinado (montagem em grade).
    if combined:
        n = len(ycols)
        ncols = min(3, n)
        nrows = math.ceil(n / ncols)
        fig, axes = plt.subplots(
            nrows, ncols, figsize=(5 * ncols, 3.4 * nrows), squeeze=False)
        for ax, (col, vals) in zip(axes.flat, ycols):
            name, unit = pretty(col)
            ax.plot(x, vals, "o-", color="#1f6feb", linewidth=1.6, markersize=4)
            ax.set_title(name, fontsize=10)
            ax.set_xlabel(xlabel, fontsize=8)
            ax.set_ylabel(unit or "", fontsize=8)
            ax.tick_params(labelsize=8)
            ax.grid(True, alpha=0.3)
        for ax in axes.flat[n:]:                       # esconde eixos vazios
            ax.set_visible(False)
        fig.suptitle(f"Varredura de composição — {base}", fontsize=13)
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        out = os.path.join(outdir, f"{base}_painel.png")
        fig.savefig(out, dpi=dpi)
        saved.append(out)
        if not show:
            plt.close(fig)

    print(f"{len(saved)} arquivo(s) salvo(s) em '{outdir}/':")
    for s in saved:
        print(f"  {s}")
    if show:
        plt.show()


_EPILOG = """\
exemplos:
  python plot_thesis.py                          lê thesis.csv, salva PNGs em figs/
  python plot_thesis.py thesis_mea/thesis.csv    plota outro arquivo
  python plot_thesis.py thesis.csv --show        abre as janelas ao final
  python plot_thesis.py thesis.csv --outdir graficos --dpi 150
  python plot_thesis.py thesis.csv --no-combined não gera o painel-resumo

o eixo x é detectado sozinho (feed_CH4_pct nas varreduras de composição,
feed_H2S_pct nas de H2S); use --x só para forçar outra coluna. exemplo com
um CSV de varredura de H2S (biogassim sweep H2S=0:0.05:0.005 --out h2s.csv):
  python plot_thesis.py h2s.csv --x feed_H2S_pct

saídas geradas em OUTDIR:
  <base>_<coluna>.png   um gráfico por métrica (pureza, recuperação, energia,
                        custo, diâmetro, perda de carga, ...) vs. composição
  <base>_painel.png     painel combinado com todas as métricas

o CSV vem de:  biogassim sweep CH4=0.40:0.70:0.05 --out thesis.csv
"""


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="plot_thesis.py",
        description=__doc__,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", default="thesis.csv",
                    help="arquivo CSV da varredura (padrão: thesis.csv)")
    ap.add_argument("--x", dest="x_col", default=None, metavar="COLUNA",
                    help="coluna do eixo x (padrão: auto, ex.: feed_CH4_pct)")
    ap.add_argument("--outdir", default="figs", metavar="DIR",
                    help="pasta de saída (padrão: figs)")
    ap.add_argument("--dpi", type=int, default=120,
                    help="resolução dos PNG em pontos por polegada (padrão: 120)")
    ap.add_argument("--show", action="store_true",
                    help="abre as janelas dos gráficos ao final")
    ap.add_argument("--no-combined", dest="combined", action="store_false",
                    help="não gera o painel-resumo combinado")
    args = ap.parse_args(argv)

    if not os.path.exists(args.csv):
        raise SystemExit(f"Arquivo não encontrado: {args.csv}\n"
                         "Gere-o com: biogassim sweep CH4=0.40:0.70:0.05 --out thesis.csv")

    # Backend só-arquivo quando não vai mostrar (evita erro sem display).
    if not args.show:
        matplotlib.use("Agg")

    plot_all(args.csv, args.x_col, args.outdir, args.show, args.dpi, args.combined)


if __name__ == "__main__":
    main()
