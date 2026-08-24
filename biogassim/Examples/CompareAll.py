"""Comparação entre tecnologias de upgrading -- tabela + gráficos + export.

Delegate do :class:`biogassim.comparison.ComparisonEngine` para o caso fixo
biogás 47% CH4 / 53% CO2. A engine é a fonte única compartilhada com a CLI
(``biogassim compare``) e a GUI (aba "Comparação de Métodos"); este módulo
mantém o ponto de entrada legado ``run_all``/``main`` e os mesmos arquivos de
saída (``comparison.csv/.json/.html/.xlsx`` + gráficos).
"""
from __future__ import annotations

from ..comparison import ComparisonConfig, ComparisonEngine
from ..Export import export_csv, export_excel, export_html, export_json
from ..Reporting import plot_comparison

OUTDIR = "examples_output"

# tecnologias comparadas historicamente (Water, MEA, PSA, Membrana 1 e multi)
_LEGACY = ["water", "mea", "psa", "membrane", "membrane_multi"]


def _efficiency(m: dict) -> float:
    return round((m.get("recovery_CH4", 0) / 100.0) * (m.get("purity_CH4", 0) / 100.0) * 100, 2)


def _select(row: dict) -> dict:
    """Linhas legadas com a chave ``technology`` (compatibilidade de testes/CSV)."""
    return {
        "technology": row.get("method_label", "?"),
        "purity_CH4": row.get("purity_CH4"),
        "recovery_CH4": row.get("recovery_CH4"),
        "CO2_removal": row.get("CO2_removal"),
        "total_kW": row.get("total_kW"),
        "specific_kWh_per_Nm3": row.get("specific_kWh_per_Nm3"),
        "specific_cost_usd_per_Nm3": row.get("specific_cost_usd_per_Nm3"),
        "global_efficiency_pct": row.get("global_efficiency_pct"),
        "stub": row.get("status") == "experimental",
    }


def run_all(flow: float = 100.0, save: bool = True) -> list[dict]:
    cfg = ComparisonConfig(selected=_LEGACY)
    eng = ComparisonEngine({"CH4": 0.47, "CO2": 0.53}, flow=flow, config=cfg)
    eng.run()
    rows = [_select(r) for r in eng.rows]
    if save:
        export_csv(rows, f"{OUTDIR}/comparison.csv")
        export_json({"comparison": rows}, f"{OUTDIR}/comparison.json")
        export_html(rows, f"{OUTDIR}/comparison.html", title="BioGasSim -- Comparação")
        try:
            export_excel({"comparison": rows}, f"{OUTDIR}/comparison.xlsx")
        except Exception:
            pass
        plot_comparison(rows, "technology",
                        ["purity_CH4", "recovery_CH4", "CO2_removal"],
                        f"{OUTDIR}/comparison_quality.png",
                        title="Qualidade do biometano (%)")
        plot_comparison(rows, "technology",
                        ["total_kW", "specific_kWh_per_Nm3"],
                        f"{OUTDIR}/comparison_energy.png",
                        title="Consumo energético")
    return rows


def main():
    rows = run_all()
    print("=" * 80)
    print("COMPARAÇÃO ENTRE TECNOLOGIAS -- biogás 47% CH4 / 53% CO2")
    print("=" * 80)
    hdr = (f"{'Tecnologia':<22}{'Pureza%':>8}{'Recup%':>8}{'CO2rem%':>8}"
           f"{'kW':>8}{'kWh/Nm³':>9}{'USD/Nm³':>9}{'Ef.geral%':>10}")
    print(hdr)
    print("-" * 80)
    for r in rows:
        def fmt(v, w):
            return f"{v:>{w}}" if isinstance(v, (int, float)) and v is not None else f"{'-':>{w}}"
        print(f"{r['technology']:<22}{fmt(r['purity_CH4'],8)}{fmt(r['recovery_CH4'],8)}"
              f"{fmt(r['CO2_removal'],8)}{fmt(r['total_kW'],8)}"
              f"{fmt(r['specific_kWh_per_Nm3'],9)}{fmt(r['specific_cost_usd_per_Nm3'],9)}"
              f"{fmt(r['global_efficiency_pct'],10)}")
    print("-" * 80)
    print("Arquivos gerados: comparison.csv/.json/.html/.xlsx + comparison_*.png")


if __name__ == "__main__":
    main()
