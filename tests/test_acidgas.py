"""Testes da absorção multi-gás (H2S/NH3/inertes) no water scrubbing."""
import pytest

from biogassim import batch, cases
from biogassim.Solvents import WaterSolvent


def _water(feed, op):
    return cases.run_case(cases.Case(technology="water", feed=feed, operating=op))["metrics"]


_HIGH_LV = {"P_bar": 20, "L_over_V": 60, "N_stages": 12, "height_m": 15}
_LOW_LV = {"P_bar": 10, "L_over_V": 20, "N_stages": 10, "height_m": 12}


def test_water_absorbs_h2s():
    m = _water({"CH4": 0.50, "CO2": 0.40, "H2S": 0.05, "N2": 0.05, "flow_mols": 100.0}, _HIGH_LV)
    assert m["converged"]
    assert m["H2S_removal"] > 95                      # H2S fortemente removido


def test_h2s_removed_more_than_co2():
    """H2S é ~3x mais solúvel que CO2 em água -> mais removido no mesmo ponto."""
    m = _water({"CH4": 0.50, "CO2": 0.40, "H2S": 0.05, "N2": 0.05, "flow_mols": 100.0}, _LOW_LV)
    assert m["H2S_removal"] > m["CO2_removal"]


def test_n2_mostly_passes_through():
    m = _water({"CH4": 0.55, "CO2": 0.40, "N2": 0.05, "flow_mols": 100.0}, _HIGH_LV)
    assert m["N2_removal"] < 10                       # inerte passa direto


def test_water_absorbs_nh3_strongly():
    m = _water({"CH4": 0.55, "CO2": 0.40, "NH3": 0.05, "flow_mols": 100.0}, _HIGH_LV)
    assert m["converged"]
    assert m["NH3_removal"] > 90                      # NH3 muito solúvel em água


def test_henry_h2s_more_soluble_than_co2():
    w = WaterSolvent()
    assert w.K_value("H2S", 298.15, 20e5, None) < w.K_value("CO2", 298.15, 20e5, None)


def test_inerts_barely_absorbed():
    w = WaterSolvent()
    k_n2 = w.K_value("N2", 298.15, 20e5, None)
    k_co2 = w.K_value("CO2", 298.15, 20e5, None)
    assert k_n2 > k_co2                               # N2 muito menos solúvel (K maior)


def test_case_validates_multispecies_feed():
    c = cases.Case(technology="water",
                   feed={"CH4": 50, "CO2": 40, "H2S": 5, "N2": 5, "flow_mols": 100})
    cases.validate_case(c)
    gas = {k: v for k, v in c.feed.items() if k != "flow_mols"}
    assert sum(gas.values()) == pytest.approx(1.0)
    assert c.feed["H2S"] == pytest.approx(0.05)


def test_batch_reports_h2s_removal():
    rows = batch.run_batch(
        [{"name": "acid", "CH4": 0.50, "CO2": 0.40, "H2S": 0.05, "N2": 0.05}],
        technology="water", P_bar=20.0)
    assert rows[0]["upg_H2S_removal"] not in (None, "")
    assert float(rows[0]["upg_H2S_removal"]) > 90


def test_binary_case_still_works():
    """Retrocompatibilidade: feed binário CH4/CO2 (condições padrão) continua ok."""
    m = cases.run_case(cases.Case(technology="water",
                                  feed={"CH4": 0.47, "CO2": 0.53, "flow_mols": 100.0}))["metrics"]
    assert m["converged"]
    assert m["purity_CH4"] > 95                       # L/V=100 padrão -> ~100%
    assert "H2S_removal" not in m                     # sem H2S no feed
