"""Workers (QThread) da GUI: simulação e estudos paramétricos.

A ciência roda inteira fora da thread da GUI (regra do prompt de modernização:
a GUI nunca deve travar durante uma simulação). Os workers são **genéricos**:
recebem callables que chamam o backend compartilhado (``cases``/``studies``/
``comparison``) e apenas transportam resultados/erro via sinais.

Cancelar: ``ParametricWorker`` recebe uma *lista de pontos* (callable, rótulo)
e checa ``should_stop()`` entre pontos; um ponto individual não é interrompido
(o Newton do absorvedor é rápido, <1 s por ponto).
"""
from __future__ import annotations

import traceback

from .qt import QtCore, Signal


def friendly_error(exc: BaseException) -> str:
    """Converte uma exceção em mensagem amigável (sem traceback p/ o usuário).

    Mapeia os erros típicos do backend para texto leigo; erros desconhecidos
    viram o tipo + mensagem curta (a stack completa vai ao log do solver).
    """
    msg = str(exc)
    cls = type(exc).__name__
    if isinstance(exc, ValueError):
        return f"Dado inválido: {msg}"
    if isinstance(exc, KeyError):
        return f"Espécie ou chave desconhecida: {msg}"
    if isinstance(exc, (OverflowError, FloatingPointError)):
        return ("A simulação divergiu numericamente (condições extremas). "
                "Reduza L/V, pressão ou o número de estágios.")
    if isinstance(exc, FileNotFoundError):
        return f"Arquivo não encontrado: {msg}"
    if isinstance(exc, PermissionError):
        return f"Sem permissão para gravar: {msg}"
    if not isinstance(exc, Exception):           # re-raise BaseException raro
        raise exc
    return f"{cls}: {msg.splitlines()[0][:200]}" if msg else f"Erro ({cls})."


class FunctionWorker(QtCore.QThread):
    """Executa ``fn()`` em background; emite ``ok(obj)`` ou ``err(msg)``."""

    ok = Signal(object)
    err = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._traceback = ""

    @property
    def trace_text(self) -> str:
        return self._traceback

    def run(self):
        try:
            self.ok.emit(self._fn())
        except BaseException as exc:  # noqa: BLE001 - transporte p/ GUI thread
            self._traceback = traceback.format_exc()
            self.err.emit(friendly_error(exc))


class ParametricWorker(QtCore.QThread):
    """Varredura paramétrica cancelável.

    ``points``: lista de ``((variável(s), valor(es)), callable)`` -- o callable
    devolve um ``dict`` (as métricas do ponto). Emite ``progress(i, n)`` entre
    pontos, ``ok(rows)`` com todas as linhas no fim.
    """

    progress = Signal(int, int)          # (i+1, n)
    point = Signal(dict)                 # linha pronta (streaming na tabela)
    ok = Signal(list)
    err = Signal(str)

    def __init__(self, points, parent=None):
        super().__init__(parent)
        self._points = points
        self._stop = False
        self._traceback = ""

    @property
    def trace_text(self) -> str:
        return self._traceback

    def stop(self):
        self._stop = True

    def run(self):
        rows = []
        n = len(self._points)
        try:
            for i, (_key, fn) in enumerate(self._points):
                if self._stop:
                    break
                self.progress.emit(i + 1, n)
                row = fn()
                row["_key"] = _key
                rows.append(row)
                self.point.emit(row)
            self.ok.emit(rows)
        except BaseException as exc:  # noqa: BLE001
            self._traceback = traceback.format_exc()
            self.err.emit(friendly_error(exc))


__all__ = ["FunctionWorker", "ParametricWorker", "friendly_error"]
