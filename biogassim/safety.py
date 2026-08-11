"""Segurança de H2S -- avisos de toxicidade/corosividade e limite configurável.

H2S (sulfeto de hidrogênio) é altamente tóxico (Limite IDLH ~50 ppm, TLV-TWA
ACGIH ~1 ppm), corrosivo e odorante (limiar olfativo ~0,0005 ppm, mas o olfato
fadiga rapidamente em concentrações maiores). O simulador NUNCA deve classificar
silenciosamente um gás contendo H2S significativo como adequado para uso em motor.

Este módulo centraliza:
  * o limite máximo admissível de H2S no gás tratado (configurável pelo usuário);
  * geração de avisos distinguindo feed / gás tratado / fase líquida;
  * decisão de adequação para motor.

Convenção de unidades:
  * ``feed_h2s_pct``  -- fração ou % molar de H2S na alimentação (aceita ambos);
  * ``treated_h2s_ppm`` -- ppmv de H2S no gás purificado;
  * ``liquid_h2s_loading`` -- mol H2S / mol solvente (saída líquida).
"""
from __future__ import annotations

# --- limites de referência (não configuráveis, apenas informativos) -------- #
H2S_IDLH_PPM = 50.0          # Immediately Dangerous to Life or Health (NIOSH)
H2S_TLV_TWA_PPM = 1.0         # ACGIH threshold-limit value (8h)
H2S_OLFAC_THRESHOLD_PPM = 0.0005
H2S_ENGINE_TYPICAL_PPM = 10.0     # tolerância típica de motores (referência)
H2S_PIPELINE_PPM = 4.0           # especificação de gasoduto comum (~4 ppmv)

# Limite máximo admissível de H2S no gás tratado (configurável pelo usuário).
# Default: 10 ppm (tolerância típica de motor a gás). Use ``set_max_h2s_treated_ppm``
# para sobrescrever (ex.: 4 ppm p/ injeção em gasoduto).
_MAX_H2S_TREATED_PPM = H2S_ENGINE_TYPICAL_PPM


def max_h2s_treated_ppm() -> float:
    """Limite máximo admissível atual de H2S no gás tratado [ppmv]."""
    return _MAX_H2S_TREATED_PPM


def set_max_h2s_treated_ppm(ppm: float) -> None:
    """Define o limite máximo admissível de H2S no gás tratado [ppmv]."""
    global _MAX_H2S_TREATED_PPM
    if ppm < 0:
        raise ValueError("Limite de H2S deve ser >= 0 ppm.")
    _MAX_H2S_TREATED_PPM = float(ppm)


def _feed_h2s_to_pct(feed_h2s) -> float:
    """Normaliza a fração/percentagem de H2S da alimentação para % molar."""
    v = float(feed_h2s or 0.0)
    return v * 100.0 if v <= 1.0 else v


def h2s_present(feed_h2s) -> bool:
    """True se a alimentação contém H2S em concentração mensurável (> 0)."""
    return float(feed_h2s or 0.0) > 0.0


def h2s_warnings(feed_h2s, treated_h2s_ppm: float = 0.0,
                 liquid_h2s_loading: float | None = None,
                 max_ppm: float | None = None) -> list[str]:
    """Lista de avisos de segurança de H2S.

    Distingue três grandezas (§14): concentração no feed, no gás tratado e na
    fase líquida. Sempre emite um alerta de toxicidade quando H2S está presente
    na alimentação, independentemente da remoção.
    """
    limit = max_ppm if max_ppm is not None else _MAX_H2S_TREATED_PPM
    feed_pct = _feed_h2s_to_pct(feed_h2s)
    warnings: list[str] = []
    if not h2s_present(feed_h2s):
        return warnings
    warnings.append(
        f"[!] H2S presente na alimentacao ({feed_pct:.4f}% mol) -- gas toxico, "
        f"corrosivo e odorante (IDLH {H2S_IDLH_PPM:.0f} ppm, TLV {H2S_TLV_TWA_PPM:.0f} ppm).")
    t_ppm = float(treated_h2s_ppm or 0.0)
    if t_ppm > 0:
        warnings.append(
            f"  Gas tratado: H2S = {t_ppm:.1f} ppm "
            f"(limite admissivel {limit:.1f} ppm).")
    else:
        warnings.append("  Gas tratado: H2S abaixo do limite de relato (~ 0 ppm).")
    if t_ppm > limit:
        warnings.append(
            f"  [X] Gas tratado EXCEDE o limite admissivel de H2S "
            f"({t_ppm:.1f} > {limit:.1f} ppm) -- NAO adequado para motor/gasoduto.")
    if liquid_h2s_loading is not None and float(liquid_h2s_loading) > 0:
        warnings.append(
            f"  Fase liquida: carregamento de H2S = {float(liquid_h2s_loading):.5f} "
            f"mol H2S/mol solvente -- efluente corrosivo, requer stripping/tratamento.")
    if t_ppm > H2S_IDLH_PPM:
        warnings.append(
            f"  [!!] Gas tratado acima do IDLH ({H2S_IDLH_PPM:.0f} ppm) -- risco imediato "
            f"a vida; area deve ser confinada/ventilada e tratada antes de manuseio.")
    return warnings


def engine_suitable(treated_h2s_ppm: float, max_ppm: float | None = None) -> bool:
    """True se o gás tratado atende ao limite de H2S para uso em motor.

    NUNCA retorna True se a concentração de H2S exceder o limite admissível
    (§14: o software nunca classifica silenciosamente gás com H2S significativo
    como adequado para motor).
    """
    limit = max_ppm if max_ppm is not None else _MAX_H2S_TREATED_PPM
    return float(treated_h2s_ppm or 0.0) <= float(limit)


__all__ = [
    "H2S_IDLH_PPM", "H2S_TLV_TWA_PPM", "H2S_OLFAC_THRESHOLD_PPM",
    "H2S_ENGINE_TYPICAL_PPM", "H2S_PIPELINE_PPM",
    "max_h2s_treated_ppm", "set_max_h2s_treated_ppm",
    "h2s_present", "h2s_warnings", "engine_suitable",
]
