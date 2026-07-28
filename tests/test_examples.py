"""Smoke tests dos exemplos e unidades auxiliares."""
import numpy as np
import pytest

from biogassim.Examples import WaterScrubbing, MEA, PSA, Membrane, CompareAll
from biogassim.UnitOperations.Compressor import compress
from biogassim.UnitOperations.base import Stream


def test_water_example_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = WaterScrubbing.run_case(save=True)["metrics"]
    assert m["converged"]
    assert m["purity_CH4"] > 90
    assert (tmp_path / "examples_output" / "water_results.json").exists()


def test_mea_example_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = MEA.run_case(save=True)["metrics"]
    assert m["converged"]
    assert m["purity_CH4"] > 95
    assert m["rich_loading"] > 0.05


def test_psa_example_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = PSA.run_case(save=False)["metrics"]
    assert "purity_CH4" in m
    assert m["purity_CH4"] > 0


def test_membrane_example_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = Membrane.run_case(save=False)["metrics"]
    assert m["purity_CH4"] > 0
    assert 0 <= m["recovery_CH4"] <= 100


def test_compare_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rows = CompareAll.run_all(save=True)
    techs = {r["technology"] for r in rows}
    assert any("Water" in t for t in techs)
    assert any("MEA" in t for t in techs)
    assert (tmp_path / "examples_output" / "comparison.csv").exists()
    assert (tmp_path / "examples_output" / "comparison.json").exists()


def test_compressor():
    s = Stream.make(["CH4", "CO2"], [0.5, 0.5], 100.0, 298.15, 1e5, "vapor")
    r = compress(s, 10e5, eta=0.75)
    assert r.out.P == pytest.approx(10e5)
    assert r.out.T > s.T           # compressão aquece
    assert r.work > 0