"""Leito fixo seco de hidróxido de ferro ("iron sponge") -- remoção de H2S.

Modelo de **projeto/engenharia**: balanços estequiométricos + critérios
heurísticos da literatura de biogás (Wellinger et al. 2013, "The Biogas
Handbook", cap. 4; critérios GARDN/Wellmann). O meio é FeOOH hidratado
(representado como Fe2O3·H2O); o CH4/CO2 atravessam o leito inalterados.

Reações:
    carga:      Fe2O3·H2O + 3 H2S -> Fe2S3·H2O + 3 H2O
    regen. ex-situ: 2 Fe2S3·H2O + 3/2 O2 -> Fe2O3·H2O + 6 S(s)  (enxofre fica no leito)
    regen. in-situ (dosagem contínua de ar): 2 H2S + O2 -> 2 S + 2 H2O  (exotérmica)

Critérios de projeto (valores default, fontes nos campos da spec):
    teor de Fe2O3 >= 0,20 fr. máss.; umidade do meio 0,30-0,40; pH 8-10;
    T <= 50 °C; EBCT (tempo de contato) 60-120 s; capacidade once-through
    ~0,20 g H2S/g Fe2O3; com regenerações, capacidade acumulada até ~2,5
    g H2S/g Fe2O3; queda de pressão pela equação de Ergun (1952) -- o
    ``Hydraulics/PressureDrop`` (Stichlmair) vale para recheio de coluna,
    não para meio granular seco.

Espaço para variantes futuras: ``media_type`` (lama úmida, redox quelado)
e ``regen_mode`` já são campos da spec.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..Core.constants import MM
from ..Properties import mixture_properties_general, normalize_mixture
from ..Properties.GasProperties import MOL_PER_NM3, P_NORMAL
from .base import UnitResult

# Estequiometria (fontes nos comentários)
O2_PER_H2S: float = 0.5          # mol O2/mol H2S (2 H2S + O2 -> 2 S + 2 H2O)
S_PER_H2S_MASS: float = MM["S"] / MM["H2S"]    # kg S/kg H2S (~0,941)
AIR_O2_FRACTION: float = 0.2095  # fração molar de O2 no ar seco
MU_G_DEFAULT: float = 1.5e-5     # Pa·s (viscosidade do biogás, ~25 °C)


@dataclass(frozen=True)
class IronSpongeSpec:
    """Parâmetros do leito fixo de óxido de ferro (defaults da literatura)."""
    contact_time_s: float = 100.0      # EBCT; lit.: 60-120 s (Wellinger 2013)
    H_over_D: float = 1.5              # razão altura/diâmetro (1-2 típico)
    max_height_m: float = 4.0          # teto prático (leitos em série = roadmap)
    u_max_m_per_s: float = 0.30        # velocidade superficial máxima
    fe2o3_wt: float = 0.30             # teor de Fe2O3; lit.: >= 0,20
    moisture_wt: float = 0.35          # umidade do meio; lit.: 0,30-0,40
    bulk_density_kg_m3: float = 750.0  # densidade a granel do meio
    voidage: float = 0.40              # porosidade do leito (p/ Ergun)
    particle_diameter_m: float = 0.006  # diâmetro equivalente da partícula (p/ Ergun)
    capacity_once_through_g_per_g: float = 0.20   # g H2S/g Fe2O3 (GARDN)
    capacity_accumulated_g_per_g: float = 2.50    # acumulada c/ regenerações
    regen_mode: str = "in_situ"        # "in_situ" | "ex_situ" | "none"
    air_excess: float = 0.5            # excesso de O2 sobre o estequiométrico
    target_H2S_ppm: float = 4.0        # alvo de especificação
    o2_residual_limit_pct: float = 1.0  # alerta de segurança (O2 no produto)
    blower_eta: float = 0.70           # rendimento do soprador
    media_type: str = "fe2o3_hydrated"  # futuro: "wet_slurry", "chelated_redox"

    def __post_init__(self) -> None:
        if self.regen_mode not in ("in_situ", "ex_situ", "none"):
            raise ValueError(
                f"regen_mode inválido: {self.regen_mode!r} "
                "(use 'in_situ', 'ex_situ' ou 'none')")
        for nome, v in (("contact_time_s", self.contact_time_s),
                        ("fe2o3_wt", self.fe2o3_wt),
                        ("bulk_density_kg_m3", self.bulk_density_kg_m3)):
            if v <= 0:
                raise ValueError(f"{nome} deve ser > 0 (recebido {v})")


@dataclass
class IronSpongeResult(UnitResult):
    """Resultado do leito fixo de Fe2O3 (converged/iterations/message herdados)."""
    treated: dict[str, float] = field(default_factory=dict)
    mass_balance_error: float = 0.0
    treated_H2S_ppm: float | None = None
    purity_CH4: float = 100.0          # %
    recovery_CH4: float = 100.0        # % (CH4 atravessa o leito)
    H2S_removal_pct: float | None = None
    CO2_removal_pct: float = 0.0       # o método não remove CO2
    methane_loss_pct: float = 0.0
    product_flow_mols: float = 0.0     # mol/s
    lhv_mj_per_nm3: float | None = None
    hhv_mj_per_nm3: float | None = None
    wobbe_mj_per_nm3: float | None = None
    # dimensionamento do leito
    diameter_m: float = 0.0
    height_m: float = 0.0
    bed_volume_m3: float = 0.0
    superficial_velocity_m_per_s: float = 0.0
    pressure_drop_Pa: float = 0.0
    # meio / vida útil
    media_mass_kg: float = 0.0
    fe2o3_mass_kg: float = 0.0
    h2s_capacity_kg: float | None = None
    life_days: float | None = None
    campaigns_per_yr: float | None = None
    media_kg_per_campaign: float = 0.0
    media_kg_per_yr: float | None = None
    h2s_load_kg_per_day: float | None = None
    sulfur_kg_per_day: float | None = None
    # regeneração in-situ com ar
    air_dose_nm3h: float = 0.0
    oxygen_residual_pct: float = 0.0
    # energia
    blower_kW: float = 0.0
    compression_kW: float = 0.0
    total_kW: float = 0.0
    specific_kWh_per_Nm3: float | None = None
    warnings: tuple[str, ...] = ()


def _ergun_dp(rho_g: float, u_g: float, mu_g: float, d_p: float,
              eps: float, length_m: float) -> float:
    """Queda de pressão num leito granular seco -- equação de Ergun (1952).

    ΔP/L = 150·μ·u·(1-ε)²/(d_p²·ε³) + 1.75·ρ·u²·(1-ε)/(d_p·ε³)
    (Ergun, Chem. Eng. Prog. 48 (1952) 89; válida para meio granular seco --
    o Stichlmair de ``Hydraulics/PressureDrop`` é para recheio de coluna.)
    """
    eps = min(max(eps, 0.25), 0.95)      # guarda de sanidade
    a = 150.0 * mu_g * u_g * (1.0 - eps) ** 2 / (d_p ** 2 * eps ** 3)
    b = 1.75 * rho_g * u_g ** 2 * (1.0 - eps) / (d_p * eps ** 3)
    return length_m * (a + b)


def solve(spec: IronSpongeSpec, composition: dict | None, flow: float,
          T_C: float = 25.0, P_bar: float = 1.10,
          capacity_g_per_g: float | None = None) -> IronSpongeResult:
    """Dimensiona o leito fixo de Fe2O3 e calcula H2S, meio, vida e energia.

    Parâmetros:
        composition: composição do biogás (dict espécie->fração molar).
        flow: vazão de alimentação (mol/s).
        T_C, P_bar: condições do leito (isotérmico; T afeta a vazão real e o ΔP).
        capacity_g_per_g: sobrescreve a capacidade (g H2S/g Fe2O3) da spec.

    O gás tratado contém N2/O2 do ar quando ``regen_mode="in_situ"`` -- a
    pureza de CH4 cai com o N2, efeito real da dosagem de ar.
    """
    comp = dict(composition or {})
    flow = float(flow)
    T_K = float(T_C) + 273.15
    P = float(P_bar) * 1e5
    warnings: list[str] = []
    if T_C > 50.0:
        warnings.append("T > 50 °C: acima do limite do meio de Fe2O3 "
                        "(ótimo 25-40 °C, lit. Wellinger 2013)")

    y_h2s = float(comp.get("H2S", 0.0) or 0.0)
    tau = 15.0      # constante de tempo heurística de remoção (EBCT 100 s -> 99,9 %)
    removal = 1.0 - math.exp(-spec.contact_time_s / tau) if y_h2s > 0 else 1.0

    # vazões (Nm³/s e m³/s reais)
    q_n = flow / MOL_PER_NM3                                  # Nm³/s
    q_actual = q_n * (T_K / 273.15) * (P_NORMAL / P)          # m³/s
    n_h2s_in = flow * y_h2s
    n_h2s_rem = n_h2s_in * removal

    # ---------------- regeneração in-situ: dosagem de ar ---------------- #
    n_o2_dose = n_n2_dose = n_o2_out = n_air = 0.0
    if spec.regen_mode == "in_situ" and n_h2s_rem > 0.0:
        n_o2_dose = O2_PER_H2S * n_h2s_rem * (1.0 + spec.air_excess)
        n_air = n_o2_dose / AIR_O2_FRACTION
        n_n2_dose = (1.0 - AIR_O2_FRACTION) * n_air
        n_o2_out = O2_PER_H2S * n_h2s_rem * spec.air_excess  # residual (excesso)

    # ---------------------- gás tratado (mol/s) ------------------------ #
    treated_mols: dict[str, float] = {}
    for sp, x in comp.items():
        x = float(x or 0.0)
        if x <= 0.0 or sp == "H2S":
            continue
        treated_mols[sp] = flow * x
    if y_h2s > 0.0:
        treated_mols["H2S"] = n_h2s_in * (1.0 - removal)
    if n_n2_dose > 0.0:
        treated_mols["N2"] = treated_mols.get("N2", 0.0) + n_n2_dose
    if n_o2_out > 0.0:
        treated_mols["O2"] = treated_mols.get("O2", 0.0) + n_o2_out
    total_out = sum(treated_mols.values())
    treated_frac = ({sp: n / total_out for sp, n in treated_mols.items()}
                    if total_out > 0 else {})
    treated = normalize_mixture(treated_frac) if treated_frac else {}

    purity = 100.0 * treated_frac.get("CH4", 0.0)
    x_h2s_out = treated_frac.get("H2S", 0.0)
    treated_ppm = x_h2s_out * 1e6
    if y_h2s > 0.0 and treated_ppm > spec.target_H2S_ppm:
        warnings.append(f"H2S tratado ({treated_ppm:.0f} ppm) acima do alvo "
                        f"({spec.target_H2S_ppm:.0f} ppm): aumentar EBCT")

    # ---------------------- dimensionamento do leito ------------------- #
    v_bed = q_actual * spec.contact_time_s                     # m³
    d_hd = (4.0 * v_bed / (math.pi * spec.H_over_D)) ** (1.0 / 3.0)
    d_umax = (4.0 * q_actual / (math.pi * spec.u_max_m_per_s)) ** 0.5
    d = max(d_hd, d_umax)
    h = v_bed / (math.pi * d ** 2 / 4.0)
    u_s = q_actual / (math.pi * d ** 2 / 4.0)
    if h > spec.max_height_m:
        warnings.append(f"Altura do leito ({h:.2f} m) acima do teto prático "
                        f"({spec.max_height_m:.2f} m): usar leitos em série")

    # ----------------------- meio, capacidade e vida ------------------- #
    m_media = v_bed * spec.bulk_density_kg_m3
    m_fe2o3 = spec.fe2o3_wt * m_media
    if capacity_g_per_g is not None:
        cap = float(capacity_g_per_g)
    elif spec.regen_mode == "none":
        cap = spec.capacity_once_through_g_per_g
    else:
        cap = spec.capacity_accumulated_g_per_g
    # 1 g H2S/g Fe2O3 = 1 kg/kg: capacidade (kg) = cap * m_fe2o3 (kg)
    cap_kg = cap * m_fe2o3
    load_kg_d = n_h2s_rem * MM["H2S"] * 86400.0 if y_h2s > 0 else 0.0
    life_days: float | None = None
    campaigns_per_yr: float | None = None
    media_kg_yr: float | None = None
    if load_kg_d > 0.0 and cap_kg > 0.0:
        life_days = cap_kg / load_kg_d
        campaigns_per_yr = 365.25 / life_days
        media_kg_yr = m_media * campaigns_per_yr
        if life_days < 30.0:
            warnings.append(f"Vida útil curta ({life_days:.1f} dias): leito "
                            "pequeno para a carga de H2S")

    # --------------------------- queda de pressão ---------------------- #
    props = (mixture_properties_general(treated, T=T_K, P=P)
             if treated else None)
    rho_g = props.density if props is not None else 1.0
    dp = _ergun_dp(rho_g, u_s, MU_G_DEFAULT, spec.particle_diameter_m,
                   spec.voidage, h)

    # ------------------------------- energia --------------------------- #
    blower_kW = q_actual * dp / spec.blower_eta / 1000.0
    compression_kW = 0.0
    if P > P_NORMAL:
        from ..UnitOperations.base import Stream
        from .Compressor import compress
        species = [sp for sp, x in comp.items() if float(x or 0.0) > 0.0]
        gas_in = Stream.make(species, [float(comp[sp]) for sp in species],
                             flow=flow, T=T_K, P=P_NORMAL, phase="vapor")
        compression_kW = compress(gas_in, P, eta=0.75).work / 1000.0
    total_kW = blower_kW + compression_kW
    bio_nm3h = total_out * 0.0224 * 3600.0
    spec_kwh = total_kW / bio_nm3h if bio_nm3h > 0 else None

    # ------------------------- qualidade do tratado -------------------- #
    lhv = hhv = wobbe = None
    if props is not None:
        lhv, hhv, wobbe = (round(props.LHV_MJ_per_Nm3, 2),
                           round(props.HHV_MJ_per_Nm3, 2),
                           round(props.wobbe_index_MJ_per_Nm3, 2))

    oxygen_residual = (100.0 * treated_frac.get("O2", 0.0)
                       if treated_frac else 0.0)
    if oxygen_residual > spec.o2_residual_limit_pct:
        warnings.append(f"O2 residual ({oxygen_residual:.2f} %) acima do limite "
                        f"de segurança ({spec.o2_residual_limit_pct:.2f} %): "
                        "reduzir excesso de ar")

    # --------------------------- balanço de massa ---------------------- #
    # Fase gás: entra flow + ar; sai flow - H2S retido no leito + N2 + O2 resid.
    n_out_expected = flow - n_h2s_rem + n_n2_dose + n_o2_out
    mbe = abs(total_out - n_out_expected) / flow if flow > 0 else 0.0

    message = ("Leito fixo de Fe2O3: projeto estequiométrico "
               f"(EBCT {spec.contact_time_s:.0f} s, regen={spec.regen_mode})")

    return IronSpongeResult(
        converged=True, iterations=0, message=message,
        treated=treated, mass_balance_error=mbe,
        treated_H2S_ppm=round(treated_ppm, 1) if y_h2s > 0 else 0.0,
        purity_CH4=round(purity, 2),
        recovery_CH4=100.0,
        H2S_removal_pct=round(removal * 100.0, 2) if y_h2s > 0 else None,
        product_flow_mols=total_out,
        lhv_mj_per_nm3=lhv, hhv_mj_per_nm3=hhv, wobbe_mj_per_nm3=wobbe,
        diameter_m=round(d, 3), height_m=round(h, 2),
        bed_volume_m3=round(v_bed, 3),
        superficial_velocity_m_per_s=round(u_s, 4),
        pressure_drop_Pa=round(dp, 1),
        media_mass_kg=round(m_media, 1), fe2o3_mass_kg=round(m_fe2o3, 1),
        h2s_capacity_kg=round(cap_kg, 1) if cap_kg > 0 else None,
        life_days=round(life_days, 1) if life_days is not None else None,
        campaigns_per_yr=(round(campaigns_per_yr, 2)
                          if campaigns_per_yr is not None else None),
        media_kg_per_campaign=round(m_media, 1),
        media_kg_per_yr=round(media_kg_yr, 0) if media_kg_yr is not None else None,
        h2s_load_kg_per_day=round(load_kg_d, 2) if y_h2s > 0 else None,
        sulfur_kg_per_day=(round(load_kg_d * S_PER_H2S_MASS, 2)
                           if y_h2s > 0 else None),
        air_dose_nm3h=(round(n_air * 3600.0 / MOL_PER_NM3, 2)
                       if n_o2_dose > 0 else 0.0),
        oxygen_residual_pct=round(oxygen_residual, 3),
        blower_kW=round(blower_kW, 3),
        compression_kW=round(compression_kW, 2),
        total_kW=round(blower_kW + compression_kW, 2),
        specific_kWh_per_Nm3=round(spec_kwh, 3) if spec_kwh is not None else None,
        warnings=tuple(warnings),
    )


__all__ = ["IronSpongeSpec", "IronSpongeResult", "solve",
           "O2_PER_H2S", "S_PER_H2S_MASS", "AIR_O2_FRACTION", "MU_G_DEFAULT"]
