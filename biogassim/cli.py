"""Interface de linha de comando do BioGasSim.

Uso:
  python -m biogassim.cli run-water
  python -m biogassim.cli run-mea
  python -m biogassim.cli run-psa
  python -m biogassim.cli run-membrane
  python -m biogassim.cli run-membrane-multi
  python -m biogassim.cli compare
"""
from __future__ import annotations

import argparse


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
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
