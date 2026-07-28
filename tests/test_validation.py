"""Validação contra valores de referência da literatura.

Pontos de validação:
  * Z de CH4 e CO2 via Peng-Robinson no limite de gás ideal (Z -> 1) e em
    regime não-ideal moderado (Z < 1 para CO2).
  * Solubilidade de CO2 em água a 25 °C: 0,034 mol/(L.atm) (Sander 2015).
  * Equilíbrio CO2-MEA 30% mássico a 40 °C vs dados de Aronu et al. (2011)
    (mesmo sistema de Jou, Mather & Otto 1995): p_CO2(α) dentro de um fator
    ~4 (modelo Kent-Eisenberg aparente, sem coef. de atividade).
  * Balanço de massa do absorvedor fecha em precisão de máquina.

Referências:
  - Sander, R. (2015). Compilation of Henry's law constants. Atmos. Chem. Phys.
  - Jou, Mather & Otto (1995). CJChE 73(1), 140-147.
  - Aronu et al. (2011). Chem. Eng. Sci. 66, 6393-6406.
"""
import numpy as np
import pytest

from biogassim.Properties.components import get
from biogassim.Thermodynamics.PengRobinson import PengRobinson
from biogassim.Thermodynamics.Henry import henry_water
from biogassim.Solvents.KentEisenberg import KentEisenberg


# ------------------------- EOS (Peng-Robinson) ------------------------- #
def test_pr_Z_ideal_limit_methane():
    """CH4 a 298,15 K e 1 atm -> Z ~ 0,9981 (gás quasi-ideal)."""
    eos = PengRobinson([get("CH4")])
    Z = eos.Z_and_phi(298.15, 101325.0, np.array([1.0]), phase="vapor").Z
    assert abs(Z - 0.9981) < 0.01, f"Z={Z:.4f}"


def test_pr_Z_ideal_limit_co2():
    """CO2 a 298,15 K e 1 atm -> Z ~ 0,9933."""
    eos = PengRobinson([get("CO2")])
    Z = eos.Z_and_phi(298.15, 101325.0, np.array([1.0]), phase="vapor").Z
    assert abs(Z - 0.9933) < 0.01, f"Z={Z:.4f}"


def test_pr_Z_co2_nonideal_decreases_with_pressure():
    """CO2 é mais não-ideal que CH4: a 10 bar, Z_CO2 < Z_CH4 < 1."""
    eos_c = PengRobinson([get("CO2")])
    eos_m = PengRobinson([get("CH4")])
    Zc = eos_c.Z_and_phi(298.15, 1.0e6, np.array([1.0]), phase="vapor").Z
    Zm = eos_m.Z_and_phi(298.15, 1.0e6, np.array([1.0]), phase="vapor").Z
    assert Zc < Zm < 1.0, f"Zc={Zc:.4f} Zm={Zm:.4f}"


# ------------------------- Henry (CO2 em água) ------------------------- #
def test_henry_CO2_water_literature():
    """HCP de CO2 em água a 25 °C = 0,034 mol/(L.atm) (Sander 2015)."""
    hl = henry_water()
    H = hl.H("CO2", 298.15)            # Pa
    Vm = 18.0e-6                        # m3/mol (água)
    hcp = 1.0 / (H * Vm) * 101325.0 / 1000.0    # mol/(L.atm)
    assert abs(hcp - 0.034) < 0.004, f"hcp={hcp:.4f}"


# ------------------------- Kent-Eisenberg vs Aronu --------------------- #
# Aronu et al. (2011) -- 30 wt% MEA, 40 C: (carregamento alpha, p_CO2 kPa)
ARONU_40C = [
    (0.102, 0.0016), (0.206, 0.0123), (0.250, 0.0246), (0.337, 0.0603),
    (0.353, 0.0851), (0.401, 0.1835), (0.417, 0.2928), (0.433, 0.3809),
    (0.447, 0.5702), (0.464, 1.0662), (0.476, 1.8326), (0.485, 2.3193),
    (0.489, 2.8577), (0.516, 8.5583), (0.524, 11.812),
]


def test_kent_eisenberg_vs_aronu_all_points():
    """p_CO2 do modelo Kent-Eisenberg dentro de fator 5 de Aronu et al. em
    todo o intervalo (modelo aparente, sem coef. de atividade)."""
    ke = KentEisenberg()
    T, m = 313.15, 4.9
    for alpha, p_lit_kPa in ARONU_40C:
        p_mod = ke.pCO2(alpha, T, m) / 1000.0
        ratio = p_mod / p_lit_kPa
        assert 0.2 < ratio < 5.0, f"alpha={alpha}: model={p_mod:.4f} lit={p_lit_kPa:.4f}"


def test_kent_eisenberg_vs_aronu_operating_range():
    """Na faixa de operação do absorvedor (alpha 0,20-0,48, carregamento
    magro->rico típico), o desvio fica dentro de fator 3. No pinch muito
    íngreme (alpha > 0,48) o modelo aparente subestima p_CO2 -- fenômeno
    conhecido, requer coef. de atividade (Deshmukh-Mather / e-NRTL)."""
    ke = KentEisenberg()
    T, m = 313.15, 4.9
    for alpha, p_lit_kPa in ARONU_40C:
        if not 0.20 <= alpha <= 0.476:
            continue
        p_mod = ke.pCO2(alpha, T, m) / 1000.0
        ratio = p_mod / p_lit_kPa
        assert 0.33 < ratio < 3.0, f"alpha={alpha}: ratio={ratio:.2f}"


def test_kent_eisenberg_pco2_monotonic_in_loading():
    """p_CO2 cresce estritamente com o carregamento (isoterma de equilíbrio)."""
    ke = KentEisenberg()
    T, m = 313.15, 4.9
    alphas = np.linspace(0.05, 0.52, 20)
    p = [ke.pCO2(a, T, m) for a in alphas]
    assert all(p[i] < p[i + 1] for i in range(len(p) - 1))


def test_kent_eisenberg_pco2_increases_with_temperature():
    """Carregamento fixo: p_CO2 cresce com T (menos solúvel em T maior)."""
    ke = KentEisenberg()
    m = 4.9
    p_cold = ke.pCO2(0.4, 313.15, m)
    p_hot = ke.pCO2(0.4, 353.15, m)
    assert p_hot > p_cold


# ------------------------- Kent-Eisenberg MDEA vs Huttenhuis -------------- #
# Huttenhuis et al. (2007), Chem. Eng. Sci. 62, 6887-6901 -- 35 wt% MDEA
# (m = 3,05 mol/L): (carregamento alpha, p_CO2 kPa). Pontos representativos
# (centro da faixa experimental reportada em cada T).
HUTTENHUIS_MDEA_298K = [
    (0.050, 0.19), (0.140, 1.10), (0.270, 3.70), (0.320, 5.50),
]
HUTTENHUIS_MDEA_283K = [
    (0.048, 0.054), (0.143, 0.35), (0.276, 1.22), (0.320, 1.70),
]
# MDEA calibrado: log β1 = 8,634 (≈ pKa 8,65), ΔH1 = -41,97 kJ/mol
MDEA_KE = KentEisenberg(amine="MDEA", log_beta1=8.634, log_beta2=0.0,
                         dH1=-41971.0, dH2=0.0)


def test_mdea_vs_huttenhuis_298k_all_points():
    """p_CO2 do modelo MDEA calibrado dentro de fator ~2,4 de Huttenhuis (2007)
    a 298,15 K (35 wt%, m=3,05 mol/L) em todo o intervalo de carregamento."""
    T, m = 298.15, 3.05
    for alpha, p_lit_kPa in HUTTENHUIS_MDEA_298K:
        p_mod = MDEA_KE.pCO2(alpha, T, m) / 1000.0
        ratio = p_mod / p_lit_kPa
        assert 0.4 < ratio < 2.5, f"alpha={alpha}: model={p_mod:.3f} lit={p_lit_kPa:.3f} r={ratio:.2f}"


def test_mdea_vs_huttenhuis_283k_all_points():
    """Mesma calibração (com ΔH1) reproduz a 283,15 K dentro de fator ~2,4 --
    valida a dependência de temperatura, não só o ajuste a 298 K."""
    T, m = 283.15, 3.05
    for alpha, p_lit_kPa in HUTTENHUIS_MDEA_283K:
        p_mod = MDEA_KE.pCO2(alpha, T, m) / 1000.0
        ratio = p_mod / p_lit_kPa
        assert 0.4 < ratio < 2.5, f"alpha={alpha}: model={p_mod:.3f} lit={p_lit_kPa:.3f} r={ratio:.2f}"


def test_mdea_vs_huttenhuis_midrange_tight():
    """Na faixa de operação do absorvedor (α 0,10-0,28), desvio dentro de
    fator 1,5 -- o modelo é mais preciso onde a coluna realmente opera."""
    T, m = 298.15, 3.05
    for alpha, p_lit_kPa in HUTTENHUIS_MDEA_298K:
        if not 0.10 <= alpha <= 0.28:
            continue
        p_mod = MDEA_KE.pCO2(alpha, T, m) / 1000.0
        ratio = p_mod / p_lit_kPa
        assert 0.6 < ratio < 1.6, f"alpha={alpha}: ratio={ratio:.2f}"


def test_mdea_pco2_monotonic_and_temperature_dependent():
    """MDEA: p_CO2 cresce com α e com T; a 283 K < 298 K no mesmo α (exotérmico)."""
    m = 3.05
    alphas = np.linspace(0.05, 0.32, 8)
    p298 = [MDEA_KE.pCO2(a, 298.15, m) for a in alphas]
    assert all(p298[i] < p298[i + 1] for i in range(len(p298) - 1))
    for a in alphas:
        assert MDEA_KE.pCO2(a, 283.15, m) < MDEA_KE.pCO2(a, 298.15, m)


# ------------------------- Balanço do absorvedor ----------------------- #
def test_absorber_mass_balance_machine_precision():
    """Balanço global de massa fecha em ~1e-10 (Newton global consistente)."""
    from biogassim.UnitOperations import Stream, Absorber, AbsorberSpec
    from biogassim.Solvents import MEASolvent
    from biogassim.Properties.components import get as gcomp
    species = ["CH4", "CO2", "H2O", "MEA"]
    gas = Stream.make(species, [0.47, 0.53, 0.0, 0.0], 100.0, 313.15, 2e5, "vapor")
    mm_mea, mm_w, w = gcomp("MEA").MM, gcomp("H2O").MM, 0.30
    x_mea = (w / mm_mea) / (w / mm_mea + (1 - w) / mm_w)
    solv = Stream.make(species, [0.0, 0.0, 1 - x_mea, x_mea], 2000.0, 313.15, 2e5, "liquid")
    spec = AbsorberSpec(N_stages=8, mode="isothermal", T_op=313.15,
                        pressure=2e5, height=12.0, max_iter=400)
    r = Absorber(gas, solv, MEASolvent(), spec).solve()
    feed = gas.z * gas.flow + solv.z * solv.flow
    out = r.gas_out.z * r.gas_out.flow + r.liquid_out.z * r.liquid_out.flow
    assert np.allclose(feed, out, atol=1e-9), f"feed={feed}, out={out}"


# ------------------------- Balanço de energia (adiabático) ------------- #
def test_absorber_adiabatic_temperature_rise():
    """Modo adiabático: a absorção exotérmica eleva a temperatura e o balanço
    de massa fecha. Verifica a 'temperature bulge' na ponta rica."""
    from biogassim.UnitOperations import Stream, Absorber, AbsorberSpec
    from biogassim.Solvents import MEASolvent
    from biogassim.Properties.components import get as gcomp
    species = ["CH4", "CO2", "H2O", "MEA"]
    gas = Stream.make(species, [0.47, 0.53, 0.0, 0.0], 100.0, 313.15, 2e5, "vapor")
    mm_mea, mm_w, w = gcomp("MEA").MM, gcomp("H2O").MM, 0.30
    x_mea = (w / mm_mea) / (w / mm_mea + (1 - w) / mm_w)
    solv = Stream.make(species, [0.0, 0.0, 1 - x_mea, x_mea], 2000.0, 313.15, 2e5, "liquid")
    spec = AbsorberSpec(N_stages=8, mode="adiabatic", T_op=313.15,
                        pressure=2e5, height=12.0, max_iter=400)
    r = Absorber(gas, solv, MEASolvent(), spec).solve()
    assert r.converged
    # balanço de massa fecha
    feed = gas.z * gas.flow + solv.z * solv.flow
    out = r.gas_out.z * r.gas_out.flow + r.liquid_out.z * r.liquid_out.flow
    assert np.allclose(feed, out, atol=1e-6), f"feed={feed}, out={out}"
    # calor de absorção liberado -> T sobe acima da alimentação
    T_profile = r.T_profile
    assert T_profile.max() > 313.15 + 1.0, f"T_max={T_profile.max():.2f}"
    # bulge na ponta rica: fundo (estágio N) mais quente que o topo (estágio 1)
    assert T_profile[-1] > T_profile[0], f"T_bot={T_profile[-1]:.2f} T_top={T_profile[0]:.2f}"
    # nenhum estágio esfria abaixo da entrada mais fria (物理)
    assert T_profile.min() >= min(gas.T, solv.T) - 0.5


def test_absorber_adiabatic_energy_balance_order():
    """O aumento de temperatura observado é da ordem do esperado:
        ΔT ~ (CO2 absorvido · ΔH_abs) / (L · cp_l)
    Confirma que o balanço de energia está na magnitude correta."""
    from biogassim.UnitOperations import Stream, Absorber, AbsorberSpec
    from biogassim.Solvents import MEASolvent
    from biogassim.Properties.components import get as gcomp
    species = ["CH4", "CO2", "H2O", "MEA"]
    gas = Stream.make(species, [0.47, 0.53, 0.0, 0.0], 100.0, 313.15, 2e5, "vapor")
    mm_mea, mm_w, w = gcomp("MEA").MM, gcomp("H2O").MM, 0.30
    x_mea = (w / mm_mea) / (w / mm_mea + (1 - w) / mm_w)
    solv = Stream.make(species, [0.0, 0.0, 1 - x_mea, x_mea], 2000.0, 313.15, 2e5, "liquid")
    spec = AbsorberSpec(N_stages=8, mode="adiabatic", T_op=313.15,
                        pressure=2e5, height=12.0, max_iter=400)
    r = Absorber(gas, solv, MEASolvent(), spec).solve()
    ic = species.index("CO2")
    co2_abs = gas.z[ic] * gas.flow - r.gas_out.z[ic] * r.gas_out.flow
    Habs = MEASolvent().heat_of_absorption("CO2")
    cp_l = MEASolvent().cp_liquid(313.15)        # J/(mol·K)
    dT_est = co2_abs * Habs / (solv.flow * cp_l)
    dT_obs = r.T_profile.max() - 313.15
    # concordância dentro de fator 3 (calor distribuído entre fases e estágios)
    assert 0.2 < dT_obs / dT_est < 3.0, f"ΔT_obs={dT_obs:.1f} ΔT_est={dT_est:.1f}"


# ------------------------- Solventes físicos vs literatura --------------- #
# Constantes de Henry H [Pa] (P·y = H·x) dos solventes físicos calibradas:
#   Selexol (DEPG): Henni et al. (2005) + Burr & Lyddon (seletividades).
#   Rectisol (metanol): Décultot et al. (2019) p/ CO2 (série T), Leu &
#     Robinson (1992) p/ H2S, Brunner (1987) p/ CH4.
# H recuperado como K_value·P e comparado aos valores tabulados em MPa (×1e6).
from biogassim.Solvents import SelexolSolvent, RectisolSolvent

_SELEXOL = SelexolSolvent()
_RECTISOL = RectisolSolvent()


def test_selexol_henry_absolute_matches_henni():
    """H(CO2) e H(CH4) em DEPG a 298 K vs Henni et al. (2005): 3,0 e 38 MPa."""
    T, P = 298.15, 1.0e5
    H_co2 = _SELEXOL.K_value("CO2", T, P, [0, 1, 0, 0]) * P / 1.0e6    # MPa
    H_ch4 = _SELEXOL.K_value("CH4", T, P, [1, 0, 0, 0]) * P / 1.0e6
    assert abs(H_co2 - 3.0) / 3.0 < 0.15, f"H_CO2={H_co2:.2f} MPa"
    assert abs(H_ch4 - 38.0) / 38.0 < 0.15, f"H_CH4={H_ch4:.1f} MPa"


def test_selexol_h2s_co2_selectivity_burr_lyddon():
    """Seletividade H2S/CO2 em DEPG ~8,8 (Burr & Lyddon): H_CO2/H_H2S ~8-10."""
    T, P = 298.15, 1.0e5
    H_co2 = _SELEXOL.K_value("CO2", T, P, [0, 1, 0, 0]) * P
    H_h2s = _SELEXOL.K_value("H2S", T, P, [0, 0, 0, 1]) * P
    sel = H_co2 / H_h2s
    assert 7.0 < sel < 11.0, f"H2S/CO2 selectivity={sel:.1f}"


def test_rectisol_co2_henry_absolute_matches_decultot():
    """H(CO2) em metanol a 298 K ~142 MPa (Décultot et al. 2019)."""
    T, P = 298.15, 1.0e5
    H = _RECTISOL.K_value("CO2", T, P, [0, 1, 0, 0]) * P / 1.0e6
    assert abs(H - 142.0) / 142.0 < 0.10, f"H_CO2={H:.1f} MPa"


def test_rectisol_co2_temperature_series_decultot():
    """A dH regressada reproduz a série de Décultot: 103 MPa @283, 185 @313 K
    (valida a dependência de temperatura, não só o ponto a 298 K)."""
    P = 1.0e5
    H283 = _RECTISOL.K_value("CO2", 283.15, P, [0, 1, 0, 0]) * P / 1.0e6
    H313 = _RECTISOL.K_value("CO2", 313.15, P, [0, 1, 0, 0]) * P / 1.0e6
    assert abs(H283 - 103.0) / 103.0 < 0.08, f"H@283={H283:.1f} MPa"
    assert abs(H313 - 185.0) / 185.0 < 0.08, f"H@313={H313:.1f} MPa"


def test_rectisol_h2s_henry_matches_leu_robinson():
    """H(H2S) em metanol a 298 K ~5 MPa (Leu & Robinson 1992, diluição inf.)."""
    T, P = 298.15, 1.0e5
    H = _RECTISOL.K_value("H2S", T, P, [0, 0, 0, 1]) * P / 1.0e6
    assert 2.5 < H < 10.0, f"H_H2S={H:.2f} MPa"


def test_rectisol_h2s_more_soluble_than_co2():
    """Rectisol é seletivo a H2S: H(H2S) << H(CO2) a 298 K (seletividade >10)."""
    T, P = 298.15, 1.0e5
    H_co2 = _RECTISOL.K_value("CO2", T, P, [0, 1, 0, 0]) * P
    H_h2s = _RECTISOL.K_value("H2S", T, P, [0, 0, 0, 1]) * P
    assert H_co2 / H_h2s > 10.0, f"selectivity={H_co2/H_h2s:.1f}"


def test_physical_solvents_more_soluble_than_water():
    """CO2 é muito mais solúvel em DEPG (~55x) e em metanol que em água."""
    from biogassim.Thermodynamics.Henry import henry_water
    hl = henry_water()
    H_water = hl.H("CO2", 298.15)                          # Pa
    H_selexol = _SELEXOL.K_value("CO2", 298.15, 1e5, [0, 1, 0, 0]) * 1e5
    H_methanol = _RECTISOL.K_value("CO2", 298.15, 1e5, [0, 1, 0, 0]) * 1e5
    # Selexol: ~55x mais solúvel (H ~55x menor); metanol também mais solúvel
    assert H_water / H_selexol > 40.0, f"DEPG/water={H_water/H_selexol:.1f}"
    assert H_water / H_methanol > 1.0, f"MeOH/water={H_water/H_methanol:.2f}"