"""Gerenciamento de projeto da GUI (novo/abrir/salvar/salvar como/recentes).

Um *projeto* BioGasPy é o mesmo formato da CLI: um ``case.json`` serializado
pela :class:`biogassim.cases.Case` (composição + operacionais + configuração de
comparação). A GUI reusa ``save_case``/``load_case``/``validate_case`` -- nada
de serialização duplicada.

Estado sujo (dirty): qualquer edição de alimentação/operacionais marca o
projeto como não salvo; salvar/abrir/limpa. Arquivos recentes persistem em
``QSettings`` (preferência de GUI, não estado de simulação).
"""
from __future__ import annotations

import os

from .qt import QObject, QSettings, Signal, ensure_app_identity

_RECENTS_KEY = "gui/recent_projects"
_MAX_RECENTS = 10


class ProjectManager(QObject):
    """Estado do projeto corrente + I/O em ``case.json`` (backend compartilhado)."""

    #: (path, dirty) -- a janela atualiza título/janela.
    project_changed = Signal(str, bool)

    def __init__(self):
        super().__init__()
        ensure_app_identity()
        self.path: str = ""
        self.dirty = False
        self._settings = QSettings()

    # ------------------------------------------------------------------ #
    # sujeira / caminho
    # ------------------------------------------------------------------ #
    @property
    def has_file(self) -> bool:
        return bool(self.path)

    def display_name(self) -> str:
        if not self.path:
            return "(sem título)"
        return os.path.splitext(os.path.basename(self.path))[0]

    def mark_dirty(self):
        if not self.dirty:
            self.dirty = True
            self.project_changed.emit(self.path, True)

    def mark_clean(self, path: str = ""):
        if path:
            self.path = path
        self.dirty = False
        self.project_changed.emit(self.path, False)

    # ------------------------------------------------------------------ #
    # I/O (delega em biogassim.cases)
    # ------------------------------------------------------------------ #
    def save(self, case) -> str:
        """Salva no caminho corrente (ou levanta ValueError se não há caminho)."""
        if not self.path:
            raise ValueError("Projeto sem arquivo: use Salvar como (save_as).")
        from .. import cases

        p = cases.save_case(case, self.path)
        self.mark_clean(p)
        self.add_recent(p)
        return p

    def save_as(self, case, path: str) -> str:
        from .. import cases

        p = cases.save_case(case, path)
        self.mark_clean(p)
        self.add_recent(p)
        return p

    def load(self, path: str):
        from .. import cases

        case = cases.load_case(path)          # valida + normaliza (backend)
        self.path = os.path.abspath(path)
        self.dirty = False
        self.add_recent(self.path)
        self.project_changed.emit(self.path, False)
        return case

    # ------------------------------------------------------------------ #
    # recentes (QSettings)
    # ------------------------------------------------------------------ #
    def recents(self) -> list[str]:
        val = self._settings.value(_RECENTS_KEY, [])
        if isinstance(val, str):
            val = [val]
        return [p for p in (val or []) if p]

    def add_recent(self, path: str):
        path = os.path.abspath(path)
        recs = [p for p in self.recents() if os.path.normcase(p) != os.path.normcase(path)]
        recs.insert(0, path)
        self._settings.setValue(_RECENTS_KEY, recs[:_MAX_RECENTS])

    @staticmethod
    def _settings_factory():  # pragma: no cover - hook de teste
        return QSettings()


__all__ = ["ProjectManager"]
