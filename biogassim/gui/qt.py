"""Shim de binding Qt: usa PySide6 (preferido) se instalado, senão PyQt5.

Isola o resto da GUI da diferença entre os dois bindings (ex.: ``Signal`` vs
``pyqtSignal``), de modo que ``from .qt import QtWidgets, Qt, Signal`` funcione
igual nos dois. Levanta ``ImportError`` com mensagem clara se nenhum estiver
disponível.
"""
from __future__ import annotations

QT_BINDING = ""
try:  # preferência do projeto
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import QObject, QSettings, Qt, Signal

    QT_BINDING = "PySide6"
except ImportError:  # pragma: no cover - depende do ambiente
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets
        from PyQt5.QtCore import QObject, QSettings, Qt
        from PyQt5.QtCore import pyqtSignal as Signal

        QT_BINDING = "PyQt5"
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "A GUI requer PySide6 (preferido) ou PyQt5. "
            "Instale um deles: 'pip install PySide6'."
        ) from exc


def exec_app(app) -> int:
    """Executa o loop de eventos de forma compatível (exec/exec_)."""
    run = getattr(app, "exec", None) or app.exec_
    return int(run())


__all__ = ["QtCore", "QtGui", "QtWidgets", "Qt", "Signal", "QObject", "QSettings",
           "QT_BINDING", "exec_app"]

def ensure_app_identity():
    """Garante organização/aplicativo para QSettings (registro/ini) mesmo
    quando a QApplication foi criada fora do app.main() (ex.: testes)."""
    inst = QtCore.QCoreApplication.instance()
    if inst is None:
        return
    if not inst.organizationName():
        inst.setOrganizationName("FEM-ITEC-UFPA")
    if not inst.applicationName():
        inst.setApplicationName("BioGasSim")
