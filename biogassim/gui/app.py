"""Ponto de entrada da GUI do BioGasSim."""
from __future__ import annotations

import sys

from .main_window import MainWindow
from .qt import QT_BINDING, QtWidgets, exec_app


def main(argv=None) -> int:
    """Abre a janela principal. Retorna o código de saída do loop de eventos."""
    argv = argv if argv is not None else sys.argv[:1]
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv)
    app.setApplicationName("BioGasSim")
    win = MainWindow()
    win.resize(1000, 660)
    win.show()
    return exec_app(app)


if __name__ == "__main__":
    print(f"BioGasSim GUI ({QT_BINDING})")
    raise SystemExit(main())
