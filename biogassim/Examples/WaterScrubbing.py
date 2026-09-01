"""Exemplo: Lavagem com água (Water Scrubbing) -- biogás 47/53.

Roda o absorvedor com água em alta pressão (água recirculada), calcula
biometano, recuperação de metano, dimensionamento, energia e gera gráficos.

Com ``regen=True`` fecha o loop de regeneração (arquitetura Wellmann): água
rica -> flash 1 a média pressão (gás rico em CH4 recomprimido e devolvido à
ALIMENTAÇÃO do absorvedor) -> flash 2 a ~1 atm (vent de CO2) -> purge + makeup
(repõe purge e a água evaporada) -> bomba de volta a P_abs. O sistema
feed+reciclo/solvente é resolvido por iteração de ponto fixo (converge em
~7 passes) e a economia reporta **makeup** (não circulação) como consumo de
água.
"""
from __future__ import annotations

import numpy as np

from ..Export import export_csv, export_json, export_profile_csv
from ..Optimization import EnergySummary, compression_energy
from ..Properties.Moisture import water_content_mg_per_nm3
from ..Reporting import plot_column_profiles, plot_equilibrium_curve
from ..Solvents import WaterSolvent
from ..UnitOperations import Absorber, AbsorberSpec, Stream
from ..UnitOperations.Compressor import compress
from ..UnitOperations.Dryer import dry_gas
from ..UnitOperations.Regeneration import regen_water
from .common import BIOGAS, biogas_stream, metrics_from_absorber

OUTDIR = "examples_output"


def _mix_streams(a: Stream, b: Stream) -> Stream:
    """Mistura isotérmica de duas correntes com a MESMA lista de espécies."""
    f = a.flow + b.flow
    z = (a.z * a.flow + b.z * b.flow) / max(f, 1e-30)
    return Stream(list(a.species), float(f), z, float(0.5 * (a.T + b.T)),
                  float(a.P), phase=a.phase)


def _makeup_stream(species, P: float, flow_mols: float, T: float) -> Stream:
    """Água fresca pura a P (makeup do loop de regeneração)."""
    z = np.zeros(len(species))
    z[species.index("H2O")] = 1.0
    return Stream(list(species), float(flow_mols), z, float(T), float(P), phase="liquid")


def run_case(P_bar: float = 20.0, L_over_V: float = 100.0, N_stages: int = 12,
             height: float = 15.0, flow: float = 100.0, save: bool = True,
             composition=None, regen: bool = False,
             dryer_mg_nm3: float | None = None, P_flash1_bar: float | None = None,
             purge_frac: float = 0.02, T_C: float = 20.0) -> dict:
    # conjunto de espécies montado a partir da composição (multi-gás): água
    # absorve CO2, H2S, NH3 etc.; N2/O2/H2/Ar passam praticamente direto.
    comp_dict = composition or {"CH4": BIOGAS["CH4"], "CO2": BIOGAS["CO2"]}
    gas_species = [s for s in comp_dict if float(comp_dict.get(s, 0.0)) > 0.0 and s != "H2O"]
    if not gas_species:
        gas_species = ["CH4", "CO2"]
    species = [*gas_species, "H2O"]
    P = P_bar * 1e5
    Tk = float(T_C) + 273.15             # coluna isotérmica: gás, solvente e
    # compressão do biogás da pressão atmosférica até P          regeneração a T_C
    gas_in = biogas_stream(flow, species=species, T=Tk, P=1.01325e5,
                           composition=comp_dict)
    comp = compress(gas_in, P, eta=0.75)
    gas_feed = comp.out
    rec_kw = 0.0
    rec_mols = 0.0
    regen_result = None
    recycle = None
    # absorvedor (mesma spec para os dois passes)
    z_solv = np.zeros(len(species))
    z_solv[species.index("H2O")] = 1.0
    solv = Stream.make(species, z_solv, flow=L_over_V * flow,
                       T=Tk, P=P, phase="liquid")
    spec = AbsorberSpec(N_stages=N_stages, packing="Pall_50",
                        mode="isothermal", T_op=Tk, pressure=P, height=height,
                        max_iter=400)
    if regen:
        # Arquitetura Wellmann (padrão real de water scrubbing), resolvida por
        # ponto fixo (converge em ~7 iterações; contração ~x0.07):
        #   gás de feed + reciclo do flash 1 -> absorvedor (água magra do loop)
        #   -> água rica -> flash 1 (média pressão): gás rico em CH4
        #      recomprimido e DEVOLVIDO À ALIMENTAÇÃO; flash 2 (~1 atm): vent
        #      de CO2; purge + makeup (repõe purge + evaporação) + bomba.
        # O CO2 do reciclo é reabsorvido e sai pelo vent; o CH4 volta ao feed,
        # elevando a recuperação global SEM contaminar a linha de produto.
        P_flash1 = (P_flash1_bar or 0.5 * P_bar) * 1e5
        solv_loop = solv                      # 1º passe: água fresca
        for _ in range(30):
            feed_i = (_mix_streams(gas_feed, recycle) if (recycle is not None
                                                          and recycle.flow > 0)
                      else gas_feed)
            r = Absorber(feed_i, solv_loop, WaterSolvent(), spec).solve()
            if not r.converged:
                break
            regen_result = regen_water(r.liquid_out, P, P_flash1=P_flash1,
                                       P_flash2=1.0e5, T_flash=Tk,
                                       purge_frac=purge_frac)
            makeup = _makeup_stream(species, P, regen_result.makeup_mols, Tk)
            solv_loop = (_mix_streams(regen_result.lean_out, makeup)
                         if regen_result.makeup_mols > 0 else regen_result.lean_out)
            rec_kw = regen_result.recycle_compression_kW
            rec_mols = (regen_result.recycle.flow if regen_result.recycle is not None
                        else 0.0)
            if recycle is not None and rec_mols > 0:
                # convergência do ponto fixo: |Δ reciclo| < 1e-4 rel
                if abs(rec_mols - recycle.flow) < 1e-4 * max(rec_mols, 1.0):
                    recycle = regen_result.recycle
                    break
            recycle = regen_result.recycle
    else:
        r = Absorber(gas_feed, solv, WaterSolvent(), spec).solve()

    metrics = metrics_from_absorber("Water Scrubbing", r, gas_in)
    # remoção por espécie para gases além de CH4/CO2 (H2S, NH3, N2, ...)
    for s in gas_species:
        if s in ("CH4", "CO2"):
            continue
        i = gas_in.species.index(s)
        fin = gas_in.flow * gas_in.z[i]
        if fin > 1e-12:
            fout = r.gas_out.flow * r.gas_out.z[i]
            metrics[f"{s}_removal"] = round(100.0 * (1.0 - fout / fin), 2)

    # água: circulação (L/V) x consumo (maquimento = purge) -- não confundir!
    mm_w = 0.018015
    mols_liq = (L_over_V * flow) if not regen else (L_over_V * gas_feed.flow)
    metrics["water_circulation_m3_per_h"] = round(mols_liq * mm_w / 1000.0 * 3600.0, 2)
    if regen and regen_result is not None:
        metrics["water_m3_per_h"] = round(regen_result.makeup_mols * mm_w / 1000.0 * 3600.0, 2)
        metrics["recycle_mols"] = round(rec_mols, 3)
        metrics["recycle_kW"] = round(rec_kw, 2)
        metrics["flash1_gas_mols"] = round(regen_result.flash1_gas.flow, 3)
        metrics["flash1_gas_CH4_pct"] = round(regen_result.flash_details["flash1_gas_CH4_pct"], 2)
        metrics["ch4_lost_in_vent_mols"] = round(
            regen_result.flash_details["ch4_lost_in_vent_mols"], 4)
        metrics["ch4_recycled_mols"] = round(regen_result.ch4_recovered_mols, 4)
        # métricas do PRODUTO BLENDADO (topo + reciclo do flash 1): pureza,
        # CO2 residual e recuperação global vs alimentação crua
        i_ch4 = species.index("CH4")
        i_co2 = species.index("CO2")
        tot = max(r.gas_out.flow, 1e-12)
        ch4_out = r.gas_out.flow * r.gas_out.z[i_ch4]
        co2_out = r.gas_out.flow * r.gas_out.z[i_co2]
        metrics["purity_CH4"] = round(100.0 * ch4_out / tot, 2)
        metrics["residual_CO2"] = round(100.0 * co2_out / tot, 3)
        ch4_in_raw = flow * comp_dict.get("CH4", 0.0)
        co2_in_raw = flow * comp_dict.get("CO2", 0.0)
        metrics["CO2_removal"] = round(100.0 * (1.0 - co2_out / max(co2_in_raw, 1e-12)), 2)
        overall = 100.0 * ch4_out / max(ch4_in_raw, 1e-12)
        metrics["recovery_CH4"] = round(min(overall, 100.0), 2)
        metrics["methane_loss"] = round(100.0 - metrics["recovery_CH4"], 2)
    else:
        metrics["water_m3_per_h"] = round(L_over_V * flow * mm_w / 1000.0 * 3600.0, 2)

    # energia: compressão do gás cru (+ compressor do reciclo) + bomba do
    # recirculado (flash ~1 atm -> P_abs)
    pumping_kw = regen_result.lean_pump_kW if (regen and regen_result is not None) \
        else L_over_V * flow * mm_w / 1000 * P / 0.7 / 1000
    energy = EnergySummary(compression=compression_energy([comp]) + rec_kw,
                           pumping=pumping_kw)
    # biometano em Nm³/h (~ gas_out.flow * 22.4e-3 * 3600)
    bio_nm3h = r.gas_out.flow * 0.0224 * 3600
    energy.finalize(bio_nm3h)
    metrics.update({"compression_kW": round(compression_energy([comp]) + rec_kw, 2),
                    "pumping_kW": round(pumping_kw, 2),
                    "total_kW": round(energy.total_kw, 2),
                    "specific_kWh_per_Nm3": round(energy.specific_kwh_per_nm3, 3)})

    # secador (opcional): leva o gás tratado à especificação de umidade
    dryer = None
    if dryer_mg_nm3 is not None:
        dryer = dry_gas(r.gas_out, dryer_mg_nm3)
        i_w = species.index("H2O")
        metrics["H2O_mg_per_Nm3_antes"] = round(
            water_content_mg_per_nm3(r.gas_out.z[i_w]), 1)
        metrics["H2O_mg_per_Nm3_depois"] = round(
            water_content_mg_per_nm3(dryer.out.z[i_w]), 1)
        metrics["dryer_regen_kW"] = round(dryer.regen_duty_kW, 2)

    if save:
        export_json(metrics, f"{OUTDIR}/water_results.json")
        export_csv([metrics], f"{OUTDIR}/water_summary.csv")
        export_profile_csv(np.column_stack([r.x_profile.T, r.y_profile.T, r.T_profile]),
                           [f"x_{s}" for s in species] + [f"y_{s}" for s in species] + ["T_K"],
                           f"{OUTDIR}/water_profiles.csv")
        plot_column_profiles(r, species, f"{OUTDIR}/water_profiles.png")
        if "CO2" in species:
            K_co2 = float(r.K_profile[species.index("CO2")].mean())
            plot_equilibrium_curve(K_co2, f"{OUTDIR}/water_equilibrium.png", label="CO2 (water)")
    return {"result": r, "metrics": metrics, "compressor": comp,
            "regen": regen_result, "recycle": recycle, "dryer": dryer}


def main():
    data = run_case()
    m = data["metrics"]
    print("=" * 60)
    print("WATER SCRUBBING -- biogás 47% CH4 / 53% CO2")
    print("=" * 60)
    print(f"Convergiu: {m['converged']} em {m['iterations']} iterações")
    print(f"Pureza CH4:      {m['purity_CH4']} %")
    print(f"Recuperação CH4: {m['recovery_CH4']} %  (perda {m['methane_loss']} %)")
    print(f"Remoção CO2:     {m['CO2_removal']} %  (residual {m['residual_CO2']} %)")
    print(f"Diâmetro: {m['diameter_m']} m | Altura: {m['height_m']} m")
    print(f"NTU: {m['NTU']} | HTU: {m['HTU_m']} m | KLa: {m['KLa']}")
    print(f"Energia: compressão {m['compression_kW']} kW, total {m['total_kW']} kW")
    print(f"Consumo específico: {m['specific_kWh_per_Nm3']} kWh/Nm³ biometano")
    print(f"Arquivos gerados em {OUTDIR}/water_*")


if __name__ == "__main__":
    main()
