"""Testes dos estudos paramétricos multivariável e da otimização."""
import json

import pytest

from biogassim import cases, studies


# ------------------------------ varreduras --------------------------------- #
def test_sweep_1d_shape_and_recovery_trend():
    rows = studies.sweep_1d("water", "L_over_V", cases.frange(40, 120, 40))
    assert len(rows) == 3
    assert all(r["converged"] for r in rows)
    recs = [r["recovery_CH4"] for r in rows]
    assert recs == sorted(recs, reverse=True)          # recuperação cai com L/V


def test_sweep_1d_over_composition():
    # Com a regeneração Wellmann (reciclo do flash 1 -> feed), a recuperação
    # global fica robusta (~97-100%) em toda a faixa de composição: feeds
    # mais ricos em CO2 dissolvem mais CH4 em termos absolutos e devolvem
    # mais CH4 via reciclo -- a monotonia crescente do modelo once-through
    # (recuperação sobe com CH4) não vale mais para a planta completa.
    rows = studies.sweep_1d("water", "CH4", cases.frange(0.4, 0.8, 0.2))
    assert all(r["converged"] for r in rows)
    recs = [r["recovery_CH4"] for r in rows]
    assert all(95.0 <= r <= 100.0 for r in recs)
    # a pureza do biometano é alta (>= 95%) em toda a faixa de composição
    # (o lean sai limpo da dessorção com ar; pureza saturada em ~100%)
    pures = [r["purity_CH4"] for r in rows]
    assert all(p >= 95.0 for p in pures)


def test_sweep_2d_shape():
    rows = studies.sweep_2d("water", "P_bar", cases.frange(10, 20, 10),
                            "L_over_V", cases.frange(60, 120, 60))
    assert len(rows) == 2 * 2
    assert all("P_bar" in r and "L_over_V" in r for r in rows)


def test_unknown_variable_rejected():
    with pytest.raises(ValueError):
        studies.sweep_1d("water", "XYZ", [1, 2])


# ------------------------------ otimização --------------------------------- #
def test_optimize_respects_constraints_and_minimizes():
    res = studies.optimize(
        "water", "specific_kWh_per_Nm3",
        variables={"L_over_V": (40, 120, 40), "P_bar": (10, 25, 5)},
        constraints={"purity_CH4": (">=", 99.9), "recovery_CH4": (">=", 90)},
        goal="minimize")
    assert res["best"] is not None
    m = res["best"]["metrics"]
    assert m["purity_CH4"] >= 99.9 and m["recovery_CH4"] >= 90       # viável
    feasible = [r["specific_kWh_per_Nm3"] for r in res["rows"]
                if r.get("converged") and (r.get("purity_CH4") or 0) >= 99.9
                and (r.get("recovery_CH4") or 0) >= 90]
    assert res["best"]["value"] == pytest.approx(min(feasible))     # é o mínimo


def test_optimize_maximize_goal():
    res = studies.optimize("water", "recovery_CH4",
                           variables={"L_over_V": (40, 120, 40)}, goal="maximize")
    best = res["best"]["value"]
    assert best == pytest.approx(max(r["recovery_CH4"] for r in res["rows"]
                                     if r.get("converged")))


def test_optimize_infeasible_returns_none():
    res = studies.optimize("water", "total_kW",
                           variables={"L_over_V": (40, 60, 20)},
                           constraints={"purity_CH4": (">=", 200)})   # impossível
    assert res["best"] is None
    assert res["n_feasible"] == 0


# -------------------------------- gráficos --------------------------------- #
def test_plot_surface_1d_and_2d(tmp_path):
    r1 = studies.sweep_1d("water", "L_over_V", cases.frange(40, 80, 40))
    p1 = tmp_path / "s1.png"
    assert studies.plot_surface(r1, "L_over_V", "recovery_CH4", str(p1))
    assert p1.exists()
    r2 = studies.sweep_2d("water", "P_bar", cases.frange(10, 20, 10),
                          "L_over_V", cases.frange(60, 120, 60))
    p2 = tmp_path / "s2.png"
    assert studies.plot_surface(r2, "P_bar", "recovery_CH4", str(p2), var_y="L_over_V")
    assert p2.exists()


# ---------------------------------- CLI ------------------------------------ #
def test_cli_sensitivity_exports(tmp_path, capsys):
    from biogassim.cli import main
    out = tmp_path / "s.csv"
    main(["sensitivity", "L_over_V=40:120:40", "--tech", "water", "--out", str(out)])
    assert out.exists()
    assert "SENSIBILIDADE" in capsys.readouterr().out


def test_cli_optimize(tmp_path, capsys):
    from biogassim.cli import main
    spec = tmp_path / "opt.json"
    spec.write_text(json.dumps({
        "technology": "water", "objective": "specific_kWh_per_Nm3", "goal": "minimize",
        "variables": {"L_over_V": [40, 120, 40], "P_bar": [10, 25, 5]},
        "constraints": {"purity_CH4": [">=", 99.9], "recovery_CH4": [">=", 90]},
    }), encoding="utf-8")
    res = tmp_path / "r.json"
    main(["optimize", str(spec), "--out", str(res)])
    assert res.exists()
    assert "OTIMIZA" in capsys.readouterr().out
