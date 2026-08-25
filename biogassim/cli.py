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
  biogassim sensitivity P_bar=5:30:5 --vary L_over_V=20:120:20 --plot surf.png
  biogassim optimize optimization.json --out best.json
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
    """Compara tecnologias via ComparisonEngine (mesmo backend da GUI).

      biogassim compare                       # métodos recomendados, biogás 47/53
      biogassim compare water mea psa membrane # só os métodos informados
      biogassim compare --case meu_projeto/case.json      # herda feed do caso
      biogassim compare --export comparison.xlsx           # exporta relatório
      biogassim compare --mode optimized --flow 200        # modo otimizado
    """
    import os

    from . import cases
    from .comparison import (
        METHODS,
        ComparisonConfig,
        ComparisonEngine,
        export_comparison,
        recommended_methods,
    )

    # feed: herda de --case se informado, senão biogás 47/53
    if args.case and os.path.exists(args.case):
        case = cases.load_case(args.case)
        feed = {k: v for k, v in case.feed.items() if k != "flow_mols"}
        flow = case.feed.get("flow_mols", 100.0)
    else:
        feed = {"CH4": 0.47, "CO2": 0.53}
        flow = 100.0
    if args.flow is not None:
        flow = args.flow

    # métodos: args.methods (alias curtos) ou recomendados
    aliases = {"water": "water", "mea": "mea", "dea": "dea", "mdea": "mdea",
               "selexol": "selexol", "rectisol": "rectisol", "psa": "psa",
               "membrane": "membrane", "membrane-multi": "membrane_multi",
               "multi": "membrane_multi"}
    if args.methods:
        selected = []
        for m in args.methods:
            key = aliases.get(m.lower(), m.lower())
            if key not in METHODS:
                raise SystemExit(f"Método desconhecido: '{m}'. Disponíveis: "
                                 f"{', '.join(METHODS)}.")
            selected.append(key)
    else:
        selected = recommended_methods()

    cfg = ComparisonConfig(selected=selected, mode=args.mode)
    eng = ComparisonEngine(feed, flow=flow, config=cfg)
    rows = eng.run()

    # tabela no terminal
    print("=" * 92)
    print(f"COMPARAÇÃO -- feed {', '.join(f'{k}={v*100:.1f}%' for k, v in feed.items())}"
          f"  flow={flow} mol/s  modo={args.mode}")
    print("=" * 92)
    hdr = (f"{'Método':<24}{'Conv':>5}{'Pureza%':>8}{'Recup%':>8}{'CO2r%':>7}"
           f"{'H2Sr%':>7}{'kW':>9}{'kWh/Nm³':>9}{'USD/Nm³':>9}")
    print(hdr)
    print("-" * 92)
    for r in rows:
        def f(v, w, d=2):
            return (f"{v:>{w}.{d}f}" if isinstance(v, (int, float)) and v is not None
                    else f"{'-':>{w}}")
        print(f"{str(r.get('method_label')):<24}{'S' if r.get('converged') else 'N':>5}"
              f"{f(r.get('purity_CH4'), 8)}{f(r.get('recovery_CH4'), 8)}"
              f"{f(r.get('CO2_removal'), 7)}{f(r.get('H2S_removal'), 7)}"
              f"{f(r.get('total_kW'), 9, 1)}{f(r.get('specific_kWh_per_Nm3'), 9, 3)}"
              f"{f(r.get('specific_cost_usd_per_Nm3'), 9, 4)}")
    print("-" * 92)
    ok = sum(1 for r in rows if r.get("converged"))
    print(f"{ok}/{len(rows)} métodos convergiram.")
    for crit in ("purity_CH4", "recovery_CH4", "total_kW", "specific_cost_usd_per_Nm3"):
        b = eng.best_by(rows, crit)
        if b:
            print(f"  Melhor por {crit}: {b['method_label']}")
    rank = eng.weighted_score(rows)
    if rank and rank[0].get("score") is not None:
        print(f"  Ranking ponderado (topo): {rank[0]['method_label']} "
              f"(score {rank[0]['score']})")
    if args.export:
        export_comparison(eng.report(rows), args.export)
        print(f"Exportado: {args.export}")


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


def _known_species():
    """Conjunto de espécies válidas para composição (banco de componentes)."""
    from .Properties.components import all_components
    return set(all_components())


def _apply_kv(case, kv):
    """Aplica pares CHAVE=VALOR ao caso.

    Espécies de gás (CH4, CO2, H2S, N2, ...) entram em ``case.feed``; chaves
    operacionais em ``case.operating``; ``flow``/``flow_mols`` na vazão; ``tech``
    na tecnologia. Para feed binário CH4/CO2 mantém a fração complementar
    automática; para feed multi-espécie a normalização é feita por
    ``cases.validate_case``.
    """
    species = _known_species()
    gas_keys = []
    for k, v in kv.items():
        if k in species:
            case.feed[k] = float(v)
            gas_keys.append(k)
        elif k in ("flow", "flow_mols"):
            case.feed["flow_mols"] = float(v)
        elif k in _OP_KEYS:
            case.operating[k] = int(v) if k == "N_stages" else float(v)
        elif k in ("tech", "technology"):
            case.technology = v.lower()
        else:
            raise SystemExit(f"Chave desconhecida: '{k}'. "
                             f"Espécies válidas: {sorted(species)}.")
    # fração complementar automática SOMENTE para feed binário CH4/CO2
    gas_set = {k for k in case.feed if k != "flow_mols"}
    if gas_set <= {"CH4", "CO2"}:
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
    from . import cases, dashboard, safety
    if args.max_h2s_ppm is not None:
        safety.set_max_h2s_treated_ppm(args.max_h2s_ppm)
    case = cases.load_case(args.case)
    out = cases.run_case(case, save=args.save,
                         outdir=args.outdir or os.path.dirname(args.case) or ".")
    m = out["metrics"]
    print(dashboard.format_dashboard(m))
    print(f"\nRUN -- {case.name} [{case.technology}]"
          f"  convergiu={m.get('converged')} iter={m.get('iterations', '-')}")


def _cmd_set(args):
    from . import cases
    case = cases.load_case(args.case) if os.path.exists(args.case) else cases.default_case()
    _apply_kv(case, _parse_assignments(args.assignments))
    cases.validate_case(case)
    cases.save_case(case, args.case)
    gas = {k: v for k, v in case.feed.items() if k != "flow_mols"}
    total = sum(gas.values())
    print(f"Caso salvo em '{args.case}'")
    print("  Composicao da alimentacao (normalizada para 100%):")
    for s, v in gas.items():
        print(f"    {s:<5} {v*100:7.3f} %")
    print(f"    {'TOTAL':<5} {total*100:7.3f} %"
          f"  {'[OK]' if abs(total - 1.0) < 1e-6 else '[AVISO: soma != 100%]'}")
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
    # roteia entre varredura de CH4 (composição) e varredura de H2S (contaminante)
    if "H2S" in kv and ":" in kv["H2S"]:
        a, b, step = (float(x) for x in kv["H2S"].split(":"))
        operating = None
        if args.case and os.path.exists(args.case):
            operating = cases.load_case(args.case).operating
        rows = cases.sweep_h2s(args.tech, cases.frange(a, b, step),
                               operating=operating, flow=args.flow)
        print("=" * 90)
        print(f"VARREDURA DE H2S -- {args.tech} (H2S {a*100:.1f}..{b*100:.1f} mol%)")
        print("=" * 90)
        hdr = (f"{'H2S%':>6}{'H2Srem%':>8}{'Pur%':>8}{'Rec%':>8}{'CO2r%':>8}"
               f"{'H2St_ppm':>9}{'kW':>8}{'kWh/Nm3':>9}{'Water':>8}")
        print(hdr)
        print("-" * 90)
        for r in rows:
            def f(v, w, dec=2):
                return f"{v:>{w}.{dec}f}" if isinstance(v, (int, float)) else f"{'-':>{w}}"
            print(f"{f(r['feed_H2S_pct'], 6, 2)}{f(r.get('H2S_removal'), 8)}"
                  f"{f(r['purity_CH4'], 8)}{f(r['recovery_CH4'], 8)}{f(r['CO2_removal'], 8)}"
                  f"{f(r.get('treated_H2S_ppm'), 9, 1)}{f(r['total_kW'], 8, 1)}"
                  f"{f(r['specific_kWh_per_Nm3'], 9, 3)}{f(r['water_m3_per_h'], 8, 1)}")
        print("-" * 90)
    elif "CH4" in kv and ":" in kv["CH4"]:
        a, b, step = (float(x) for x in kv["CH4"].split(":"))
        operating = None
        if args.case and os.path.exists(args.case):
            operating = cases.load_case(args.case).operating
        rows = cases.sweep_composition(args.tech, cases.frange(a, b, step),
                                       operating=operating, flow=args.flow)
        print("=" * 88)
        print(f"VARREDURA DE COMPOSICAO -- {args.tech} (CH4 {a:.0%}..{b:.0%})")
        print("=" * 88)
        hdr = (f"{'CH4%':>6}{'Pur%':>8}{'Rec%':>8}{'CO2r%':>8}{'kW':>9}{'kWh/Nm3':>9}"
               f"{'D(m)':>7}{'Flood%':>8}{'USD/Nm3':>10}")
        print(hdr)
        print("-" * 88)
        for r in rows:
            def f(v, w, dec=2):
                return f"{v:>{w}.{dec}f}" if isinstance(v, (int, float)) else f"{'-':>{w}}"
            print(f"{f(r['feed_CH4_pct'], 6, 1)}{f(r['purity_CH4'], 8)}{f(r['recovery_CH4'], 8)}"
                  f"{f(r['CO2_removal'], 8)}{f(r['total_kW'], 9, 1)}{f(r['specific_kWh_per_Nm3'], 9, 3)}"
                  f"{f(r['diameter_m'], 7)}{f(r['flooding_pct'], 8, 1)}"
                  f"{f(r.get('specific_cost_usd_per_Nm3'), 10, 4)}")
        print("-" * 88)
    else:
        raise SystemExit("Uso: biogassim sweep CH4=inicio:fim:passo | H2S=inicio:fim:passo "
                         "(ex.: CH4=0.20:0.95:0.05, H2S=0:0.05:0.005).")
    if args.out:
        if args.out.endswith(".json"):
            export_json({"sweep": rows}, args.out)
        else:
            export_csv(rows, args.out)
        print(f"Exportado: {args.out}")


def _parse_range(spec):
    """'L_over_V=40:120:20' -> ('L_over_V', (40.0, 120.0, 20.0))."""
    (name, rng), = _parse_assignments([spec]).items()
    parts = rng.split(":")
    if len(parts) != 3:
        raise SystemExit(f"Intervalo inválido '{spec}'. Use VAR=inicio:fim:passo.")
    a, b, step = (float(p) for p in parts)
    return name, (a, b, step)


def _cmd_sensitivity(args):
    from . import cases, studies
    from .Export import export_csv, export_json
    var_x, rx = _parse_range(args.spec)
    var_y = None
    if args.vary:
        var_y, ry = _parse_range(args.vary)
        rows = studies.sweep_2d(args.tech, var_x, cases.frange(*rx),
                                var_y, cases.frange(*ry), flow=args.flow)
    else:
        rows = studies.sweep_1d(args.tech, var_x, cases.frange(*rx), flow=args.flow)
    ok = sum(1 for r in rows if r.get("converged"))
    dims = f"{var_x}" + (f" × {var_y}" if var_y else "")
    print("=" * 72)
    print(f"SENSIBILIDADE -- {args.tech}: {dims}  ({ok}/{len(rows)} convergiram)")
    print("=" * 72)
    for r in rows[:24]:
        coord = f"{var_x}={r[var_x]}" + (f" {var_y}={r[var_y]}" if var_y else "")
        print(f"  {coord:<28} pureza={r.get('purity_CH4')!s:>7} "
              f"recup={r.get('recovery_CH4')!s:>7} kW={r.get('total_kW')!s:>8} "
              f"{args.metric}={r.get(args.metric)}")
    if len(rows) > 24:
        print(f"  ... (+{len(rows) - 24} pontos)")
    if args.out:
        if args.out.endswith(".json"):
            export_json({"sensitivity": rows}, args.out)
        else:
            export_csv(rows, args.out)
        print(f"Exportado: {args.out}")
    if args.plot:
        ok_plot = studies.plot_surface(rows, var_x, args.metric, args.plot, var_y=var_y)
        print(f"Gráfico: {args.plot}" if ok_plot else "matplotlib indisponível: sem gráfico.")


def _cmd_optimize(args):
    import json

    from . import studies
    from .Export import export_json
    with open(args.spec, encoding="utf-8") as f:
        cfg = json.load(f)
    res = studies.optimize(
        technology=cfg.get("technology", "water"),
        objective=cfg["objective"],
        variables={k: tuple(v) for k, v in cfg["variables"].items()},
        constraints={k: tuple(v) for k, v in cfg.get("constraints", {}).items()},
        goal=cfg.get("goal", "minimize"),
        flow=float(cfg.get("flow_mols", 100.0)))
    print("=" * 66)
    print(f"OTIMIZAÇÃO -- {res['n_feasible']}/{res['n_evaluated']} pontos viáveis")
    print("=" * 66)
    if res["best"] is None:
        print(res.get("message", "Nenhum ponto viável."))
    else:
        b = res["best"]
        print(f"  Objetivo : {b['objective']} = {b['value']}  ({b['goal']})")
        print(f"  Variáveis: {b['variables']}")
        m = b["metrics"]
        print(f"  Pureza CH4     : {m.get('purity_CH4')} %")
        print(f"  Recuperação CH4: {m.get('recovery_CH4')} %")
        print(f"  Energia total  : {m.get('total_kW')} kW")
        print(f"  Custo esp.     : {m.get('specific_cost_usd_per_Nm3')} USD/Nm³")
    if args.out:
        export_json(res, args.out)
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


def _cmd_help(args):
    """Gera (se ausente) e localiza o manual HTML; --open abre no navegador."""
    import pathlib

    from .Reporting.help_html import build_help_html

    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "docs" / "HELP.html"
    if not path.exists() or args.rebuild:
        path = build_help_html(out=path)
        print(f"Manual (re)gerado: {path}")
    else:
        print(f"Manual disponível: {path}")
    print("Abra no navegador ou rode: biogassim help --open")
    if args.open:
        import webbrowser
        webbrowser.open(path.as_uri())


def _cmd_report(args):
    from . import cases, dashboard, safety
    from .Export import export_html
    if args.max_h2s_ppm is not None:
        safety.set_max_h2s_treated_ppm(args.max_h2s_ppm)
    case = cases.load_case(args.case) if os.path.exists(args.case) else cases.default_case()
    m = cases.run_case(case)["metrics"]
    out = args.out or f"{case.name}_report.html"
    export_html([m], out, title=f"BioGasSim -- {case.name}")
    print(dashboard.format_dashboard(m))
    print(f"Relatorio HTML: {out}")


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

    pc = sub.add_parser("compare", help="Comparar tecnologias de upgrading")
    pc.add_argument("methods", nargs="*", default=[],
                    help="Métodos: water mea dea mdea selexol rectisol psa membrane membrane-multi")
    pc.add_argument("--case", default=None, help="Herdar feed (composição/vazão) de um caso JSON")
    pc.add_argument("--flow", type=float, default=None, help="Vazão do biogás (mol/s)")
    pc.add_argument("--mode", default="standard", choices=["standard", "optimized"],
                    help="Modo: standard (parâmetros padrão) ou optimized (otimiza antes)")
    pc.add_argument("--export", default=None,
                    help="Exportar relatório (.csv/.json/.html/.xlsx/.pdf)")
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
    pr.add_argument("--max-h2s-ppm", type=float, default=None,
                    help="Limite máximo admissível de H2S no gás tratado (ppmv)")
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

    psw = sub.add_parser("sweep",
                         help="Varredura de composição (CH4) ou de contaminante (H2S)")
    psw.add_argument("spec", help="CH4=inicio:fim:passo  ou  H2S=inicio:fim:passo")
    psw.add_argument("--tech", default="water", choices=["water", "mea"])
    psw.add_argument("--flow", type=float, default=100.0, help="Vazão do biogás (mol/s)")
    psw.add_argument("--case", default=None, help="Caso p/ herdar condições operacionais")
    psw.add_argument("--out", default=None, help="Exportar (.csv ou .json)")
    psw.set_defaults(func=_cmd_sweep)

    pse = sub.add_parser("sensitivity",
                         help="Estudo paramétrico / superfície de resposta (1-D ou 2-D)")
    pse.add_argument("spec", help="VAR=inicio:fim:passo (ex.: L_over_V=40:120:20)")
    pse.add_argument("--vary", default=None,
                     help="Segunda variável VAR=inicio:fim:passo (torna 2-D)")
    pse.add_argument("--tech", default="water", choices=["water", "mea"])
    pse.add_argument("--metric", default="recovery_CH4",
                     help="Métrica p/ o gráfico (ex.: recovery_CH4, specific_kWh_per_Nm3)")
    pse.add_argument("--flow", type=float, default=100.0, help="Vazão do biogás (mol/s)")
    pse.add_argument("--out", default=None, help="Exportar tabela (.csv ou .json)")
    pse.add_argument("--plot", default=None, help="Gráfico PNG (curva 1-D ou heatmap 2-D)")
    pse.set_defaults(func=_cmd_sensitivity)

    popt = sub.add_parser("optimize", help="Otimização (busca em grade) a partir de um JSON")
    popt.add_argument("spec", help="Arquivo JSON: objective/goal/variables/constraints")
    popt.add_argument("--out", default=None, help="Exportar resultado (.json)")
    popt.set_defaults(func=_cmd_optimize)

    pe = sub.add_parser("export", help="Executar um caso e exportar (.xlsx/.csv/.json)")
    pe.add_argument("output", help="Arquivo de saída (extensão define o formato)")
    pe.add_argument("--case", default="case.json", help="Arquivo do caso (JSON)")
    pe.set_defaults(func=_cmd_export)

    prep = sub.add_parser("report", help="Executar um caso e gerar relatório HTML")
    prep.add_argument("--case", default="case.json", help="Arquivo do caso (JSON)")
    prep.add_argument("--out", default=None, help="Arquivo HTML de saída")
    prep.add_argument("--max-h2s-ppm", type=float, default=None,
                      help="Limite máximo admissível de H2S no gás tratado (ppmv)")
    prep.set_defaults(func=_cmd_report)

    pg = sub.add_parser("gui", help="Abrir a interface gráfica (PySide6/PyQt5)")
    pg.set_defaults(func=_cmd_gui)
    ph = sub.add_parser("help", help="Gerar/localizar o manual HTML (docs/HELP.html)")
    ph.add_argument("--open", action="store_true", help="abrir no navegador padrão")
    ph.add_argument("--rebuild", action="store_true", help="regenerar a partir do README")
    ph.set_defaults(func=_cmd_help)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
