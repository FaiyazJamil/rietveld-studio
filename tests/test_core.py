from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from rietveld_studio.analysis import associate_peaks, correlation_diagnostics, json_safe, profile_statistics
from rietveld_studio.chemistry import composition_distance, hill_formula, parse_formula
from rietveld_studio.models import InstrumentConfig, PhaseSpec, ProjectConfig, RecipeConfig
from rietveld_studio.powder import load_powder
from rietveld_studio.structures import inspect_cif, phase_from_cif, preview_reflections, select_block


@pytest.mark.parametrize("formula,expected", [
    ("LiFePO4", {"Li": 1, "Fe": 1, "P": 1, "O": 4}),
    ("LiMn0.6Fe0.4PO4", {"Li": 1, "Mn": .6, "Fe": .4, "P": 1, "O": 4}),
    ("LiFePO₄", {"Li": 1, "Fe": 1, "P": 1, "O": 4}),
    ("Fe2(SO4)3", {"Fe": 2, "S": 3, "O": 12}),
    ("CuSO4·5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}),
    ("LMFP", {"Li": 1, "Mn": .6, "Fe": .4, "P": 1, "O": 4}),
])
def test_formula_stoichiometry(formula, expected):
    assert parse_formula(formula) == pytest.approx(expected)


@pytest.mark.parametrize("formula", ["", "XxO2", "Li(PO4", "Li1-xFePO4", "Li0FePO4", "FePO4)"])
def test_formula_rejects_ambiguous_or_invalid(formula):
    with pytest.raises(ValueError):
        parse_formula(formula)


def test_formula_comparison_is_scale_invariant():
    a = parse_formula("LiFePO4")
    b = parse_formula("Li4Fe4P4O16")
    assert composition_distance(a, b) == pytest.approx(0)
    assert composition_distance(a, parse_formula("Li3Fe2P3O12")) > 0
    assert hill_formula(parse_formula("H2CO3")) == "C H2 O3"
    assert hill_formula(a) == "Fe Li O4 P"


@pytest.fixture
def ascii_pattern(tmp_path):
    path = tmp_path / "pattern.csv"
    x = np.linspace(10, 90, 301)
    y = 100 + 500 * np.exp(-((x - 35) / .5)**2)
    sigma = np.sqrt(y)
    np.savetxt(path, np.column_stack([x, y, sigma]), delimiter=",", header="2theta,I,sigma", comments="")
    return path, x, y, sigma


def test_powder_supplied_sigma_preserved(ascii_pattern):
    path, x, y, sigma = ascii_pattern
    pattern = load_powder(path, uncertainty="column", sigma_col=2)
    assert np.array_equal(pattern.x, x)
    assert np.allclose(pattern.y, y)
    assert np.allclose(pattern.sigma, sigma)
    mask = pattern.fit_mask(20, 80, [(30, 40)])
    assert not mask[(x >= 30) & (x <= 40)].any()
    assert mask.sum() == np.sum((x >= 20) & (x <= 80) & ~((x >= 30) & (x <= 40)))


def test_malformed_rows_after_data_are_not_silently_removed(ascii_pattern):
    path, *_ = ascii_pattern
    with path.open("a") as output:
        output.write("malformed row\n")
    with pytest.raises(ValueError, match="Invalid numeric row"):
        load_powder(path)


def test_zero_sigma_and_duplicate_positions_rejected(ascii_pattern, tmp_path):
    _, x, y, sigma = ascii_pattern
    path = tmp_path / "bad.xye"
    sigma[10] = 0
    np.savetxt(path, np.column_stack([x, y, sigma]))
    with pytest.raises(ValueError, match="must be positive"):
        load_powder(path, uncertainty="column", sigma_col=2)
    sigma[10] = 1
    x[5] = x[4]
    np.savetxt(path, np.column_stack([x, y, sigma]))
    with pytest.raises(ValueError, match="duplicate"):
        load_powder(path, uncertainty="column", sigma_col=2)


def test_negative_intensity_needs_explicit_weights(tmp_path):
    path = tmp_path / "negative.xy"
    np.savetxt(path, np.column_stack([np.linspace(10, 90, 100), np.linspace(-4, 10, 100)]))
    with pytest.raises(ValueError, match="Negative intensities"):
        load_powder(path)
    data = load_powder(path, uncertainty="constant", constant_sigma=2)
    assert np.all(data.sigma == 2)
    assert "descriptive" in data.weighting


def test_xrdml_cps_counting_uncertainty(tmp_path):
    path = tmp_path / "scan.xrdml"
    path.write_text('''<xrdMeasurements xmlns="urn:example"><xrdMeasurement><scan><dataPoints>
      <positions axis="2Theta"><startPosition>10</startPosition><endPosition>80</endPosition></positions>
      <commonCountingTime>4</commonCountingTime><intensities unit="cps">''' + " ".join(["100"] * 100) +
      "</intensities></dataPoints></scan></xrdMeasurement></xrdMeasurements>")
    data = load_powder(path)
    assert np.all(data.y == 100)
    assert np.all(data.sigma == 5)  # sqrt(100 CPS * 4 s)/4 s
    assert len(data.x) == 100


def test_statistics_definitions_and_exclusions():
    obs = np.array([100., 200., 9999., 300., 400.])
    calc = np.array([101., 198., -9999., 302., 398.])
    weights = np.ones(5) / 4
    mask = np.array([True, True, False, True, True])
    stats = profile_statistics(obs, calc, weights, mask, 1)
    assert stats["n_observations"] == 4
    assert stats["weighted_SSE"] == pytest.approx(13 / 4)
    assert stats["chi2_reduced"] == pytest.approx((stats["Rwp_percent"] / stats["Rexp_percent"])**2)
    assert stats["goodness_of_fit"]**2 == pytest.approx(stats["chi2_reduced"])
    assert stats["Rp_percent"] == pytest.approx(.7)


def test_correlation_diagnostics():
    rows, matrix = correlation_diagnostics([[4, 5.7], [5.7, 9]], ["a", "b"])
    assert rows[0]["correlation"] == pytest.approx(.95)
    assert np.diag(matrix).tolist() == [1., 1.]
    rows, _ = correlation_diagnostics([[0, 0], [0, 1]], ["fixed", "variable"])
    assert rows == []


def test_peak_overlaps_remain_ambiguous_and_unknowns_stay_unknown():
    x = np.linspace(10, 80, 7001)
    y = sum(100 * np.exp(-((x - p) / .04)**2) for p in [20, 40, 60])
    refs = [{"phase": "A", "h": 1, "k": 0, "l": 0, "two_theta": 20.01, "Icalc": 10},
            {"phase": "B", "h": 1, "k": 1, "l": 0, "two_theta": 19.99, "Icalc": 10},
            {"phase": "A", "h": 2, "k": 0, "l": 0, "two_theta": 40.02, "Icalc": 20}]
    matches = associate_peaks(x, y, np.zeros_like(x), np.ones_like(x, dtype=bool), refs)
    assert [r["status"] for r in matches] == ["ambiguous/overlap", "associated", "unassigned"]
    assert matches[-1]["assignments"] == ""


def test_calibrated_size_requires_fixed_instrument_profile():
    recipe = RecipeConfig(profile_mode="sample", refine_size=True)
    with pytest.raises(ValueError, match="calibrated"):
        recipe.validate(InstrumentConfig())
    recipe.validate(InstrumentConfig(calibrated=True))
    recipe.profile_mode = "instrument"
    with pytest.raises(ValueError, match="sample-profile"):
        recipe.validate(InstrumentConfig(calibrated=True))
    with pytest.raises(ValueError, match="Bragg-Brentano"):
        RecipeConfig(position_correction="displacement").validate(InstrumentConfig(geometry="Debye-Scherrer"))


def test_portable_project_resolves_relative_inputs(tmp_path):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    cif = input_dir / "phase.cif"
    cif.write_text("example")
    pattern = input_dir / "pattern.xy"
    pattern.write_text("example")
    project = ProjectConfig(powder_path=str(pattern), phases=[PhaseSpec("phase", str(cif))], output_dir=str(tmp_path / "result"))
    destination = tmp_path / "project.rsv.json"
    project.save(destination)
    raw = json.loads(destination.read_text())
    assert raw["phases"][0]["cif_path"] == str(Path("inputs") / "phase.cif")
    loaded = ProjectConfig.load(destination)
    assert loaded.phases[0].cif_path == str(cif.resolve())
    assert loaded.powder_path == str(pattern.resolve())


def test_cif_inspection_and_systematic_absences(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples" / "NaCl_start.cif"
    records = inspect_cif(source)
    assert records[0]["space_group"] == "F m -3 m"
    assert len(records[0]["sites"]) == 2
    selected = select_block(source, records[0]["block_name"], tmp_path / "selected.cif")
    phase = phase_from_cif(selected, inspect_cif(selected)[0])
    reflections = preview_reflections(phase, 1.540593)
    assert reflections
    for r in reflections:
        parity = {abs(r[k]) % 2 for k in ("h", "k", "l")}
        assert len(parity) == 1  # F-centering: all odd or all even.
    assert any((r["h"], r["k"], r["l"]) == (1, 1, 1) for r in reflections)


def test_json_contains_no_nonstandard_numbers():
    value = json_safe({"a": np.float64(np.nan), "b": np.array([np.inf, 1]), "c": np.bool_(True)})
    encoded = json.dumps(value, allow_nan=False)
    assert "NaN" not in encoded and "Infinity" not in encoded

