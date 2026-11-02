from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
GSAS_PATH = os.environ.get("GSASII_PATH", "")


@pytest.mark.integration
@pytest.mark.skipif(not GSAS_PATH, reason="Set GSASII_PATH to run the real GSAS-II recovery test")
def test_real_engine_recovers_known_lattice_and_exports(tmp_path):
    spec = importlib.util.spec_from_file_location("generate_demo", ROOT / "scripts" / "generate_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project = module.generate(tmp_path / "simulation", GSAS_PATH)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    process = subprocess.run([sys.executable, "-m", "rietveld_studio.engine", str(project)],
        capture_output=True, text=True, env=environment, timeout=180)
    assert process.returncode == 0, process.stdout[-6000:] + process.stderr[-2000:]
    assert '"kind": "complete"' in process.stdout
    folder = project.parent / "refined_run"
    result = json.loads((folder / "result.json").read_text())
    a = result["phases"][0]["cell"]["length_a"]
    su = result["phases"][0]["cell_su"]["length_a"]
    assert a == pytest.approx(5.6402, abs=5e-4)
    assert su > 0
    assert abs(a - 5.6402) < 5 * su
    stats = result["statistics"]
    assert .8 < stats["chi2_reduced"] < 1.2
    assert stats["Rwp_percent"] == pytest.approx(result["engine_histogram_residuals"]["wR"], rel=1e-6)
    assert len(result["reflections"]) >= 10
    assert any(stage["stage"] == "cell" and stage["accepted"] for stage in result["stage_history"])
    for name in ["engine.log", "refinement.gpx", "report.html", "refinement.png", "refinement.svg", "refinement.pdf",
                 "refinement_tables.xlsx", "reflections.csv", "export_to_origin.py", "refined_Na_Cl.cif", "project.rsv.json"]:
        assert (folder / name).stat().st_size > 0
    assert not (folder / "refinement.opju").exists()  # No fake native file is manufactured.
    with np.load(folder / "covariance.npz", allow_pickle=False) as data:
        assert data["covariance"].shape == (stats["n_parameters"],) * 2
    from rietveld_studio.models import ProjectConfig
    archived = ProjectConfig.load(folder / "project.rsv.json")
    assert Path(archived.phases[0].cif_path).is_file()
    assert archived.powder_options["sigma_col"] == 2


def _simulate_scenario(tmp_path, *, doublet=False, second_phase=False, sample_broadening=False):
    from rietveld_studio.engine import load_gsas, write_instrument
    from rietveld_studio.models import InstrumentConfig, ProjectConfig, RecipeConfig
    from rietveld_studio.structures import inspect_cif, phase_from_cif
    g2 = load_gsas(GSAS_PATH)
    instrument = InstrumentConfig(u=3., v=-1., w=7., x=.5, y=.5,
        wavelength2=1.544427 if doublet else None,
        geometry="Bragg-Brentano" if doublet else "Debye-Scherrer", calibrated=True)
    instfile = tmp_path / "instrument.instprm"
    write_instrument(instrument, instfile)
    gpx = g2.G2Project(newgpx=str(tmp_path / "truth.gpx"))
    hist = gpx.add_simulated_powder_histogram("SYNTHETIC scenario", str(instfile), 15, 110,
                                            Tstep=.025, scale=5000 if sample_broadening else 100)
    source = ROOT / "examples" / "NaCl_start.cif"
    nacl = tmp_path / "NaCl.cif"
    nacl.write_text(source.read_text())
    phase1 = gpx.add_phase(str(nacl), phasename="NaCl", histograms=[hist])
    specs = [phase_from_cif(nacl, inspect_cif(nacl)[0])]
    specs[0].name = "NaCl"
    truth_fraction = None
    if second_phase:
        kcl = tmp_path / "KCl.cif"
        kcl.write_text(source.read_text().replace("NaCl", "KCl").replace("Sodium", "Potassium")
            .replace("5.6500", "6.3000").replace("Na Cl", "K Cl").replace("Na1 Na", "K1 K"))
        phase2 = gpx.add_phase(str(kcl), phasename="KCl", histograms=[hist])
        phase2.HAPvalue("Scale", .5)
        specs.append(phase_from_cif(kcl, inspect_cif(kcl)[0]))
        specs[-1].name = "KCl"
        def mass_term(phase):
            general = phase.data["General"]
            # GSAS-II HAP scale convention already accounts for cell-volume normalization.
            return general["Mass"] * phase.HAPvalue("Scale")
        truth_fraction = mass_term(phase1) / (mass_term(phase1) + mass_term(phase2))
    for phase in gpx.phases():
        phase.set_refinements({"Cell": False, "Atoms": {"all": ""}})
        phase.set_HAP_refinements({"Scale": False})
    if sample_broadening:
        phase1.setSampleProfile(hist, "size", "isotropic", .08)
        phase1.setSampleProfile(hist, "microstrain", "isotropic", 250.)
    hist.set_refinements({"Background": {"no. coeffs": 3, "coeffs": [90., -15., 5.], "refine": False}})
    gpx.set_Controls("cycles", 0)
    gpx.do_refinements([{}])
    x = np.asarray(gpx.histogram(0).getdata("X"))
    expected = np.asarray(gpx.histogram(0).getdata("Ycalc"))
    observed = np.random.default_rng(47523).poisson(np.maximum(expected, 1)).astype(float)
    data = tmp_path / "synthetic.xye"
    np.savetxt(data, np.column_stack([x, observed, np.sqrt(np.maximum(observed, 1))]))
    instrument.instrument_file = str(instfile)
    config = ProjectConfig(name="SYNTHETIC scenario validation", powder_path=str(data),
        powder_options={"uncertainty": "column", "sigma_col": 2}, phases=specs, instrument=instrument,
        recipe=RecipeConfig(background_terms=3, profile_mode="sample" if sample_broadening else "fixed",
            refine_size=sample_broadening, refine_strain=sample_broadening,
            position_correction="zero" if doublet else "none", min_two_theta=20,
            max_two_theta=105, excluded_ranges=[[44, 45]]),
        output_dir=str(tmp_path / "run"), gsas_path=GSAS_PATH)
    path = tmp_path / "request.rsv.json"
    config.save(path)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    process = subprocess.run([sys.executable, "-m", "rietveld_studio.engine", str(path)],
        capture_output=True, text=True, env=env, timeout=180)
    assert process.returncode == 0, process.stdout[-6000:] + process.stderr[-2000:]
    result = json.loads((tmp_path / "run" / "result.json").read_text())
    return result, truth_fraction, x


@pytest.mark.integration
@pytest.mark.skipif(not GSAS_PATH, reason="GSASII_PATH required")
def test_doublet_multiphase_fractions_and_exclusions(tmp_path):
    result, true_fraction, x = _simulate_scenario(tmp_path, doublet=True, second_phase=True)
    nacl, kcl = result["phases"]
    assert nacl["weight_fraction"] == pytest.approx(true_fraction, abs=.025)
    assert nacl["weight_fraction"] + kcl["weight_fraction"] == pytest.approx(1, abs=1e-6)
    assert nacl["weight_fraction_su"] is not None
    assert kcl["cell"]["length_a"] == pytest.approx(6.3, abs=.001)
    assert {r["component"] for r in result["reflections"]} == {"Kα1", "Kα2"}
    assert result["statistics"]["n_observations"] == np.sum((x >= 20) & (x <= 105) & ~((x >= 44) & (x <= 45)))
    assert result["statistics"]["chi2_reduced"] < 1.4


@pytest.mark.integration
@pytest.mark.skipif(not GSAS_PATH, reason="GSASII_PATH required")
def test_calibrated_size_and_strain_recovery(tmp_path):
    result, _, _ = _simulate_scenario(tmp_path, sample_broadening=True)
    phase = result["phases"][0]
    assert phase["size_um"] == pytest.approx(.08, rel=.15)
    assert phase["microstrain_ppm"] == pytest.approx(250, rel=.20)
    assert phase["microstrain_su_ppm"] > 0
    assert abs(phase["microstrain_ppm"] - 250) < 4 * phase["microstrain_su_ppm"]
    assert result["statistics"]["chi2_reduced"] < 1.4


@pytest.mark.integration
@pytest.mark.skipif(not GSAS_PATH, reason="GSASII_PATH required")
def test_failed_stage_restores_previous_accepted_model(tmp_path, monkeypatch):
    from rietveld_studio import engine
    from rietveld_studio.models import ProjectConfig
    spec = importlib.util.spec_from_file_location("generate_rollback_demo", ROOT / "scripts" / "generate_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = module.generate(tmp_path / "simulation", GSAS_PATH)
    project = ProjectConfig.load(path)
    original_apply = engine._apply_stage
    def inject_failure(gpx, stage, config):
        original_apply(gpx, stage, config)
        if stage == "profile_lorentzian":
            gpx.phases()[0].data["General"]["Cell"][1] = 100
            raise RuntimeError("Injected stage failure for rollback verification")
    monkeypatch.setattr(engine, "_apply_stage", inject_failure)
    destination = engine.run_refinement(project)
    result = json.loads((destination / "result.json").read_text())
    assert any(s["stage"] == "profile_lorentzian" and not s["accepted"] for s in result["stage_history"])
    assert result["phases"][0]["cell"]["length_a"] == pytest.approx(5.6402, abs=.001)
    assert result["statistics"]["chi2_reduced"] < 1.3
    assert "Injected stage failure" in " ".join(result["warnings"])

