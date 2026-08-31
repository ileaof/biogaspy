"""Camada de modelo da GUI: estados visuais e barramento de sinais.

Separação modelo-visão (seção do prompt de modernização): o *estado* da
aplicação (alimentação, métricas do último caso, estado visual do solver,
projeto) vive aqui, centralizado; as abas e a janela principal são apenas
visões conectadas por sinais. **Nenhuma ciência mora aqui** -- métricas vêm de
``biogassim.cases``/``biogassim.comparison`` (mesmo backend da CLI).
"""
from __future__ import annotations

from .qt import QObject, Signal

# --------------------------------------------------------------------------- #
# Estados visuais do solver (chip da barra de status + faixas das abas)
# --------------------------------------------------------------------------- #
STATE_READY = "READY"
STATE_RUNNING = "RUNNING"
STATE_CONVERGED = "CONVERGED"
STATE_WARNING = "WARNING"
STATE_FAILED = "FAILED"
STATE_OUTDATED = "OUTDATED"

# (texto, cor de fundo, cor de texto) por estado -- usados como CSS inline.
STATE_STYLE: dict[str, tuple[str, str, str]] = {
    STATE_READY: ("Pronto", "#e8e8e8", "#333"),
    STATE_RUNNING: ("Executando…", "#fff3cd", "#856404"),
    STATE_CONVERGED: ("Convergiu", "#d4edda", "#155724"),
    STATE_WARNING: ("Atenção", "#fff3cd", "#856404"),
    STATE_FAILED: ("Falhou", "#f8d7da", "#721c24"),
    STATE_OUTDATED: ("Desatualizado", "#e2e3e5", "#383d41"),
}


def state_css(state: str) -> str:
    """CSS inline para o chip de estado."""
    _text, bg, fg = STATE_STYLE.get(state, STATE_STYLE[STATE_READY])
    return f"background: {bg}; color: {fg}; font-weight: 600;"


# --------------------------------------------------------------------------- #
# Barramento de sinais: uma instância por janela, compartilhada por todas as
# abas. Substitui a passagem direta de ``main_window`` entre widgets.
# --------------------------------------------------------------------------- #
class AppState(QObject):
    """Estado aplicativo compartilhado + sinais da GUI.

    Signals:
      * ``feed_changed``        -- composição/condições mudaram (marcar obsoleto).
      * ``sim_state_changed``   -- chip de estado do solver mudou.
      * ``metrics_ready``       -- novo resultado de ``cases.run_case`` disponível.
      * ``sweep_ready``         -- varredura/estudo paramétrico concluído.
      * ``comparison_ready``    -- comparação de métodos concluída (rows).
      * ``solver_log``          -- linha para o log do solver.
      * ``project_dirty``       -- estado de projeto não salvo mudou.
      * ``error``               -- erro amigável a ser exibido.
    """

    feed_changed = Signal()
    sim_state_changed = Signal(str)
    metrics_ready = Signal(dict)
    sweep_ready = Signal(list)
    comparison_ready = Signal(list)
    solver_log = Signal(str)
    project_dirty = Signal(bool)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.state = STATE_READY
        #: métricas do último caso executado (fonte p/ Resultados, Desempenho,
        #: Economia e Relatórios). ``None`` = nunca rodou.
        self.metrics: dict | None = None
        #: resultado bruto do caso (AbsorberResult) p/ relatórios, se disponível.
        self.result = None
        #: linhas da última comparação de métodos (fonte p/ Desempenho & Economia).
        self.comparison_rows: list[dict] = []
        self.stale = False

    # -- transições de estado ---------------------------------------------- #
    def set_state(self, state: str):
        self.state = state
        self.sim_state_changed.emit(state)

    def set_metrics(self, metrics: dict, result=None):
        self.metrics = dict(metrics)
        self.result = result
        self.stale = False
        if not metrics.get("converged", False):
            self.set_state(STATE_FAILED)
        else:
            self.set_state(STATE_CONVERGED)
        self.metrics_ready.emit(self.metrics)

    def set_comparison(self, rows: list[dict]):
        self.comparison_rows = list(rows)
        self.comparison_ready.emit(self.comparison_rows)

    # -- obsolescência ------------------------------------------------------ #
    def mark_stale(self):
        """Resultado anterior virou obsoleto (feed/condições mudaram)."""
        if self.stale or self.metrics is None:
            self.stale = self.metrics is not None
            if self.stale:
                self.set_state(STATE_OUTDATED)
            return
        self.stale = True
        self.set_state(STATE_OUTDATED)

    def has_results(self) -> bool:
        return self.metrics is not None

    # -- log ---------------------------------------------------------------- #
    def log(self, line: str):
        self.solver_log.emit(line)


__all__ = [
    "AppState", "STATE_READY", "STATE_RUNNING", "STATE_CONVERGED",
    "STATE_WARNING", "STATE_FAILED", "STATE_OUTDATED", "STATE_STYLE",
    "state_css",
]
