"""Ponto de entrada da GUI do BioGasSim."""
from __future__ import annotations

import sys


def main(argv=None) -> int:
    """Abre a janela principal. Retorna o código de saída do loop de eventos."""
    argv = argv if argv is not None else sys.argv[:1]
    from .qt import QSettings, QtWidgets, exec_app

    # High-DPI: Qt6 (PySide6) faz isso automaticamente; ativa no PyQt5.
    try:
        from PyQt5 import QtCore as _qc  # noqa: F401  (só no fallback PyQt5)
        _qc.QApplication.setAttribute(_qc.Qt.AA_EnableHighDpiScaling, True)
    except ImportError:
        pass

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv)
    app.setApplicationName("BioGasSim")
    app.setOrganizationName("FEM-ITEC-UFPA")
    QSettings().setDefaultFormat(QSettings.IniFormat)  # preferências de GUI

    from .main_window import MainWindow
    win = MainWindow()
    geo = QSettings().value("gui/main_window/geometry")
    if geo is not None:
        try:
            win.restoreGeometry(geo)
        except Exception:
            pass
    else:
        win.resize(1280, 800)
    win.show()
    return exec_app(app)


if __name__ == "__main__":
    print(f"BioGasSim GUI ({__import__('biogassim.gui.qt', fromlist=['QT_BINDING']).QT_BINDING})")
    raise SystemExit(main())
