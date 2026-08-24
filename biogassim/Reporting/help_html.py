"""Gera :file:`docs/HELP.html` a partir do :file:`README.md`.

Converte o Markdown do README em um manual HTML no estilo do ``MANUAL.html`` de
referência: sumário lateral fixo (TOC), cabeçalho (masthead) com chips, seções
numeradas (§N), tabelas, blocos de código/terminal, tema claro/escuro e rodapé.
O motor de cálculo referenciado é o do próprio pacote — nenhuma termodinâmica é
duplicada aqui.

Uso::

    python -m biogassim.Reporting.help_html            # escreve docs/HELP.html
    python -m biogassim.Reporting.help_html --check     # só valida, sem escrever
"""
from __future__ import annotations

import argparse
import html as _html
import pathlib
import re
import sys

import markdown

__all__ = ["build_help_html", "render", "main"]

ROOT = pathlib.Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
OUT = ROOT / "docs" / "HELP.html"

# chips do masthead (rótulos curtos, independentes da contagem de testes)
_CHIPS: list[tuple[str, str]] = [
    ("ok", "Water Scrubbing + MEA validados"),
    ("ok", "Newton global · adiabático"),
    ("", "Peng-Robinson · Henry · Kent-Eisenberg"),
    ("", "GUI PySide6 / PyQt5"),
    ("", "CLI · casos · comparação de métodos"),
]

_MD_EXT = ["toc", "tables", "fenced_code", "sane_lists", "attr_list"]
_MD_CFG = {"toc": {"permalink": False}}


# ------------------------------- CSS (estilo MANUAL.html) ------------------- #
_CSS = r"""
  :root{
    --ground:#F4F7FA; --surface:#EAF1EA; --surface-2:#DDE7DD;
    --ink:#16271E; --ink-soft:#415A4A; --ink-faint:#6B8073;
    --ink-2:var(--ink-soft); --ink-3:var(--ink-faint);
    --rule:#C9D6CC; --rule-soft:#DCE6DC;
    --bio:#1F8A5B;  /* biometano - verde */
    --gas:#2E6F9E;  /* gás - azul */
    --warm:#C2812B;  /* destaque - âmbar */
    --crit:#B4453B;
    --term-bg:#0C161A; --term-ink:#DCE6EE; --term-dim:#7E92A0;
    --accent:var(--bio); --cold:var(--gas); --warm:var(--warm);
    --ok:#1E7A4C;
    --code-bg:var(--surface); --warn-bg:#F6ECE1; --warn-rule:#C9A469;
    --maxw:860px;
    --serif:"Iowan Old Style","Palatino Linotype","Palatino",Georgia,"Times New Roman",serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
    --mono:"JetBrains Mono","SF Mono","Cascadia Code",Consolas,"Liberation Mono",monospace;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --ground:#0E1512; --surface:#16221E; --surface-2:#1E2C26;
      --ink:#DCE6EE; --ink-soft:#A6B6AE; --ink-faint:#7E9088;
      --rule:#243028; --rule-soft:#1E2A24;
      --bio:#4ADE80; --gas:#5FA8D6; --warm:#D69A4A; --crit:#E07060;
      --term-bg:#070D0B; --term-ink:#DCE6EE; --term-dim:#5E7270;
      --ok:#4ADE80; --warn-bg:#261A12; --warn-rule:#B9763A;
    }
  }
  :root[data-theme="dark"]{
    --ground:#0E1512; --surface:#16221E; --surface-2:#1E2C26;
    --ink:#DCE6EE; --ink-soft:#A6B6AE; --ink-faint:#7E9088;
    --rule:#243028; --rule-soft:#1E2A24;
    --bio:#4ADE80; --gas:#5FA8D6; --warm:#D69A4A; --crit:#E07060;
    --term-bg:#070D0B; --term-ink:#DCE6EE; --term-dim:#5E7270;
    --ok:#4ADE80; --warn-bg:#261A12; --warn-rule:#B9763A;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{
    margin:0; background:var(--ground); color:var(--ink);
    font-family:var(--sans); font-size:16.5px; line-height:1.62;
    -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  }
  a{color:var(--accent); text-decoration:none}
  a:hover{text-decoration:underline}
  h1,h2,h3,h4{font-family:var(--serif); font-weight:700; line-height:1.18; text-wrap:balance; letter-spacing:-.005em}
  .mf{font-style:italic; color:var(--warm); font-family:var(--serif)}
  code,.mono{font-family:var(--mono)}
  strong{color:var(--ink)}

  /* layout */
  .shell{display:grid; grid-template-columns:248px minmax(0,1fr); gap:52px; max-width:1200px; margin:0 auto; padding:0 28px}
  @media (max-width:960px){ .shell{grid-template-columns:1fr; gap:0} }

  /* TOC */
  .toc{position:sticky; top:0; align-self:start; max-height:100vh; overflow-y:auto;
    padding:28px 0 34px; font-size:13px; line-height:1.5; color:var(--ink-soft)}
  @media (max-width:960px){ .toc{position:static; max-height:none; padding:12px 0 8px; border-bottom:1px solid var(--rule)} }
  .toc h4{font-family:var(--sans); font-size:10.5px; font-weight:600; letter-spacing:.11em;
    text-transform:uppercase; color:var(--ink-faint); margin:20px 0 4px}
  .toc h4:first-child{margin-top:0}
  .toc ol{list-style:none; padding:0; margin:0 0 6px}
  .toc li{margin:2px 0}
  .toc a{color:var(--ink-soft); display:block; padding:4px 10px; border-radius:3px; border-left:2px solid transparent; line-height:1.35}
  .toc a:hover{background:var(--surface); color:var(--ink); text-decoration:none}
  .toc a.active{color:var(--accent); border-left-color:var(--accent); background:var(--surface)}
  .toc ol ol{margin:2px 0 2px; padding-left:12px}
  .toc ol ol a{font-size:12px; padding:2px 8px}

  /* main */
  .doc{min-width:0; max-width:var(--maxw); padding:0 0 90px}
  section{padding-top:34px; margin-top:16px; border-top:1px solid var(--rule-soft)}
  .part + section{border-top:none; margin-top:0; padding-top:22px}
  h2{font-size:27px; margin:0 0 8px; scroll-margin-top:1rem}
  h2 .num{font-family:var(--mono); font-size:14px; font-weight:500; color:var(--accent); letter-spacing:0; margin-right:.5em; vertical-align:.02em}
  h3{font-size:19px; margin:26px 0 4px; color:var(--ink); scroll-margin-top:1rem}
  h4{font-size:15.5px; margin:20px 0 2px; font-family:var(--sans); font-weight:600; letter-spacing:.01em}
  p{margin:10px 0}
  ul,ol{padding-left:1.3em}
  li{margin:3px 0}
  code{font-size:.85em; background:var(--surface); padding:1px 5px; border-radius:4px; color:var(--ink)}

  /* eyebrow */
  .eyebrow{font-family:var(--sans); font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); font-weight:600; margin:0 0 6px}

  /* masthead / hero */
  .masthead{padding:44px 0 4px}
  h1.title{font-family:var(--serif); font-size:40px; margin:0 0 10px; letter-spacing:-.01em; line-height:1.1}
  .lede{font-family:var(--serif); font-size:18px; color:var(--ink-soft); max-width:60ch; margin:.6rem 0 1rem; line-height:1.5}
  .chips{display:flex; flex-wrap:wrap; gap:8px; margin:16px 0 6px}
  .chip{font-family:var(--sans); font-size:12px; padding:5px 11px; border:1px solid var(--rule); border-radius:999px; color:var(--ink-soft); background:var(--surface)}
  .chip.ok{border-color:var(--ok); color:var(--ok)}

  .duo-rule{height:4px; border:none; border-radius:2px; margin:26px 0; background:linear-gradient(90deg,var(--warm),var(--cold))}
  hr.divider{border:none; border-top:1px solid var(--rule-soft); margin:32px 0}

  /* part dividers */
  .part{margin:40px 0 8px; padding-top:22px; border-top:2px solid var(--rule)}
  .part .pk{font-family:var(--sans); font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--warm); font-weight:600; margin:0 0 4px}
  .part h2{font-family:var(--serif); font-size:30px; margin:0 0 6px}
  .part .psub{color:var(--ink-soft); margin:0 0 6px; font-size:15px; font-family:var(--serif); max-width:62ch; line-height:1.5}

  /* code blocks */
  pre{font-family:var(--mono); font-size:13px; line-height:1.55; background:var(--surface); border:1px solid var(--rule);
    border-left:3px solid var(--accent); border-radius:7px; padding:12px 15px; overflow-x:auto; margin:12px 0; color:var(--ink)}
  pre code{background:none; border:none; padding:0; font-size:inherit; color:inherit}

  /* terminal (blocos com linguagem: bash/python) */
  pre.term{font-family:var(--mono); font-size:13px; line-height:1.55; background:var(--term-bg); color:var(--term-ink);
    padding:13px 15px; white-space:pre; margin:6px 0 14px; border:1px solid #000; border-radius:7px; overflow-x:auto;
    box-shadow:inset 0 0 0 1px rgba(255,255,255,.03)}
  pre.term code{color:inherit; background:none}

  /* tables */
  .tablewrap{overflow-x:auto; margin:14px 0}
  table{border-collapse:collapse; width:100%; font-size:13.5px}
  th,td{padding:7px 11px; text-align:left; border-bottom:1px solid var(--rule-soft); vertical-align:top}
  th{font-family:var(--sans); font-weight:600; font-size:11.5px; letter-spacing:.05em; text-transform:uppercase;
    color:var(--ink-faint); border-bottom:1px solid var(--rule)}
  td{font-variant-numeric:tabular-nums}
  td code{font-size:12px}
  tbody tr:hover td{background:var(--surface)}

  /* note (soft callout) */
  .note{background:var(--surface); border:1px solid var(--rule); border-left:3px solid var(--gas);
    padding:12px 15px; border-radius:7px; margin:14px 0; color:var(--ink-soft); font-size:14.5px}
  .note strong{color:var(--ink)}

  /* callouts (warn) */
  .callout{background:var(--warn-bg); border:1px solid var(--warn-rule); border-left:3px solid var(--crit);
    border-radius:7px; padding:12px 15px; margin:16px 0; font-size:14.5px}
  .callout .ct{font-family:var(--sans); font-size:10.5px; letter-spacing:.12em; text-transform:uppercase;
    color:var(--crit); margin:0 0 4px; font-weight:700; display:block}

  /* architecture block (blocos sem linguagem: árvores ASCII) */
  pre.arch{font-family:var(--mono); font-size:12.5px; background:var(--surface); border:1px solid var(--rule);
    border-radius:7px; padding:15px; overflow-x:auto; white-space:pre; line-height:1.5; margin:14px 0; color:var(--ink)}
  pre.arch code{color:inherit; background:none}

  /* blockquote vira note */
  blockquote{background:var(--surface); border:1px solid var(--rule); border-left:3px solid var(--bio);
    padding:12px 15px; border-radius:7px; margin:14px 0; color:var(--ink-soft); font-size:14.5px}
  blockquote p{margin:4px 0}

  /* imagens */
  img{max-width:100%; height:auto; border:1px solid var(--rule); border-radius:7px; margin:14px 0}
  figure{margin:14px 0}
  figcaption{font-size:12.5px; color:var(--ink-faint); margin-top:4px; text-align:center}

  /* footer */
  footer{margin-top:56px; padding-top:20px; border-top:1px solid var(--rule-soft); color:var(--ink-faint); font-size:12.5px}
  footer .by{font-family:var(--serif); color:var(--ink-soft); font-size:13.5px; margin:0 0 2px}

  @media (max-width:960px){
    .doc{padding:0 0 60px}
    h1.title{font-size:30px}
    .part h2{font-size:24px}
  }
"""

_SCRIPT = """
const links=[...document.querySelectorAll('.toc a')];
const secs=[...document.querySelectorAll('section[id]')];
const obs=new IntersectionObserver(es=>{
  es.forEach(e=>{ if(e.isIntersecting){
    const id=e.target.id; links.forEach(l=>l.classList.toggle('active',l.getAttribute('href')==='#'+id));
  }});
},{rootMargin:'-10% 0px -75% 0px'});
secs.forEach(s=>obs.observe(s));
"""


# --------------------------------- parsing --------------------------------- #
def _parse_front(text: str) -> tuple[str, str, str]:
    """Separa título (H1), lede (1º parágrafo) e corpo (a partir do 1º ``##``).

    O bloco de status (``> ...``) e o parágrafo-lede são consumidos pelo
    masthead; o restante do README vira o corpo do manual.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines) and not lines[i].startswith("# "):
        i += 1
    title = lines[i][2:].strip() if i < len(lines) else "BioGasSim"
    i += 1
    front: list[str] = []
    while i < len(lines) and not lines[i].startswith("## "):
        front.append(lines[i])
        i += 1
    body_md = "\n".join(lines[i:])
    # lede = 1º bloco de linhas não-vazias e não-citadas após o título
    lede_lines: list[str] = []
    j = 0
    while j < len(front) and (not front[j].strip() or front[j].lstrip().startswith(">")):
        j += 1
    while j < len(front) and front[j].strip() and not front[j].lstrip().startswith(">"):
        lede_lines.append(front[j].strip())
        j += 1
    lede = " ".join(lede_lines).strip()
    return title, lede, body_md


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return _html.unescape(s).strip()


def _classify_pre(html_body: str) -> str:
    """Blocos com linguagem (bash/python) viram terminal; sem linguagem viram arch."""
    html_body = re.sub(
        r'<pre><code class="language-[^"]*">',
        '<pre class="term"><code>',
        html_body,
    )
    html_body = re.sub(r'<pre><code>', '<pre class="arch"><code>', html_body)
    return html_body


def _rewrite_links(html_body: str) -> str:
    """Ajusta links/imagens relativos: HELP.html vive em docs/."""
    html_body = html_body.replace('src="docs/', 'src="').replace('href="docs/', 'href="')
    html_body = html_body.replace('href="LICENSE"', 'href="../LICENSE"')
    html_body = html_body.replace('href="README.md"', 'href="../README.md"')
    return html_body


def _sectionize(html_body: str) -> tuple[str, list[tuple[str, str, int]]]:
    """Envolve cada ``<h2>`` em ``<section id>`` com §N; devolve (html, lista p/ TOC)."""
    pat = re.compile(r'<h2 id="([^"]+)">(.*?)</h2>', re.S)
    parts = pat.split(html_body)
    out: list[str] = []
    toc: list[tuple[str, str, int]] = []
    n = 0
    i = 1
    while i < len(parts):
        sid, stext, sbody = parts[i], parts[i + 1], parts[i + 2]
        n += 1
        toc.append((sid, _strip_tags(stext), n))
        out.append(
            f'<section id="{sid}">\n<h2><span class="num">§{n}</span>{stext}</h2>\n'
            f'{sbody}\n</section>\n'
        )
        i += 3
    return "".join(out), toc


def _build_toc(html_body: str, h2_toc: list[tuple[str, str, int]]) -> str:
    """TOC aninhado: H2 (§N) com H3 filhos."""
    # agrupa H3 por H2 precedente (cada H3 pertence ao último H2 antes dele)
    cur_sid = None
    nest: dict[str, list[tuple[str, str]]] = {sid: [] for sid, _, _ in h2_toc}
    for m in re.finditer(r'<h(2|3) id="([^"]+)">(.*?)</h\1>', html_body, re.S):
        lvl, hid, htext = m.group(1), m.group(2), _strip_tags(m.group(3))
        if lvl == "2":
            cur_sid = hid
        elif lvl == "3" and cur_sid in nest:
            nest[cur_sid].append((hid, htext))
    items: list[str] = []
    for sid, text, n in h2_toc:
        children = nest[sid]
        if children:
            sub = "".join(
                f'<li><a href="#{cid}">{_html.escape(ctext)}</a></li>'
                for cid, ctext in children
            )
            items.append(
                f'<li><a href="#{sid}">§{n} · {_html.escape(text)}</a>'
                f'<ol>{sub}</ol></li>'
            )
        else:
            items.append(f'<li><a href="#{sid}">§{n} · {_html.escape(text)}</a></li>')
    return f'<nav class="toc">\n  <h4>Conteúdo</h4>\n  <ol>\n  {"".join(items)}\n  </ol>\n</nav>'


def render(readme_text: str) -> str:
    """Converte o texto do README em HTML do manual (string pronta p/ gravar)."""
    title, lede, body_md = _parse_front(readme_text)
    body_html = markdown.markdown(
        body_md, extensions=_MD_EXT, extension_configs=_MD_CFG, output_format="html5"
    )
    body_html = _classify_pre(body_html)
    body_html = _rewrite_links(body_html)
    sectioned, h2_toc = _sectionize(body_html)
    toc_html = _build_toc(body_html, h2_toc)

    lede_html = markdown.markdown(lede, extensions=["sane_lists"], output_format="html5")
    lede_html = re.sub(r"^<p>(.*)</p>$", r"\1", lede_html.strip(), flags=re.S)

    chips = "".join(
        f'<span class="chip {"ok" if cls else ""}">{_html.escape(lbl)}</span>'
        for cls, lbl in _CHIPS
    )

    title_esc = _html.escape(title)
    return (
        "<!doctype html>\n"
        '<html lang="pt-BR">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title_esc} — Manual de Ajuda</title>\n"
        '<style>\n' + _CSS + "\n</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="shell">\n'
        + toc_html
        + '\n<main class="doc">\n'
        '<header class="masthead">\n'
        '<p class="eyebrow">Manual de Ajuda · BioGasPy</p>\n'
        f'<h1 class="title">{title_esc} <span class="mf">·</span> Upgrading de Biogás</h1>\n'
        f'<p class="lede">{lede_html}</p>\n'
        f'<div class="chips">{chips}</div>\n'
        "</header>\n"
        '<hr class="duo-rule">\n'
        + sectioned
        + "\n"
        "<footer>\n"
        '<p class="by"><strong>BioGasPy — Thermodynamic Gas Upgrading Simulator</strong></p>\n'
        '<p>Prof. Dr. Ivaldo Leão Ferreira · Federal University of Pará — UFPA · '
        "Faculty of Mechanical Engineering</p>\n"
        "<p>FEM-ITEC-UFPA 2026 · Gerado a partir do <code>README.md</code> "
        "via <code>biogassim.Reporting.help_html</code>.</p>\n"
        "</footer>\n"
        "</main>\n"
        "</div>\n"
        "<script>" + _SCRIPT + "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def build_help_html(readme: pathlib.Path = README, out: pathlib.Path = OUT) -> pathlib.Path:
    """Lê o README, gera o HTML e grava ``out``; retorna o caminho gravado."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(readme.read_text(encoding="utf-8")), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Gera docs/HELP.html a partir do README.md")
    p.add_argument("--readme", type=pathlib.Path, default=README, help="caminho do README")
    p.add_argument("--out", type=pathlib.Path, default=OUT, help="caminho de saída")
    p.add_argument("--check", action="store_true", help="apenas valida a renderização, sem gravar")
    args = p.parse_args(argv)
    if args.check:
        render(args.readme.read_text(encoding="utf-8"))  # pode levantar se README sumir
        return 0
    path = build_help_html(args.readme, args.out)
    print(f"OK -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
