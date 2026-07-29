"""Testes da parametrização multicomponente de composição e da simulação em lote."""
import pytest

from biogassim import batch
from biogassim.Properties import (
    DEFAULT_GASES,
    mixture_properties_general,
    to_mole_fractions,
)

mpg = mixture_properties_general


# ---------------------------- propriedades --------------------------------- #
def test_default_gases_present():
    for g in ["CH4", "CO2", "N2", "O2", "H2", "H2O", "H2S", "NH3", "CO", "Ar"]:
        assert g in DEFAULT_GASES


def test_dry_air_matches_literature():
    a = mpg({"N2": 0.78, "O2": 0.21, "Ar": 0.01})
    assert a.molar_mass_gmol == pytest.approx(28.96, abs=0.15)   # ~28.96 g/mol
    assert a.Z == pytest.approx(1.0, abs=0.01)
    assert a.LHV_MJ_per_Nm3 == pytest.approx(0.0)                # inerte


def test_hydrogen_heating_value():
    h = mpg({"H2": 1.0})
    assert h.LHV_MJ_per_kg == pytest.approx(120.0, abs=2.0)      # ~120 MJ/kg
    assert h.molar_mass_gmol == pytest.approx(2.016, abs=0.01)


def test_multicomponent_fractions_normalized():
    m = mpg({"CH4": 0.72, "CO2": 0.25, "N2": 0.03})
    assert sum(m.fractions.values()) == pytest.approx(1.0)
    assert m.fractions["N2"] == pytest.approx(0.03)


def test_h2s_adds_to_heating_value():
    base = mpg({"CH4": 0.55, "CO2": 0.45}).LHV_MJ_per_Nm3
    with_h2s = mpg({"CH4": 0.55, "CO2": 0.40, "H2S": 0.05}).LHV_MJ_per_Nm3
    assert with_h2s > base                                       # H2S é combustível


# ----------------------------- conversões ---------------------------------- #
def test_mass_basis_gives_more_moles_of_lighter():
    x = to_mole_fractions({"CH4": 0.5, "CO2": 0.5}, "mass")
    assert x["CH4"] > x["CO2"]                                   # CH4 mais leve
    assert x["CH4"] == pytest.approx(0.7329, abs=1e-3)


def test_volume_basis_equals_mole_basis():
    xm = to_mole_fractions({"CH4": 0.6, "CO2": 0.4}, "mole")
    xv = to_mole_fractions({"CH4": 0.6, "CO2": 0.4}, "volume")
    assert xv == pytest.approx(xm)


def test_molar_flow_basis_normalizes():
    x = to_mole_fractions({"CH4": 72, "CO2": 25, "N2": 3}, "molar_flow")
    assert x["CH4"] == pytest.approx(0.72)


def test_invalid_species_and_values_rejected():
    with pytest.raises(KeyError):
        mpg({"CH4": 0.5, "XYZ": 0.5})
    with pytest.raises(ValueError):
        to_mole_fractions({"CH4": -0.1, "CO2": 0.5})
    with pytest.raises(ValueError):
        to_mole_fractions({"CH4": 0.0, "CO2": 0.0})


# -------------------------------- batch ------------------------------------ #
def test_run_batch_properties_uniform_keys():
    feeds = [{"name": "a", "CH4": 0.6, "CO2": 0.4},
             {"name": "b", "CH4": 0.5, "CO2": 0.45, "N2": 0.05}]
    rows = batch.run_batch(feeds)
    assert len(rows) == 2
    assert all(r["status"] == "ok" for r in rows)
    assert rows[0].keys() == rows[1].keys()                     # chaves uniformes
    assert rows[1]["x_N2"] == pytest.approx(0.05)


def test_run_batch_with_upgrading():
    rows = batch.run_batch([{"name": "c", "CH4": 0.6, "CO2": 0.4}],
                           technology="water", P_bar=20.0)
    assert rows[0]["upg_purity_CH4"] is not None
    assert rows[0]["upg_recovery_CH4"] > 80


def test_run_batch_reports_bad_rows_without_crashing():
    feeds = [{"name": "good", "CH4": 0.6, "CO2": 0.4},
             {"name": "bad", "CH4": 0.0, "CO2": 0.0}]
    rows = batch.run_batch(feeds)
    assert rows[0]["status"] == "ok"
    assert rows[1]["status"].startswith("erro")
    assert rows[0].keys() == rows[1].keys()                     # uniforme mesmo com erro


def test_run_batch_requires_species_columns():
    with pytest.raises(ValueError):
        batch.run_batch([{"name": "x", "foo": 1.0}])


def test_run_batch_from_csv(tmp_path):
    p = tmp_path / "feeds.csv"
    p.write_text("name,CH4,CO2\nf1,0.5,0.5\nf2,0.7,0.3\n", encoding="utf-8")
    rows = batch.run_batch(str(p))
    assert len(rows) == 2
    assert all(r["status"] == "ok" for r in rows)


# --------------------------------- CLI ------------------------------------- #
def test_cli_props_multigas(capsys):
    from biogassim.cli import main
    main(["props", "CH4=0.72", "CO2=0.25", "N2=0.03"])
    out = capsys.readouterr().out
    assert "x_N2" in out
    assert "Wobbe" in out


def test_cli_batch_exports(tmp_path, capsys):
    from biogassim.cli import main
    feeds = tmp_path / "feeds.csv"
    feeds.write_text("name,CH4,CO2,N2\na,0.6,0.4,0\nb,0.7,0.25,0.05\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    main(["batch", str(feeds), "--out", str(out)])
    assert out.exists()
    assert "avaliadas" in capsys.readouterr().out
