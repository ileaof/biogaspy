"""Comparação entre tecnologias de upgrading -- tabela + gráficos + export.

Roda Water Scrubbing, MEA, PSA, Membrana (1 estágio) e Membrana multi-estágio
(2 estágios + reciclo) sob o mesmo biogás 47/53 e gera
tabela comparativa (pureza, recuperação, energia, custo, emissões evitadas,
eficiência global) em CSV/JSON/HTML + gráfico de barras.
"""
from __future__ import annotations

from ..Export import export_csv, export_excel, export_html, export_json
from ..Optimization import Economics
from ..Reporting import plot_comparison
from . import MEA, PSA, Membrane, MembraneMultiStage, WaterScrubbing
from .common import BIOGAS

OUTDIR = "examples_output"


def _efficiency(m: dict) -> float:
    """Eficiência global (%) = (CH4 recuperado no biometano / CH4 no biogás) * pureza."""
    return round((m.get("recovery_CH4", 0) / 100.0) * (m.get("purity_CH4", 0) / 100.0) * 100, 2)


def _economics(m: dict, total_kw: float, flow: float) -> dict:
    bio_nm3h = flow * 0.0224 * 3600 * (m.get("recovery_CH4", 90) / 100.0)
    co2_kg_h = flow * BIOGAS["CO2"] * (m.get("CO2_removal", 0) / 100.0) * 0.044 * 3600
    econ = Economics.from_process(total_kw=total_kw, biometane_nm3h=bio_nm3h,
                                  co2_avoided_kg_h=co2_kg_h)
    spec_kwh = total_kw / bio_nm3h if bio_nm3h > 0 else 0.0
    return {"opex_usd_yr": round(econ.opex_usd_yr, 0),
            "specific_kWh_per_Nm3": round(spec_kwh, 3),
            "specific_cost_usd_per_Nm3": round(econ.specific_cost_usd_per_nm3, 4),
            "co2_avoided_t_per_yr": round(econ.co2_avoided_t_per_yr, 1)}


def run_all(flow: float = 100.0, save: bool = True) -> list[dict]:
    rows = []
    # Water
    w = WaterScrubbing.run_case(save=False)
    mw = dict(w["metrics"])
    mw.update({"total_kW": mw.get("total_kW", 0),
               "water_m3h": round(w["result"].L_profile.mean() * 0.018 * 3600, 1)})
    mw.update(_economics(mw, mw.get("total_kW", 0), flow))
    mw["global_efficiency_pct"] = _efficiency(mw)
    rows.append(_select(mw))

    # MEA
    me = MEA.run_case(save=False)
    mme = dict(me["metrics"])
    mme.update(_economics(mme, mme.get("total_kW", 0), flow))
    mme["global_efficiency_pct"] = _efficiency(mme)
    rows.append(_select(mme))

    # PSA
    p = PSA.run_case(save=False)
    mp = dict(p["metrics"])
    mp["total_kW"] = round(50.0, 1)   # estimativa de compressor PSA
    mp.update(_economics(mp, mp["total_kW"], flow))
    mp["global_efficiency_pct"] = _efficiency(mp)
    rows.append(_select(mp, is_stub=True))

    # Membrane (1 estágio)
    mb = Membrane.run_case(save=False)
    mmb = dict(mb["metrics"])
    mmb["total_kW"] = round(30.0, 1)  # estimativa de compressor + vácuo
    mmb.update(_economics(mmb, mmb["total_kW"], flow))
    mmb["global_efficiency_pct"] = _efficiency(mmb)
    rows.append(_select(mmb, is_stub=True))

    # Membrane multi-estágio (2 estágios + reciclo do permeado)
    mms = MembraneMultiStage.run_case(save=False)
    mmms = dict(mms["metrics"])
    mmms["technology"] = "Membrane multi-stage"
    mmms["total_kW"] = round(45.0, 1)  # estimativa: compressão + recompressão do reciclo
    mmms.update(_economics(mmms, mmms["total_kW"], flow))
    mmms["global_efficiency_pct"] = _efficiency(mmms)
    rows.append(_select(mmms, is_stub=True))

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


def _select(m: dict, is_stub: bool = False) -> dict:
    return {
        "technology": m.get("technology", "?"),
        "purity_CH4": m.get("purity_CH4"),
        "recovery_CH4": m.get("recovery_CH4"),
        "CO2_removal": m.get("CO2_removal"),
        "residual_CO2": m.get("residual_CO2"),
        "total_kW": m.get("total_kW"),
        "specific_kWh_per_Nm3": m.get("specific_kWh_per_Nm3"),
        "specific_cost_usd_per_Nm3": m.get("specific_cost_usd_per_Nm3"),
        "co2_avoided_t_per_yr": m.get("co2_avoided_t_per_yr"),
        "global_efficiency_pct": m.get("global_efficiency_pct"),
        "stub": is_stub,
    }


def main():
    rows = run_all()
    print("=" * 80)
    print("COMPARAÇÃO ENTRE TECNOLOGIAS -- biogás 47% CH4 / 53% CO2")
    print("=" * 80)
    hdr = f"{'Tecnologia':<22}{'Pureza%':>8}{'Recup%':>8}{'CO2rem%':>8}{'kW':>8}{'kWh/Nm³':>9}{'USD/Nm³':>9}{'Ef.geral%':>10}"
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
