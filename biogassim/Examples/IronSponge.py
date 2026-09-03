"""Exemplo: iron sponge -- leito fixo seco de Fe2O3 para remoção de H2S."""
from __future__ import annotations

from ..Export import export_json
from ..UnitOperations.IronSponge import IronSpongeSpec, solve

OUTDIR = "examples_output"


def run_case(contact_time_s: float = 100.0, fe2o3_wt: float = 0.30,
             moisture_wt: float = 0.35, H_over_D: float = 1.5,
             regen_mode: str = "in_situ", air_excess: float = 0.5,
             capacity_g_per_g: float | None = None, P_bar: float = 1.10,
             composition=None, flow: float = 100.0, save: bool = False,
             T_C: float = 25.0) -> dict:
    """Roda o leito fixo de Fe2O3 e devolve ``{"metrics": {...}}``.

    Métricas cruas no formato que ``comparison._standardize`` espera
    (chaves comuns às demais tecnologias + campos próprios do leito).
    """
    spec = IronSpongeSpec(
        contact_time_s=float(contact_time_s), fe2o3_wt=float(fe2o3_wt),
        moisture_wt=float(moisture_wt), H_over_D=float(H_over_D),
        regen_mode=str(regen_mode), air_excess=float(air_excess))
    r = solve(spec, composition, flow, T_C=float(T_C), P_bar=float(P_bar),
              capacity_g_per_g=(None if capacity_g_per_g is None
                                else float(capacity_g_per_g)))
    metrics = {
        "technology": f"Iron sponge (Fe2O3 {spec.fe2o3_wt:.0%}, regen={spec.regen_mode})",
        "converged": r.converged,
        "message": "; ".join(r.warnings) if r.warnings else r.message,
        "mass_balance_error": r.mass_balance_error,
        # qualidade
        "purity_CH4": r.purity_CH4,
        "recovery_CH4": r.recovery_CH4,
        "CO2_removal": r.CO2_removal_pct,
        "H2S_removal": r.H2S_removal_pct,
        "methane_loss": r.methane_loss_pct,
        "treated_H2S_ppm": r.treated_H2S_ppm,
        "treated_LHV_MJ_per_Nm3": r.lhv_mj_per_nm3,
        "treated_HHV_MJ_per_Nm3": r.hhv_mj_per_nm3,
        "treated_wobbe_MJ_per_Nm3": r.wobbe_mj_per_nm3,
        "product_flow_mols": round(r.product_flow_mols, 4),
        # leito
        "diameter_m": r.diameter_m,
        "height_m": r.height_m,
        "bed_volume_m3": r.bed_volume_m3,
        "superficial_velocity_m_per_s": r.superficial_velocity_m_per_s,
        "pressure_drop_Pa": r.pressure_drop_Pa,
        "operating_pressure_bar": round(float(P_bar), 2),
        # meio / vida
        "media_mass_kg": r.media_mass_kg,
        "fe2o3_mass_kg": r.fe2o3_mass_kg,
        "h2s_capacity_kg": r.h2s_capacity_kg,
        "life_days": r.life_days,
        "campaigns_per_yr": r.campaigns_per_yr,
        "media_kg_per_campaign": r.media_kg_per_campaign,
        "media_kg_per_yr": r.media_kg_per_yr,
        "h2s_load_kg_per_day": r.h2s_load_kg_per_day,
        "sulfur_kg_per_day": r.sulfur_kg_per_day,
        # regeneração in-situ
        "air_dose_nm3h": r.air_dose_nm3h,
        "oxygen_residual_pct": r.oxygen_residual_pct,
        # energia
        "pumping_kW": r.blower_kW,            # soprador -> eletricidade
        "compression_kW": r.compression_kW,
        "total_kW": r.total_kW,
        "specific_kWh_per_Nm3": r.specific_kWh_per_Nm3,
        "warnings": list(r.warnings),
    }
    if save:
        export_json(metrics, f"{OUTDIR}/iron_sponge_results.json")
    return {"metrics": metrics}


def main():
    m = run_case()["metrics"]
    print("=" * 60)
    print("IRON SPONGE (LEITO FIXO Fe2O3) -- projeto estequiométrico")
    print("=" * 60)
    print(f"Leito: D = {m['diameter_m']} m | H = {m['height_m']} m "
          f"| V = {m['bed_volume_m3']} m³")
    print(f"ΔP (Ergun): {m['pressure_drop_Pa']} Pa | "
          f"u_s = {m['superficial_velocity_m_per_s']} m/s")
    print(f"Meio: {m['media_mass_kg']} kg (Fe2O3: {m['fe2o3_mass_kg']} kg)")
    print(f"Vida útil: {m['life_days']} dias "
          f"({m['campaigns_per_yr']} campanhas/ano)")
    print(f"Consumo de meio: {m['media_kg_per_yr']} kg/ano")
    print(f"H2S: remoção {m['H2S_removal']} % | tratado {m['treated_H2S_ppm']} ppm")
    print(f"Pureza CH4: {m['purity_CH4']} % (N2 do ar dilui o tratado)")
    if m["warnings"]:
        print("Avisos: " + "; ".join(m["warnings"]))


if __name__ == "__main__":
    main()
