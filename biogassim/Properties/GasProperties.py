"""Composição e propriedades de mistura de gás CH4-CO2 (Milestone 1).

Fornece o motor por trás do editor interativo de composição e do comando de CLI
``props``: normalização/validação da composição binária e o cálculo, em tempo
real, de todas as propriedades da mistura:

* massa molar da mistura;
* fator de compressibilidade Z (Peng-Robinson, real);
* densidade real (a T, P) e densidade normal (Nm³);
* poder calorífico inferior/superior (LHV/HHV) por mol, por Nm³ e por kg;
* Índice de Wobbe (superior);
* densidade relativa ao ar (gas specific gravity).

Convenção de volume normal: 0 °C e 101,325 kPa (22,414 L/mol -> 44,615 mol/Nm³).
Poderes caloríficos de combustão a 25 °C (CH4 combustível; CO2 inerte):
HHV_CH4 = 890,3 kJ/mol, LHV_CH4 = 802,3 kJ/mol (GPSA / NIST).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from ..Core.constants import R_J_MOL_K
from ..Thermodynamics import PengRobinson
from ..Thermodynamics.Interactions import kij_matrix
from .components import get as get_component

# --- constantes de referência --------------------------------------------- #
T_NORMAL = 273.15            # K   (0 °C)
P_NORMAL = 101_325.0         # Pa  (1 atm)
MOL_PER_NM3 = P_NORMAL / (R_J_MOL_K * T_NORMAL)   # ~44.615 mol/Nm³
MM_AIR = 0.028964            # kg/mol (ar seco)

# Gases padrão suportados na parametrização de composição.
DEFAULT_GASES = ["CH4", "CO2", "N2", "O2", "H2", "H2O", "H2S", "NH3", "CO", "Ar"]

# Poderes caloríficos de combustão a 25 °C, kJ/mol -- (HHV, LHV).
# Combustíveis: CH4, H2, H2S, NH3, CO. Inertes/não-combustíveis -> (0, 0).
HEATING_VALUES_KJ_PER_MOL = {
    "CH4": (890.3, 802.3),
    "H2": (285.8, 241.8),
    "CO": (283.0, 283.0),      # sem H2O nos produtos -> HHV ≈ LHV
    "H2S": (562.0, 517.4),
    "NH3": (382.6, 316.8),
    "CO2": (0.0, 0.0),
    "N2": (0.0, 0.0),
    "O2": (0.0, 0.0),
    "H2O": (0.0, 0.0),
    "Ar": (0.0, 0.0),
}


def _heating_values(species: str) -> tuple[float, float]:
    return HEATING_VALUES_KJ_PER_MOL.get(species, (0.0, 0.0))


@dataclass
class GasProperties:
    """Propriedades de uma mistura CH4-CO2 a (T, P)."""
    x_CH4: float
    x_CO2: float
    T: float                       # K
    P: float                       # Pa
    molar_mass: float              # kg/mol
    molar_mass_gmol: float         # g/mol
    Z: float                       # fator de compressibilidade
    density: float                 # kg/m³ (real, a T e P)
    density_normal: float          # kg/Nm³ (0 °C, 1 atm)
    LHV_MJ_per_mol: float
    HHV_MJ_per_mol: float
    LHV_MJ_per_Nm3: float
    HHV_MJ_per_Nm3: float
    LHV_MJ_per_kg: float
    HHV_MJ_per_kg: float
    wobbe_index_MJ_per_Nm3: float  # Índice de Wobbe superior
    specific_gravity: float        # densidade relativa ao ar

    def as_dict(self) -> dict:
        return asdict(self)


def normalize_composition(ch4: float | None = None, co2: float | None = None,
                          tol: float = 1e-9) -> tuple[float, float]:
    """Normaliza e valida uma composição binária CH4-CO2.

    Aceita uma ou ambas as frações (molares **ou** percentuais -- qualquer escala
    positiva; o resultado é sempre normalizado para somar 1). Se apenas uma for
    dada, a complementar é ``1 - x``. Levanta ``ValueError`` para frações
    negativas ou composição nula.

    Devolve ``(x_CH4, x_CO2)`` com ``x_CH4 + x_CO2 = 1``.
    """
    if ch4 is None and co2 is None:
        raise ValueError("Informe a fração de CH4 e/ou de CO2.")
    if ch4 is None:
        ch4 = 1.0 - float(co2)
    if co2 is None:
        co2 = 1.0 - float(ch4)
    ch4, co2 = float(ch4), float(co2)
    if ch4 < -tol or co2 < -tol:
        raise ValueError(f"Frações não podem ser negativas: CH4={ch4}, CO2={co2}.")
    ch4, co2 = max(ch4, 0.0), max(co2, 0.0)
    total = ch4 + co2
    if total <= tol:
        raise ValueError("Composição nula: CH4 + CO2 deve ser > 0.")
    return ch4 / total, co2 / total


def mixture_molar_mass(x_ch4: float, x_co2: float) -> float:
    """Massa molar da mistura (kg/mol)."""
    return x_ch4 * get_component("CH4").MM + x_co2 * get_component("CO2").MM


def compressibility(x_ch4: float, x_co2: float, T: float, P: float) -> float:
    """Fator de compressibilidade Z da mistura (Peng-Robinson, fase vapor)."""
    species = ["CH4", "CO2"]
    eos = PengRobinson([get_component(s) for s in species], kij=kij_matrix(species))
    return float(eos.Z_and_phi(T, P, [x_ch4, x_co2], phase="vapor").Z)


def mixture_properties(ch4: float | None = None, co2: float | None = None,
                       T: float = 298.15, P: float = P_NORMAL) -> GasProperties:
    """Todas as propriedades da mistura CH4-CO2 a ``(T, P)``.

    ``ch4``/``co2`` são normalizados por :func:`normalize_composition`.
    """
    x_ch4, x_co2 = normalize_composition(ch4, co2)
    mm = mixture_molar_mass(x_ch4, x_co2)                 # kg/mol
    Z = compressibility(x_ch4, x_co2, T, P)
    density = P * mm / (Z * R_J_MOL_K * T)                # kg/m³ real
    density_normal = mm * MOL_PER_NM3                     # kg/Nm³ (base ideal)

    hhv_mol = sum(x * HEATING_VALUES_KJ_PER_MOL[s][0]
                  for x, s in ((x_ch4, "CH4"), (x_co2, "CO2"))) / 1000.0   # MJ/mol
    lhv_mol = sum(x * HEATING_VALUES_KJ_PER_MOL[s][1]
                  for x, s in ((x_ch4, "CH4"), (x_co2, "CO2"))) / 1000.0   # MJ/mol
    hhv_nm3 = hhv_mol * MOL_PER_NM3
    lhv_nm3 = lhv_mol * MOL_PER_NM3
    hhv_kg = hhv_mol / mm
    lhv_kg = lhv_mol / mm
    sg = mm / MM_AIR
    wobbe = hhv_nm3 / (sg ** 0.5)

    return GasProperties(
        x_CH4=x_ch4, x_CO2=x_co2, T=T, P=P,
        molar_mass=mm, molar_mass_gmol=mm * 1000.0, Z=Z,
        density=density, density_normal=density_normal,
        LHV_MJ_per_mol=lhv_mol, HHV_MJ_per_mol=hhv_mol,
        LHV_MJ_per_Nm3=lhv_nm3, HHV_MJ_per_Nm3=hhv_nm3,
        LHV_MJ_per_kg=lhv_kg, HHV_MJ_per_kg=hhv_kg,
        wobbe_index_MJ_per_Nm3=wobbe, specific_gravity=sg,
    )


# --------------------------------------------------------------------------- #
# Misturas multicomponente arbitrárias (CH4/CO2/N2/O2/H2/H2O/H2S/NH3/CO/Ar/...)
# --------------------------------------------------------------------------- #
_MOLE_BASES = {"mole", "mole_fraction", "molar", "molar_flow", "volume", "volume_fraction"}
_MASS_BASES = {"mass", "mass_fraction", "mass_flow"}


def to_mole_fractions(values: dict, basis: str = "mole") -> dict:
    """Converte uma composição em frações molares normalizadas (soma = 1).

    ``basis`` aceita: ``mole``/``molar_flow``, ``volume`` (para gás ideal,
    fração volumétrica = fração molar), ``mass``/``mass_flow``. Vazões (molar ou
    mássica) são tratadas como quantidades relativas e normalizadas. Levanta
    ``ValueError`` para valores negativos ou soma nula, e ``KeyError`` para
    espécie não cadastrada.
    """
    if not values:
        raise ValueError("Composição vazia.")
    vals = {k: float(v) for k, v in values.items()}
    if any(v < 0 for v in vals.values()):
        raise ValueError(f"Frações/vazões não podem ser negativas: {vals}.")
    if sum(vals.values()) <= 0:
        raise ValueError("Composição nula: a soma deve ser > 0.")
    b = basis.lower()
    if b in _MASS_BASES:
        moles = {k: vals[k] / get_component(k).MM for k in vals}   # KeyError se desconhecida
    elif b in _MOLE_BASES:
        for k in vals:
            get_component(k)                                        # valida espécie
        moles = vals
    else:
        raise ValueError(f"Base '{basis}' inválida. Use mole/mass/volume/molar_flow/mass_flow.")
    total = sum(moles.values())
    return {k: moles[k] / total for k in moles}


def normalize_mixture(comp: dict, basis: str = "mole") -> dict:
    """Alias explícito de :func:`to_mole_fractions` (normaliza para frações molares)."""
    return to_mole_fractions(comp, basis)


@dataclass
class GasMixture:
    """Propriedades de uma mistura gasosa multicomponente arbitrária a (T, P)."""
    fractions: dict                # frações molares normalizadas
    T: float
    P: float
    molar_mass: float              # kg/mol
    molar_mass_gmol: float         # g/mol
    Z: float
    density: float                 # kg/m³ (real, a T e P)
    density_normal: float          # kg/Nm³
    LHV_MJ_per_mol: float
    HHV_MJ_per_mol: float
    LHV_MJ_per_Nm3: float
    HHV_MJ_per_Nm3: float
    LHV_MJ_per_kg: float
    HHV_MJ_per_kg: float
    wobbe_index_MJ_per_Nm3: float
    specific_gravity: float

    def as_dict(self) -> dict:
        return asdict(self)


def mixture_properties_general(comp: dict, T: float = 298.15, P: float = P_NORMAL,
                               basis: str = "mole") -> GasMixture:
    """Propriedades de uma mistura arbitrária de qualquer subconjunto dos gases.

    Aceita a composição em qualquer ``basis`` (ver :func:`to_mole_fractions`).
    Z e densidade vêm de Peng-Robinson multicomponente; LHV/HHV/Wobbe somam a
    contribuição molar de cada componente combustível.
    """
    x = to_mole_fractions(comp, basis)
    species = list(x)
    comps = [get_component(s) for s in species]
    frac = [x[s] for s in species]

    mm = sum(x[s] * get_component(s).MM for s in species)          # kg/mol
    Z = float(PengRobinson(comps, kij=kij_matrix(species))
              .Z_and_phi(T, P, frac, phase="vapor").Z)
    density = P * mm / (Z * R_J_MOL_K * T)
    density_normal = mm * MOL_PER_NM3

    hhv_mol = sum(x[s] * _heating_values(s)[0] for s in species) / 1000.0   # MJ/mol
    lhv_mol = sum(x[s] * _heating_values(s)[1] for s in species) / 1000.0
    sg = mm / MM_AIR
    hhv_nm3 = hhv_mol * MOL_PER_NM3
    return GasMixture(
        fractions={s: float(x[s]) for s in species}, T=T, P=P,
        molar_mass=mm, molar_mass_gmol=mm * 1000.0, Z=Z,
        density=density, density_normal=density_normal,
        LHV_MJ_per_mol=lhv_mol, HHV_MJ_per_mol=hhv_mol,
        LHV_MJ_per_Nm3=lhv_mol * MOL_PER_NM3, HHV_MJ_per_Nm3=hhv_nm3,
        LHV_MJ_per_kg=lhv_mol / mm, HHV_MJ_per_kg=hhv_mol / mm,
        wobbe_index_MJ_per_Nm3=hhv_nm3 / (sg ** 0.5) if sg > 0 else 0.0,
        specific_gravity=sg,
    )


__all__ = [
    "GasProperties", "GasMixture", "DEFAULT_GASES",
    "normalize_composition", "mixture_molar_mass", "compressibility",
    "mixture_properties", "to_mole_fractions", "normalize_mixture",
    "mixture_properties_general",
    "T_NORMAL", "P_NORMAL", "MOL_PER_NM3", "MM_AIR", "HEATING_VALUES_KJ_PER_MOL",
]
