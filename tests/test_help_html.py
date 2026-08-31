"""Testes do gerador do manual HTML (docs/HELP.html a partir do README).

Cobre:
  * render() produz HTML bem-formado com masthead, TOC, seções e rodapé;
  * seções numeradas §N a partir dos H2 do README, com ids;
  * TOC aninhado (H2 + H3 filhos);
  * blocos com linguagem viram terminal (.term), sem linguagem viram arch;
  * links/imagens relativos reescritos (docs/ -> relativo a docs/);
  * build_help_html grava o arquivo;
  * CLI ``biogassim help`` localiza/gera o manual.
"""
from __future__ import annotations

import importlib
import os
import pathlib
import re
import subprocess
import sys

from biogassim.Reporting.help_html import build_help_html, render

README = pathlib.Path(__file__).resolve().parents[1] / "README.md"


def _html() -> str:
    return render(README.read_text(encoding="utf-8"))


def test_render_has_masthead_toc_sections_footer():
    h = _html()
    assert "<title>BioGasSim" in h
    assert 'class="masthead"' in h
    assert 'class="eyebrow"' in h
    assert 'Manual de Ajuda' in h
    assert '<nav class="toc">' in h
    assert re.search(r'<section id="[^"]+">', h)
    assert "<footer>" in h
    # autoria no rodapé
    assert "Ivaldo Leão Ferreira" in h
    assert "UFPA" in h


def test_sections_numbered_from_h2():
    h = _html()
    nums = re.findall(r'<span class="num">§(\d+)</span>', h)
    # 11 seções H2 no README (Clonar..Licença)
    assert len(nums) == 11
    assert nums == [str(i) for i in range(1, 12)]


def test_toc_has_nested_h3():
    h = _html()
    toc = re.search(r'<nav class="toc">.*?</nav>', h, re.S).group(0)
    # H2 "Uso rápido (CLI)" agrupa 6 H3 (Comparação..Interface gráfica)
    assert 'href="#uso-rapido-cli"' in toc
    assert 'href="#comparacao-de-metodos-cli"' in toc
    assert 'href="#interface-grafica-gui"' in toc
    # aninhamento: H3 dentro de <ol> filho do <li> do H2
    assert "<ol><li><a href" in toc


def test_code_blocks_classified_term_vs_arch():
    h = _html()
    # blocos com linguagem (bash/python) -> terminal escuro
    assert '<pre class="term">' in h
    # bloco sem linguagem (árvore de arquitetura) -> arch (surface)
    assert '<pre class="arch">' in h


def test_relative_links_and_images_rewritten():
    h = _html()
    # imagem: docs/images/gui.png -> images/gui.png (HELP.html vive em docs/)
    assert 'src="images/gui.png"' in h
    assert 'src="docs/images/' not in h
    # links docs/ARCHITECTURE.md -> ARCHITECTURE.md (mesmo dir)
    assert 'href="ARCHITECTURE.md"' in h
    assert 'href="ROADMAP.md"' in h
    # LICENSE (raiz do repo) -> ../LICENSE
    assert 'href="../LICENSE"' in h


def test_build_help_html_writes_file(tmp_path):
    out = tmp_path / "HELP.html"
    path = build_help_html(README, out)
    assert path == out
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert "BioGasSim" in text


def test_cli_help_locates_or_builds():
    r = subprocess.run(
        [sys.executable, "-m", "biogassim.cli", "help"],
        capture_output=True, text=True, timeout=120,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert r.returncode == 0, r.stderr
    assert "Manual" in r.stdout
    # HELP.html existe em docs/ após o comando
    help_path = pathlib.Path(__file__).resolve().parents[1] / "docs" / "HELP.html"
    assert help_path.exists()


def test_markdown_is_declared_dependency():
    """Regressão: usuários relataram precisar instalar 'markdown' manualmente
    para a ajuda funcionar — o pacote deve estar declarado em requirements.txt
    e no pyproject.toml."""
    root = pathlib.Path(__file__).resolve().parents[1]
    reqs = (root / "requirements.txt").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^markdown>=", reqs, re.M | re.I)
    assert '"markdown>=' in pyproject
    # e o pacote realmente importa (gera o manual sem prerequisite extra)
    importlib.import_module("markdown")
