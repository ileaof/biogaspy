"""Exemplo: Separação por membrana MULTI-ESTÁGIO.

Compara, sob o mesmo biogás 47/53, três configurações resolvidas pelo modelo de
mistura completa (solução-difusão):

  1. **Um estágio** -- referência.
  2. **Dois estágios com reciclo do permeado** -- retentado do estágio 1 é o
     produto (biometano); o permeado é reprocessado no estágio 2, cujo retentado
     (rico em CH4) retorna à alimentação. É a configuração padrão de biometano.
  3. **Três estágios em série no retentado** -- cascata que concentra CH4.

Ilustra o compromisso pureza x recuperação x área: um único estágio perde CH4
no permeado; o reciclo recupera esse CH4 (recuperação sobe muito para pureza
comparável); a cascata em série concentra CH4 a pureza de biometano, ao custo
de mais área.
"""
from __future__ import annotations

import numpy as np

from ..Export import export_json
from ..Membranes import series_stages, single_stage, two_stage_recycle
from .common import BIOGAS

OUTDIR = "examples_output"


def run_case(material: str = "Polyimide", P_feed_bar: float = 15.0,
             P_perm_bar: float = 1.0, flow: float = 100.0,
             save: bool = True) -> dict:
    species = ["CH4", "CO2"]
    z = np.array([BIOGAS["CH4"], BIOGAS["CO2"]])
    Pf, Pp, T = P_feed_bar * 1e5, P_perm_bar * 1e5, 308.15

    s = single_stage(material, species, z, flow, T, Pf, Pp, stage_cut=0.65)
    d = two_stage_recycle(material, species, z, flow, T, Pf, Pp, cut1=0.65, cut2=0.6)
    c = series_stages(material, species, z, flow, T, Pf, Pp, cuts=[0.3, 0.3, 0.3])

    def row(name: str, r, area: float, recycle: float = 0.0) -> dict:
        return {
            "config": name,
            "purity_CH4": round(r.purity_CH4 * 100, 2),
            "recovery_CH4": round(r.recovery_CH4 * 100, 2),
            "CO2_removal": round(r.CO2_removal * 100, 2),
            "total_area_m2": round(area, 0),
            "recycle_mols": round(recycle, 2),
        }

    rows = [
        row("1 estagio", s, s.area),
        row("2 estagios + reciclo", d, d.total_area, d.recycle_flow),
        row("3 estagios em serie", c, c.total_area),
    ]
    # métricas "principais" = 2 estágios com reciclo (config padrão de biometano)
    metrics = {
        "technology": f"Membrane multi-stage ({material})",
        "material": material,
        "P_feed_bar": P_feed_bar,
        "P_perm_bar": P_perm_bar,
        "rows": rows,
        "purity_CH4": rows[1]["purity_CH4"],
        "recovery_CH4": rows[1]["recovery_CH4"],
        "CO2_removal": rows[1]["CO2_removal"],
        "two_stage_converged": d.converged,
        "mass_balance_error": d.mass_balance_error,
    }
    if save:
        export_json(metrics, f"{OUTDIR}/membrane_multistage_results.json")
    return {"single": s, "two_stage": d, "series": c, "metrics": metrics}


def main():
    out = run_case()
    m = out["metrics"]
    single, two = m["rows"][0], m["rows"][1]
    print("=" * 74)
    print(f"MEMBRANA MULTI-ESTAGIO -- {m['material']} "
          f"(P_feed={m['P_feed_bar']} bar, P_perm={m['P_perm_bar']} bar)")
    print("biogas 47% CH4 / 53% CO2")
    print("=" * 74)
    hdr = (f"{'Configuracao':<24}{'Pureza%':>9}{'Recup%':>9}"
           f"{'CO2rem%':>9}{'Area m2':>13}{'Recic.':>9}")
    print(hdr)
    print("-" * 74)
    for r in m["rows"]:
        print(f"{r['config']:<24}{r['purity_CH4']:>9.2f}{r['recovery_CH4']:>9.2f}"
              f"{r['CO2_removal']:>9.2f}{r['total_area_m2']:>13,.0f}{r['recycle_mols']:>9.2f}")
    print("-" * 74)
    print(f"Leitura: 1 estagio e 2 estagios+reciclo dao pureza parecida "
          f"(~{single['purity_CH4']:.0f}% vs ~{two['purity_CH4']:.0f}%),")
    print(f"mas o reciclo eleva a recuperacao de CH4 de {single['recovery_CH4']:.1f}% "
          f"para {two['recovery_CH4']:.1f}% -- recupera o CH4")
    print("perdido no permeado. A cascata em serie concentra CH4 a pureza de "
          "biometano, com mais area.")
    print(f"Balanco de massa (2 estagios): erro {m['mass_balance_error']:.1e} | "
          f"convergiu={m['two_stage_converged']}")


if __name__ == "__main__":
    main()
