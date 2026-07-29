"""Exportadores adicionais: Excel, HTML, PDF, Tecplot, VTK.

- Excel e HTML usam pandas (real).
- PDF, Tecplot e VTK são stubs documentados (ver ROADMAP).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def export_excel(tables: dict[str, list[dict[str, Any]]], path) -> None:
    """Cada chave vira uma planilha. Requer openpyxl (opcional)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd
    except ImportError:
        # fallback: salva cada tabela como CSV separado
        for name, rows in tables.items():
            Path(str(path) + f".{name}.csv").write_text(_rows_to_csv(rows), encoding="utf-8")
        return
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for name, rows in tables.items():
            df = pd.DataFrame(rows)
            df.to_excel(w, sheet_name=name[:31], index=False)


def export_html(table: list[dict[str, Any]], path, title: str = "BioGasSim Results") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not table:
        path.write_text("<html><body><p>Sem dados.</p></body></html>", encoding="utf-8")
        return
    keys = list(table[0].keys())
    rows = "".join(
        "<tr>" + "".join(f"<td>{row.get(k, '')}</td>" for k in keys) + "</tr>"
        for row in table
    )
    head = "".join(f"<th>{k}</th>" for k in keys)
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
    <title>{title}</title>
    <style>body{{font-family:sans-serif}} table{{border-collapse:collapse}} td,th{{border:1px solid #999;padding:4px}}</style>
    </head><body><h1>{title}</h1><table><thead><tr>{head}</tr></thead>
    <tbody>{rows}</tbody></table></body></html>"""
    path.write_text(html, encoding="utf-8")


def export_pdf_stub(data, path) -> None:
    """PDF: requer reportlab (não implementado nesta entrega). Ver ROADMAP."""
    Path(path).with_suffix(".txt").write_text(
        "Exportação PDF ainda não implementada (ver ROADMAP). Dados em JSON/CSV anexos.",
        encoding="utf-8")


def export_tecplot_stub(profile, path) -> None:
    """Tecplot: stub. Formato .plt requer biblioteca específica (ROADMAP)."""
    Path(path).write_text("VARIABLES = stage, value\nZONE\n# stub Tecplot\n", encoding="utf-8")


def export_vtk_stub(grid, path) -> None:
    """VTK: estruturado para visualização 3D da coluna (ROADMAP)."""
    Path(path).write_text("# vtk DataFile Version 3.0\nBioGasSim\nASCII\n\n", encoding="utf-8")


def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
    import csv
    import io
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return buf.getvalue()


__all__ = ["export_excel", "export_html", "export_pdf_stub",
           "export_tecplot_stub", "export_vtk_stub"]
