"""Captura docs/images/gui.png renderizando a MainWindow em modo offscreen.

Roda um caso (preenche a tabela de resultados) e a varredura de H2S (preenche
o mapa de desempenho), depois grava o pixmap da janela. Usado apenas para
atualizar a imagem do README/HELP.html -- não é um teste.
"""
from __future__ import annotations

import os
import pathlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from biogassim.gui.qt import QtWidgets, exec_app  # noqa: E402
from biogassim.gui.main_window import MainWindow  # noqa: E402


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    w = MainWindow()
    w.resize(1580, 1040)
    # garante a aba Simulação visível
    w.tabs.setCurrentIndex(0)
    w.show()
    app.processEvents()
    # popula resultados + mapa de desempenho
    try:
        w._on_run()
    except Exception as exc:  # pragma: no cover
        print("run falhou:", exc)
    app.processEvents()
    try:
        w._on_sweep()
    except Exception as exc:  # pragma: no cover
        print("sweep falhou:", exc)
    if getattr(w, "canvas", None) is not None:
        try:
            w.canvas.draw()
        except Exception:  # pragma: no cover
            pass
    app.processEvents()
    # captura a janela inteira (menu + abas + conteúdo)
    pm = w.grab()
    out = pathlib.Path(__file__).resolve().parent / "images" / "gui.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    pm.save(str(out))
    print(f"OK -> {out}  ({pm.width()}x{pm.height()})")
    w.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())