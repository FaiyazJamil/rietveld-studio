from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from rietveld_studio.analysis import profile_statistics
from rietveld_studio.diagnostics import diagnose_fit
from rietveld_studio.initialization import background_strategy, rank_alignment_starts
from rietveld_studio.models import InstrumentConfig, ProjectConfig, RecipeConfig
from rietveld_studio.optimization import max_shift_su, stability

ROOT = Path(__file__).resolve().parents[1]
GSAS_PATH = os.environ.get("GSASII_PATH", "")


def test_bounded_alignment_recovers_cell_scale_and_allowed_zero():
    x = np.linspace(10, 110, 6000)
    d = np.array([3.0, 2.5, 2.1, 1.8, 1.5, 1.3])
    intensities = np.array([100, 60, 80, 30, 40, 50])
    wavelength, scale, offset = 1.540593, .986, .10
    positions = 2 * np.degrees(np.arcsin(wavelength / (2 * d * scale))) + offset
    y = sum(a * np.exp(-.5 * ((x - p) / .045)**2) for a, p in zip(intensities, positions))
    best = rank_alignment_starts(x, y, np.ones_like(x, dtype=bool), d, intensities, wavelength, allow_zero=True)[0]
    assert best["cell_scale"] == pytest.approx(scale, abs=.001)
    assert best["zero_offset_deg"] == pytest.approx(offset, abs=.03)
    fixed_zero = rank_alignment_starts(x, y, np.ones_like(x, dtype=bool), d, intensities, wavelength, allow_zero=False)
    assert all(row["zero_offset_deg"] == 0 for row in fixed_zero)
    assert all(.98 <= row["cell_scale"] <= 1.02 for row in fixed_zero)


@pytest.mark.parametrize("mode,terms", [("auto", 3), ("subtracted", 3), ("raw", 8)])
def test_processed_background_is_explicit_and_low_order(mode, terms):
    project = ProjectConfig(powder_path="3 Ca Doped_bg_subtracted.xy", recipe=RecipeConfig(background_terms=8, background_mode=mode))
    assert background_strategy(project)["effective_terms"] == terms


def test_unit_sigma_does_not_make_goodness_of_fit_a_quality_certificate():
    observed = np.linspace(1, 20, 100)
    calculated = observed + .5
    mask = np.ones(100, dtype=bool)
    first = profile_statistics(observed, calculated, np.ones(100), mask, 4)
    scaled = profile_statistics(observed * 10, calculated * 10, np.ones(100), mask, 4)
    assert first["Rwp_percent"] == pytest.approx(scaled["Rwp_percent"])
    assert first["Rp_percent"] == pytest.approx(scaled["Rp_percent"])
    assert scaled["chi2_reduced"] == pytest.approx(first["chi2_reduced"] * 100)
    assert scaled["Rexp_percent"] == pytest.approx(first["Rexp_percent"] / 10)


def test_convergence_requires_small_parameter_shifts_not_only_flat_rwp():
    recipe = RecipeConfig()
    cov = {"varyList": ["a"], "sig": [1.], "Rvals": {"lastShifts": {"a": 2.}}}
    assert max_shift_su(cov) == 2
    assert not stability(10., 10.00001, cov, recipe)[0]
    cov["Rvals"]["lastShifts"]["a"] = .02
    assert stability(10., 10.00001, cov, recipe)[0]
    assert not stability(10., 9.5, cov, recipe)[0]
    assert not stability(10., 10., {"varyList": [], "sig": []}, recipe)[0]


@pytest.mark.parametrize("changes", [{"max_passes": 0}, {"start_trials": 10}, {"cell_search_percent": 6},
                                     {"shift_su_tolerance": 0}, {"background_mode": "invented"}])
def test_invalid_optimizer_controls_rejected(changes):
    with pytest.raises(ValueError):
        RecipeConfig(**changes).validate(InstrumentConfig())


def test_descriptive_diagnostics_keep_negative_observations():
    x = np.linspace(10, 90, 1000)
    y = 20 * np.exp(-((x - 40) / .12)**2) + .2 * np.sin(np.arange(1000))
    calc = 20 * np.exp(-((x - 40) / .12)**2)
    mask = np.ones(1000, dtype=bool)
    stats = profile_statistics(y, calc, np.ones(1000), mask, 4)
    stats["statistical_interpretation"] = "descriptive_only"
    profile = dict(x=x, yobs=y.copy(), ycalc=calc, background=np.zeros(1000), weights=np.ones(1000), mask=mask)
    result = diagnose_fit(profile, [], stats, "constant sigma=1; descriptive")
    assert result["negative_observations"] > 0
    assert "chosen sigma" in " ".join(result["messages"])
    assert np.array_equal(profile["yobs"], y)
    assert result["baseline_noise_MAD_input_units"] > 0


def _example(tmp_path):
    spec = importlib.util.spec_from_file_location("generate_iterative_demo", ROOT / "scripts/generate_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return ProjectConfig.load(module.generate(tmp_path / "simulation", GSAS_PATH))


def _run(project, path):
    project.save(path)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    process = subprocess.run([sys.executable, "-m", "rietveld_studio.engine", str(path)],
        capture_output=True, text=True, env=env, timeout=180)
    assert process.returncode == 0, process.stdout[-6000:] + process.stderr[-1500:]
    return json.loads((Path(project.output_dir) / "result.json").read_text())


@pytest.mark.integration
@pytest.mark.skipif(not GSAS_PATH, reason="GSASII_PATH required")
def test_independent_starts_recover_a_distant_narrow_profile(tmp_path):
    project = _example(tmp_path)
    source = Path(project.phases[0].cif_path)
    source.write_text(source.read_text().replace("5.6500", "5.7200"))
    project.recipe.start_trials = 3
    project.output_dir = str(tmp_path / "iterative")
    result = _run(project, tmp_path / "iterative.json")
    assert result["phases"][0]["cell"]["length_a"] == pytest.approx(5.6402, abs=.001)
    assert result["statistics"]["Rwp_percent"] < 13
    assert len(result["trial_history"]) >= 2
    assert any(r["selected"] for r in result["trial_history"])
    original = result["trial_history"][0]
    if original["success"]:
        assert result["statistics"]["Rwp_percent"] <= original["Rwp_percent"] + 1e-5
    assert len(result["iteration_history"]) > len(result["stage_history"])
    for name in ["iteration_history.csv", "trial_history.csv", "convergence.svg", "fit_diagnostics.csv", "refined_instrument.instprm"]:
        assert (Path(project.output_dir) / name).is_file()


@pytest.mark.integration
@pytest.mark.skipif(not GSAS_PATH, reason="GSASII_PATH required")
def test_processed_data_and_continuation_preserve_weights(tmp_path):
    project = _example(tmp_path)
    raw = np.loadtxt(project.powder_path)
    x = raw[:, 0]
    # Known smooth background used by the synthetic generator, plus finite counting noise.
    y = (raw[:, 1] - 90) * .01
    path = tmp_path / "SYNTHETIC_bg_subtracted.xy"
    np.savetxt(path, np.column_stack([x, y]), header="'Synthetic comment metadata")
    project.powder_path = str(path)
    project.powder_options = {"uncertainty": "constant", "constant_sigma": .1}
    project.recipe.start_trials = 1
    project.output_dir = str(tmp_path / "processed")
    result = _run(project, tmp_path / "processed.json")
    assert result["statistics"]["statistical_interpretation"] == "descriptive_only"
    assert result["convergence"]["background_strategy"]["effective_mode"] == "subtracted"
    assert result["background_actual"][0][2] <= 3
    with np.load(Path(project.output_dir) / "profile.npz") as arrays:
        assert np.allclose(arrays["yobs"], y)
        assert np.allclose(arrays["weights"], 100.)
    from rietveld_studio.continuation import continuation_project
    continued = continuation_project(project.output_dir)
    assert continued.powder_options["uncertainty"] == "constant"
    assert continued.powder_options["constant_sigma"] == .1
    assert continued.recipe.background_mode == "subtracted"
    assert Path(continued.instrument.instrument_file).name == "refined_instrument.instprm"
    assert continued.continued_from == project.output_dir
    continued.output_dir = str(tmp_path / "continued")
    again = _run(continued, tmp_path / "continued.json")
    assert again["statistics"]["Rwp_percent"] <= result["statistics"]["Rwp_percent"] * 1.02
    assert again["statistics"]["statistical_interpretation"] == "descriptive_only"

