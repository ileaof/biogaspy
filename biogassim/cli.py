"""Interface de linha de comando do BioGasSim.

Uso (tecnologias prontas):
  python -m biogassim.cli run-water | run-mea | run-psa | run-membrane
  python -m biogassim.cli run-membrane-multi | compare

Uso (casos, composição e lote):
  biogassim new meu_projeto --tech water
  biogassim set CH4=0.47 CO2=0.53 --case meu_projeto/case.json
  biogassim run meu_projeto/case.json
  biogassim props CH4=0.72 CO2=0.25 N2=0.03 --P 20   # mistura multicomponente
  biogassim props CH4=0.5 CO2=0.5 --basis mass       # base massica
  biogassim sweep CH4=0.20:0.95:0.05 --tech water --out sweep.csv
  biogassim batch feeds.csv --tech water --out results.csv
  biogassim export results.xlsx --case meu_projeto/case.json
  biogassim report --case meu_projeto/case.json
"""
from __future__ import annotations

import argparse
import os


def _print(m, title):
    print("=" * 60)
    print(title)
    print("=" * 60)
    for k, v in m.items():
        if isinstance(v, float):
            print(f"  {k:<28}: {v:.4f}")
        else:
            print(f"  {k:<28}: {v}")


def _cmd_run_water(args):
    from .Examples import WaterScrubbing
    m = WaterScrubbing.run_case(P_bar=args.P, L_over_V=args.LV, N_stages=args.N,
                                height=args.H, flow=args.flow)["metrics"]
    _print(m, "WATER SCRUBBING")


def _cmd_run_mea(args):
    from .Examples import MEA
    m = MEA.run_case(P_bar=args.P, L_over_V=args.LV, N_stages=args.N,
                     height=args.H, flow=args.flow)["metrics"]
    _print(m, "MEA (AMINA QUÍMICA)")


def _cmd_run_psa(args):
    from .Examples import PSA
    m = PSA.run_case(P_high_bar=args.P, adsorbent=args.adsorbent)["metrics"]
    _print(m, "PSA")


def _cmd_run_membrane(args):
    from .Examples import Membrane
    m = Membrane.run_case(material=args.material, P_feed_bar=args.P,
                          stage_cut=args.stage_cut)["metrics"]
    _print(m, "MEMBRANA (1 estágio)")


def _cmd_run_membrane_multi(args):
    from .Examples import MembraneMultiStage
    MembraneMultiStage.main()


def _cmd_compare(args):
    from .Examples import CompareAll
    CompareAll.main()


# --------------------------------------------------------------------------- #
# Milestone 1: gerência de casos, composição e estudos paramétricos CH4-CO2
# --------------------------------------------------------------------------- #
def _parse_assignments(pairs):
    """Converte ['CH4=0.47', 'CO2=0.53'] -> {'CH4':'0.47', 'CO2':'0.53'}."""
    kv = {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"Atribuição inválida '{p}'. Use CHAVE=VALOR.")
        k, v = p.split("=", 1)
        kv[k.strip()] = v.strip()
    return kv


_OP_KEYS = {"P_bar", "L_over_V", "N_stages", "height_m"}


def _apply_kv(case, kv):
    for k, v in kv.items():
        if k in ("CH4", "CO2"):
            case.feed[k] = float(v)
        elif k in ("flow", "flow_mols"):
            case.feed["flow_mols"] = float(v)
        elif k in _OP_KEYS:
            case.operating[k] = int(v) if k == "N_stages" else float(v)
        elif k in ("tech", "technology"):
            case.technology = v.lower()
        else:
            raise SystemExit(f"Chave desconhecida: '{k}'.")
    # fração complementar automática (editar CH4 atualiza CO2 e vice-versa)
    if "CH4" in kv and "CO2" not in kv:
        case.feed["CO2"] = 1.0 - float(kv["CH4"])
    elif "CO2" in kv and "CH4" not in kv:
        case.feed["CH4"] = 1.0 - float(kv["CO2"])
    return case


def _cmd_new(args):
    from . import cases
    case_path = cases.new_project(args.path, name=args.name, technology=args.tech)
    print(f"Projeto criado em '{args.path}'")
    print(f"  Caso padrão: {case_path}")
    print(f"  Resultados : {os.path.join(args.path, 'results')}/")


def _cmd_run(args):
    from . import cases
    case = cases.load_case(args.case)
    out = cases.run_case(case, save=args.save,
                         outdir=args.outdir or os.path.dirname(args.case) or ".")
    _print(out["metrics"], f"RUN -- {case.name} [{case.technology}]")


def _cmd_set(args):
    from . import cases
    case = cases.load_case(args.case) if os.path.exists(args.case) else cases.default_case()
    _apply_kv(case, _parse_assignments(args.assignments))
    cases.validate_case(case)
    cases.save_case(case, args.case)
    print(f"Caso salvo em '{args.case}'")
    print(f"  Composição : CH4={case.feed['CH4']:.4f}  CO2={case.feed['CO2']:.4f}"
          f"  (soma={case.feed['CH4'] + case.feed['CO2']:.4f})")
    print(f"  Tecnologia : {case.technology}")
    print(f"  Operacional: {case.operating}")


def _cmd_props(args):
    from .Properties import mixture_properties_general
    comp = {k: float(v) for k, v in _parse_assignments(args.assignments).items()}
    p = mixture_properties_general(comp, T=args.T, P=args.P * 1e5, basis=args.basis)
    out = {"basis": args.basis, "T_K": p.T, "P_bar": p.P / 1e5}
    for s, x in p.fractions.items():
        out[f"x_{s}"] = round(x, 4)
    out.update({
        "molar_mass_g_per_mol": round(p.molar_mass_gmol, 4),
        "Z": round(p.Z, 5),
        "density_kg_per_m3": round(p.density, 4),
        "density_kg_per_Nm3": round(p.density_normal, 4),
        "LHV_MJ_per_Nm3": round(p.LHV_MJ_per_Nm3, 3),
        "HHV_MJ_per_Nm3": round(p.HHV_MJ_per_Nm3, 3),
        "LHV_MJ_per_kg": round(p.LHV_MJ_per_kg, 3),
        "HHV_MJ_per_kg": round(p.HHV_MJ_per_kg, 3),
        "Wobbe_index_MJ_per_Nm3": round(p.wobbe_index_MJ_per_Nm3, 3),
        "specific_gravity": round(p.specific_gravity, 4),
    })
    _print(out, "PROPRIEDADES DA MISTURA")


def _cmd_batch(args):
    from .batch import run_batch
    from .Export import export_csv, export_json
    rows = run_batch(args.feeds, T=args.T, P_bar=args.P, basis=args.basis,
                     technology=args.tech, flow=args.flow)
    ok = sum(1 for r in rows if r.get("status") == "ok")
    print("=" * 70)
    print(f"BATCH -- {ok}/{len(rows)} composições avaliadas ({args.feeds})")
    print("=" * 70)
    for r in rows[:20]:
        print(f"  {str(r['name']):<16} MM={r.get('MM_g_per_mol', '-')!s:>8} g/mol "
              f"Z={r.get('Z', '-')!s:>7} LHV={r.get('LHV_MJ_per_Nm3', '-')!s:>7} MJ/Nm³ "
              f"Wobbe={r.get('wobbe_MJ_per_Nm3', '-')!s:>7} [{r.get('status')}]")
    if len(rows) > 20:
        print(f"  ... (+{len(rows) - 20} linhas)")
    if args.out:
        if args.out.endswith(".json"):
            export_json({"batch": rows}, args.out)
        else:
            export_csv(rows, args.out)
        print(f"Exportado: {args.out}")


def _cmd_sweep(args):
    from . import cases
    from .Export import export_csv, export_json
    kv = _parse_assignments([args.spec])
    if "CH4" not in kv or ":" not in kv["CH4"]:
        raise SystemExit("Uso: biogassim sweep CH4=inicio:fim:passo (ex.: CH4=0.20:0.95:0.05).")
    a, b, step = (float(x) for x in kv["CH4"].split(":"))
    operating = None
    if args.case and os.path.exists(args.case):
        operating = cases.load_case(args.case).operating
    rows = cases.sweep_composition(args.tech, cases.frange(a, b, step),
                                   operating=operating, flow=args.flow)
    print("=" * 78)
    print(f"VARREDURA DE COMPOSIÇÃO -- {args.tech} (CH4 {a:.0%}..{b:.0%})")
    print("=" * 78)
    hdr = f"{'CH4%':>6}{'Pur%':>8}{'Rec%':>8}{'CO2r%':>8}{'kW':>9}{'kWh/Nm3':>9}{'D(m)':>7}{'Flood%':>8}"
    print(hdr)
    print("-" * 78)
    for r in rows:
        def f(v, w, dec=2):
            return f"{v:>{w}.{dec}f}" if isinstance(v, (int, float)) else f"{'-':>{w}}"
        print(f"{f(r['feed_CH4_pct'], 6, 1)}{f(r['purity_CH4'], 8)}{f(r['recovery_CH4'], 8)}"
              f"{f(r['CO2_removal'], 8)}{f(r['total_kW'], 9, 1)}{f(r['specific_kWh_per_Nm3'], 9, 3)}"
              f"{f(r['diameter_m'], 7)}{f(r['flooding_pct'], 8, 1)}")
    print("-" * 78)
    if args.out:
        if args.out.endswith(".json"):
            export_json({"sweep": rows}, args.out)
        else:
            export_csv(rows, args.out)
        print(f"Exportado: {args.out}")


def _cmd_export(args):
    from . import cases
    from .Export import export_csv, export_json
    case = cases.load_case(args.case) if os.path.exists(args.case) else cases.default_case()
    m = cases.run_case(case)["metrics"]
    ext = os.path.splitext(args.output)[1].lower()
    if ext in (".xlsx", ".xls"):
        try:
            from .Export import export_excel
            export_excel({"results": [m]}, args.output)
        except ImportError:
            alt = os.path.splitext(args.output)[0] + ".csv"
            export_csv([m], alt)
            print(f"openpyxl ausente (instale o extra 'excel'); exportado CSV: {alt}")
            return
    elif ext == ".csv":
        export_csv([m], args.output)
    else:
        export_json(m, args.output)
    print(f"Exportado: {args.output}  (caso '{case.name}', {case.technology})")


def _cmd_gui(args):
    try:
        from .gui.app import main as gui_main
    except ImportError as exc:
        raise SystemExit(f"GUI indisponível: {exc}") from exc
    raise SystemExit(gui_main())


def _cmd_report(args):
    from . import cases
    from .Export import export_html
    case = cases.load_case(args.case) if os.path.exists(args.case) else cases.default_case()
    m = cases.run_case(case)["metrics"]
    out = args.out or f"{case.name}_report.html"
    export_html([m], out, title=f"BioGasSim -- {case.name}")
    _print(m, f"REPORT -- {case.name} [{case.technology}]")
    print(f"Relatório HTML: {out}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="biogassim", description="BioGasSim CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pw = sub.add_parser("run-water", help="Lavagem com água")
    pw.add_argument("--P", type=float, default=20.0, help="Pressão (bar)")
    pw.add_argument("--LV", type=float, default=100.0, help="Razão L/V (molar)")
    pw.add_argument("--N", type=int, default=12, help="Número de estágios")
    pw.add_argument("--H", type=float, default=15.0, help="Altura (m)")
    pw.add_argument("--flow", type=float, default=100.0, help="Vazão biogás (mol/s)")
    pw.set_defaults(func=_cmd_run_water)

    pm = sub.add_parser("run-mea", help="Lavagem com MEA")
    pm.add_argument("--P", type=float, default=2.0, help="Pressão (bar)")
    pm.add_argument("--LV", type=float, default=20.0, help="Razão L/V (molar)")
    pm.add_argument("--N", type=int, default=8, help="Número de estágios")
    pm.add_argument("--H", type=float, default=12.0, help="Altura (m)")
    pm.add_argument("--flow", type=float, default=100.0, help="Vazão biogás (mol/s)")
    pm.set_defaults(func=_cmd_run_mea)

    pp = sub.add_parser("run-psa", help="PSA (estimativa)")
    pp.add_argument("--P", type=float, default=7.0, help="Pressão alta (bar)")
    pp.add_argument("--adsorbent", default="Zeolite_13X",
                    choices=["Zeolite_13X", "ActivatedCarbon"])
    pp.set_defaults(func=_cmd_run_psa)

    pmem = sub.add_parser("run-membrane", help="Membrana (1 estágio)")
    pmem.add_argument("--P", type=float, default=10.0, help="Pressão alimentação (bar)")
    pmem.add_argument("--material", default="CelluloseAcetate",
                      choices=["CelluloseAcetate", "Polyimide", "Polysulfone", "Silica"])
    pmem.add_argument("--stage-cut", type=float, default=0.5)
    pmem.set_defaults(func=_cmd_run_membrane)

    pmm = sub.add_parser("run-membrane-multi",
                         help="Membrana multi-estágio (1 vs 2-estágios+reciclo vs série)")
    pmm.set_defaults(func=_cmd_run_membrane_multi)

    pc = sub.add_parser("compare", help="Comparar todas as tecnologias")
    pc.set_defaults(func=_cmd_compare)

    # --- Milestone 1: casos, composição e estudos paramétricos CH4-CO2 ----- #
    pn = sub.add_parser("new", help="Criar um projeto de simulação")
    pn.add_argument("path", help="Diretório do projeto a criar")
    pn.add_argument("--name", default=None, help="Nome do caso")
    pn.add_argument("--tech", default="water", choices=["water", "mea"])
    pn.set_defaults(func=_cmd_new)

    pr = sub.add_parser("run", help="Executar um caso (case.json)")
    pr.add_argument("case", help="Arquivo do caso (JSON)")
    pr.add_argument("--save", action="store_true", help="Salvar métricas em results/")
    pr.add_argument("--outdir", default=None, help="Diretório de saída")
    pr.set_defaults(func=_cmd_run)

    ps = sub.add_parser("set", help="Modificar composição/condições (ex.: CH4=0.47 CO2=0.53)")
    ps.add_argument("assignments", nargs="+", help="Pares CHAVE=VALOR")
    ps.add_argument("--case", default="case.json", help="Arquivo do caso (JSON)")
    ps.set_defaults(func=_cmd_set)

    pp = sub.add_parser("props", help="Propriedades de uma mistura (qualquer gás)")
    pp.add_argument("assignments", nargs="+",
                    help="Espécies=valor, ex.: CH4=0.72 CO2=0.25 N2=0.03")
    pp.add_argument("--T", type=float, default=298.15, help="Temperatura (K)")
    pp.add_argument("--P", type=float, default=1.01325, help="Pressão (bar)")
    pp.add_argument("--basis", default="mole",
                    help="Base: mole/mass/volume/molar_flow/mass_flow")
    pp.set_defaults(func=_cmd_props)

    pb = sub.add_parser("batch", help="Avaliar muitas composições de um CSV (feeds.csv)")
    pb.add_argument("feeds", help="CSV com colunas de espécies (CH4, CO2, N2, ...)")
    pb.add_argument("--out", default=None, help="Exportar resultados (.csv ou .json)")
    pb.add_argument("--tech", default=None, choices=["water", "mea"],
                    help="Rodar upgrading sobre a subcomposição CH4/CO2")
    pb.add_argument("--T", type=float, default=298.15, help="Temperatura (K)")
    pb.add_argument("--P", type=float, default=1.01325, help="Pressão (bar)")
    pb.add_argument("--basis", default="mole",
                    help="Base: mole/mass/volume/molar_flow/mass_flow")
    pb.add_argument("--flow", type=float, default=100.0, help="Vazão p/ upgrading (mol/s)")
    pb.set_defaults(func=_cmd_batch)

    psw = sub.add_parser("sweep", help="Varredura de composição (ex.: CH4=0.20:0.95:0.05)")
    psw.add_argument("spec", help="CH4=inicio:fim:passo")
    psw.add_argument("--tech", default="water", choices=["water", "mea"])
    psw.add_argument("--flow", type=float, default=100.0, help="Vazão do biogás (mol/s)")
    psw.add_argument("--case", default=None, help="Caso p/ herdar condições operacionais")
    psw.add_argument("--out", default=None, help="Exportar (.csv ou .json)")
    psw.set_defaults(func=_cmd_sweep)

    pe = sub.add_parser("export", help="Executar um caso e exportar (.xlsx/.csv/.json)")
    pe.add_argument("output", help="Arquivo de saída (extensão define o formato)")
    pe.add_argument("--case", default="case.json", help="Arquivo do caso (JSON)")
    pe.set_defaults(func=_cmd_export)

    prep = sub.add_parser("report", help="Executar um caso e gerar relatório HTML")
    prep.add_argument("--case", default="case.json", help="Arquivo do caso (JSON)")
    prep.add_argument("--out", default=None, help="Arquivo HTML de saída")
    prep.set_defaults(func=_cmd_report)

    pg = sub.add_parser("gui", help="Abrir a interface gráfica (PySide6/PyQt5)")
    pg.set_defaults(func=_cmd_gui)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
