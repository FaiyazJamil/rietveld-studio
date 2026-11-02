"""GSAS-II adapter. Runs only in an isolated worker, never in the Qt GUI thread."""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import platform
import re
import shutil
import sys
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .analysis import associate_peaks, correlation_diagnostics, json_safe, profile_statistics
from .initialization import background_strategy
from .models import ProjectConfig
from .powder import load_powder
from .structures import select_block


def load_gsas(path=""):
    path = path or os.environ.get("GSASII_PATH", "")
    if not path:
        bundled_install = Path(__file__).resolve().parents[2] / ".engine" / "GSAS-II"
        if bundled_install.is_dir():
            path = str(bundled_install)
    if path:
        location = Path(path).expanduser().resolve()
        candidates = [location, location.parent]
        for candidate in candidates:
            if (candidate / "GSASII" / "GSASIIscriptable.py").is_file():
                sys.path.insert(0, str(candidate))
                break
        else:
            raise RuntimeError(f"No supported GSAS-II source package found at {location}. Choose its repository root or GSASII subfolder.")
    try:
        g2 = importlib.import_module("GSASII.GSASIIscriptable")
    except ImportError as exc:
        raise RuntimeError("GSAS-II cannot be imported. Run the bundled setup or choose the GSAS-II Python executable and source folder in Engine settings.") from exc
    gsas_path = importlib.import_module("GSASII.GSASIIpath")
    if not getattr(gsas_path, "BinaryPathLoaded", False):
        raise RuntimeError("GSAS-II Python code was found, but compiled modules are missing or incompatible. Run scripts/bootstrap_engine.py in the engine environment.")
    # Some source distributions load extensions at top level; pip builds keep them in GSASII.
    for name in ("pyspg", "pypowder"):
        try:
            module = importlib.import_module(f"GSASII.{name}")
        except ImportError:
            module = importlib.import_module(name)
        if name == "pyspg" and not hasattr(module, "sgforpy"):
            raise RuntimeError("GSAS-II symmetry module is incompatible.")
    return g2


def doctor(path="") -> dict:
    try:
        g2 = load_gsas(path)
        from GSASII import GSASIIpath
        return {"ok": True, "python": sys.executable, "python_version": platform.python_version(),
                "numpy": np.__version__, "gsas_module": g2.__file__,
                "gsas_version": str(GSASIIpath.GetVersionNumber()),
                "binary_path": str(getattr(GSASIIpath, "binaryPath", "co-located"))}
    except Exception as exc:
        return {"ok": False, "python": sys.executable, "error": str(exc)}


def write_instrument(config, path):
    config.validate()
    label = "lab data" if config.geometry == "Bragg-Brentano" else "transmission data"
    lines = [f"#GSAS-II instrument parameter file; Rietveld Studio {label}", "Type:PXC;Bank:1"]
    if config.wavelength2 is not None:
        lines.append(f"Lam1:{config.wavelength};Lam2:{config.wavelength2};I(L2)/I(L1):{config.ka2_ratio};Zero:0.0")
    else:
        lines.append(f"Lam:{config.wavelength};Zero:0.0")
    lines.append(f"Polariz.:{config.polarization};Azimuth:0.0")
    lines.append(f"U:{config.u};V:{config.v};W:{config.w};X:{config.x};Y:{config.y};Z:0.0;SH/L:{config.shl}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _slug(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")[:80] or "phase"


def _emit(callback, **event):
    if callback:
        callback(json_safe(event))


def _cov(gpx):
    return gpx.data.get("Covariance", {}).get("data", {})


def _parameters(gpx):
    cov = _cov(gpx)
    rows = []
    shifts = cov.get("Lastshft", [None] * len(cov.get("varyList", [])))
    last_shifts = cov.get("Rvals", {}).get("lastShifts", {})
    for name, value, su, stage_shift in zip(cov.get("varyList", []), cov.get("variables", []), cov.get("sig", []), shifts):
        shift = last_shifts.get(name)
        rows.append({"parameter": name, "value": value, "standard_uncertainty": su,
                     "last_shift": shift, "stage_total_shift": stage_shift,
                     "shift_over_su": abs(shift / su) if shift is not None and su > 0 else None})
    return json_safe(rows)


def _physical_issues(gpx, initial_cells, x):
    issues = []
    for phase in gpx.phases():
        cell = phase.get_cell()
        initial = initial_cells[phase.name]
        if not all(math.isfinite(float(v)) and v > 0 for v in cell.values()):
            issues.append(f"{phase.name}: invalid unit cell")
        if abs(cell["volume"] / initial["volume"] - 1) > .20:
            issues.append(f"{phase.name}: volume changed more than 20% from the starting CIF")
        for atom in phase.atoms():
            if not all(math.isfinite(float(v)) for v in atom.coordinates):
                issues.append(f"{phase.name}/{atom.label}: nonfinite coordinates")
            if atom.adp_flag == "I" and not 0 <= atom.uiso <= .15:
                issues.append(f"{phase.name}/{atom.label}: Uiso outside 0–0.15 Å²")
        hap = phase.data["Histograms"][gpx.histogram(0).name]
        if hap["Scale"][0] <= 0:
            issues.append(f"{phase.name}: nonpositive scale")
        if hap["Size"][1][0] <= 0 or hap["Mustrain"][1][0] < 0:
            issues.append(f"{phase.name}: nonphysical sample broadening")
        if hap["Pref.Ori."][0] == "MD" and hap["Pref.Ori."][1] <= 0:
            issues.append(f"{phase.name}: nonpositive March-Dollase ratio")
    hist = gpx.histogram(0)
    inst = hist.InstrumentParameters
    tan = np.tan(np.radians(x / 2))
    gaussian = inst["U"][1] * tan**2 + inst["V"][1] * tan + inst["W"][1]
    if np.any(gaussian <= 0):
        issues.append("Instrument Gaussian profile variance is nonpositive within the fit range")
    lorentz = inst["X"][1] / np.cos(np.radians(x / 2)) + inst["Y"][1] * tan + inst.get("Z", [0, 0])[1]
    if np.any(lorentz < -1e-7):
        issues.append("Instrument Lorentzian broadening is negative within the fit range")
    if hist.SampleParameters["Scale"][0] <= 0:
        issues.append("Nonpositive histogram scale")
    return issues


def _apply_stage(gpx, name, config):
    hist = gpx.histogram(0)
    if name == "background_scale":
        hist.set_refinements({"Background": {"type": "chebyschev-1", "no. coeffs": background_strategy(config)["effective_terms"],
                                            "refine": True}, "Sample Parameters": ["Scale"]})
        for i, phase in enumerate(gpx.phases()):
            phase.set_HAP_refinements({"Scale": i > 0})
    elif name == "position":
        if config.recipe.position_correction == "zero":
            hist.set_refinements({"Instrument Parameters": ["Zero"]})
        else:
            hist.set_refinements({"Sample Parameters": ["Shift"]})
    elif name == "cell":
        for phase, spec in zip(gpx.phases(), config.phases):
            phase.set_refinements({"Cell": spec.refine_cell})
    elif name == "profile_gaussian":
        hist.set_refinements({"Instrument Parameters": ["U", "V", "W"]})
    elif name == "profile_lorentzian":
        hist.set_refinements({"Instrument Parameters": ["X", "Y"]})
    elif name == "profile_asymmetry":
        hist.set_refinements({"Instrument Parameters": ["SH/L"]})
        gpx.set_Controls("parmMin", .0001, variable=f":{hist.id}:SH/L")
        gpx.set_Controls("parmMax", .1, variable=f":{hist.id}:SH/L")
    elif name == "size":
        for phase, spec in zip(gpx.phases(), config.phases):
            phase.setSampleProfile(hist, "size", "isotropic", spec.initial_size_um if spec.initial_size_um is not None else .2)
            phase.set_HAP_refinements({"Size": {"type": "isotropic", "refine": True}})
    elif name == "strain":
        for phase, spec in zip(gpx.phases(), config.phases):
            phase.setSampleProfile(hist, "microstrain", "isotropic", spec.initial_strain_ppm if spec.initial_strain_ppm is not None else 100.)
            phase.set_HAP_refinements({"Mustrain": {"type": "isotropic", "refine": True}})
    elif name == "orientation":
        for phase, spec in zip(gpx.phases(), config.phases):
            phase.HAPvalue("PO", 1)
            if spec.initial_march_dollase is not None:
                phase.data["Histograms"][hist.name]["Pref.Ori."][1] = spec.initial_march_dollase
            phase.data["Histograms"][hist.name]["Pref.Ori."][3] = config.recipe.orientation_axis
            phase.set_HAP_refinements({"Pref.Ori.": True})
    elif name == "positions":
        for phase in gpx.phases():
            phase.set_refinements({"Atoms": {a.label: "X" for a in phase.atoms()}})
    elif name == "uiso":
        for phase in gpx.phases():
            for atom in phase.atoms():
                if atom.adp_flag == "I":
                    atom.refinement_flags = ("X" if config.recipe.refine_positions else "") + "U"
    elif name != "final":
        raise ValueError(f"Unknown refinement stage: {name}")


def _recipe(config):
    r = config.recipe
    stages = ["background_scale"]
    if r.position_correction != "none":
        stages.append("position")
    if r.refine_cell:
        stages.append("cell")
    if r.profile_mode == "instrument":
        stages += ["profile_gaussian", "profile_lorentzian"]
        if r.refine_asymmetry:
            stages.append("profile_asymmetry")
    if r.profile_mode == "sample" and r.refine_size:
        stages.append("size")
    if r.profile_mode == "sample" and r.refine_strain:
        stages.append("strain")
    if r.preferred_orientation:
        stages.append("orientation")
    if r.refine_positions:
        stages.append("positions")
    if r.refine_uiso:
        stages.append("uiso")
    return stages + ["final"]


def run_refinement(config: ProjectConfig, callback=None) -> Path:
    config.validate()
    g2 = load_gsas(config.gsas_path)
    output = Path(config.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "result.json").exists() or (output / "refinement.gpx").exists():
        raise ValueError("Output folder already contains a refinement. Choose a new run folder to preserve it.")
    inputs = output / "inputs"
    checkpoints = output / "checkpoints"
    inputs.mkdir(exist_ok=True)
    checkpoints.mkdir(exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    powder = load_powder(config.powder_path, **config.powder_options)
    mask = powder.fit_mask(config.recipe.min_two_theta, config.recipe.max_two_theta, config.recipe.excluded_ranges)
    powder.save_xye(inputs / "pattern.xye")
    original = inputs / ("original_powder" + Path(config.powder_path).suffix)
    if Path(config.powder_path).resolve() != original:
        shutil.copy2(config.powder_path, original)
    warnings = list(powder.warnings)
    if not config.instrument.calibrated:
        warnings.append("No calibrated instrument profile was declared. Absolute lattice parameters retain wavelength/zero/height systematic errors; size/strain quantification is disabled.")
    inst_path = inputs / "instrument.instprm"
    if config.instrument.instrument_file:
        shutil.copy2(config.instrument.instrument_file, inst_path)
    else:
        write_instrument(config.instrument, inst_path)
    gpx_path = output / "refinement.gpx"
    gpx = g2.G2Project(newgpx=str(gpx_path))
    gpx.set_Controls("cycles", config.recipe.cycles)
    hist = gpx.add_powder_histogram(str(inputs / "pattern.xye"), str(inst_path), fmthint="xye")
    restore_observations(hist, powder)
    if "C" not in str(hist.InstrumentParameters["Type"][0]) or "X" not in str(hist.InstrumentParameters["Type"][0]):
        raise ValueError("This interface supports constant-wavelength X-ray (PXC) instrument profiles only.")
    hist.SampleParameters["Type"] = config.instrument.geometry
    if config.instrument.geometry == "Bragg-Brentano":
        for key, value in {"Shift": 0.0, "Transparency": 0.0, "SurfRoughA": 0.0, "SurfRoughB": 0.0}.items():
            hist.SampleParameters.setdefault(key, [value, False])
    else:
        for key in ("Absorption", "DisplaceX", "DisplaceY"):
            hist.SampleParameters.setdefault(key, [0.0, False])
    hist.SampleParameters["Gonio. radius"] = config.instrument.radius_mm
    hist.SampleParameters["Scale"][1] = False
    # Calibration files sometimes contain refine flags: explicitly hold all initially.
    for value in hist.InstrumentParameters.values():
        if isinstance(value, list) and len(value) >= 3:
            value[2] = False
    # Importers may supply refinement flags on sample parameters as well.
    for value in hist.SampleParameters.values():
        if isinstance(value, list) and len(value) == 2 and isinstance(value[1], (bool, np.bool_)):
            value[1] = False
    if config.instrument.wavelength2 is not None and "Lam2" not in hist.InstrumentParameters:
        warnings.append("The selected instrument file is single-wavelength; it overrides the GUI doublet settings.")
    lo = max(float(powder.x[0]), config.recipe.min_two_theta or float(powder.x[0]))
    hi = min(float(powder.x[-1]), config.recipe.max_two_theta or float(powder.x[-1]))
    hist.set_refinements({"Limits": [lo, hi]})
    hist.data["Limits"][2:] = [list(pair) for pair in config.recipe.excluded_ranges]
    initial_cells = {}
    provenance = []
    for index, spec in enumerate(config.phases):
        phase_path = inputs / f"phase_{index + 1}_{_slug(spec.name)}.cif"
        select_block(spec.cif_path, spec.block_name, phase_path)
        phase = gpx.add_phase(str(phase_path), phasename=spec.name, histograms=[hist], fmthint="CIF")
        if phase.data["General"].get("Modulated") or phase.data["General"].get("Type") != "nuclear":
            raise ValueError("Modulated/magnetic phases need an expert GSAS-II workflow and are not supported here.")
        phase.set_refinements({"Cell": False, "LeBail": False, "Atoms": {"all": ""}})
        phase.set_HAP_refinements({"Scale": False, "Size": {"refine": False},
                                   "Mustrain": {"refine": False}, "Pref.Ori.": False})
        if spec.initial_size_um is not None:
            phase.setSampleProfile(hist, "size", "isotropic", spec.initial_size_um)
        if spec.initial_strain_ppm is not None:
            phase.setSampleProfile(hist, "microstrain", "isotropic", spec.initial_strain_ppm)
        initial_cells[phase.name] = phase.get_cell()
        source_hash = hashlib.sha256(Path(spec.cif_path).read_bytes()).hexdigest()
        if spec.sha256 and source_hash != spec.sha256:
            warnings.append(f"{spec.name}: source CIF bytes changed since selection; the actual input has been archived.")
        provenance.append(asdict(spec) | {"original_sha256": source_hash,
            "used_cif": str(phase_path.relative_to(output)),
            "used_sha256": hashlib.sha256(phase_path.read_bytes()).hexdigest()})
    gpx.save()
    from .optimization import optimize
    gpx, history, optimizer_notes, trials, iterations, convergence = optimize(
        g2, gpx, config, powder, mask, initial_cells, _recipe(config), _apply_stage, _physical_issues,
        lambda **event: _emit(callback, **event))
    warnings.extend(optimizer_notes)
    result = _extract(gpx, config, powder, mask, provenance, warnings, history, initial_cells)
    result["trial_history"] = trials
    result["iteration_history"] = iterations
    result["convergence"] = convergence
    if not convergence["converged"]:
        result["warnings"].append("The best numerical result was retained, but the requested Rwp/parameter-shift convergence criteria were not both established. Inspect iteration_history.csv and the residuals.")
    result["started_utc"] = started
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    result["engine"] = doctor(config.gsas_path)
    from . import __author__, __doi__, __license__, __repository__, __version__, software_citation
    result["application"] = {"name": "Rietveld Studio", "version": __version__,
                             "author": __author__, "license": __license__,
                             "doi": __doi__, "repository": __repository__,
                             "citation": software_citation()}
    result["inputs_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir() if p.is_file()}
    result["refined_cifs"] = {}
    used_names = set()
    for index, phase in enumerate(gpx.phases(), 1):
        destination = output / f"refined_{_slug(phase.name)}.cif"
        if destination.name in used_names:
            destination = output / f"refined_{index}_{_slug(phase.name)}.cif"
        used_names.add(destination.name)
        try:
            phase.export_CIF(str(destination))
            result["refined_cifs"][phase.name] = destination.name
        except Exception as exc:
            result["warnings"].append(f"Refined CIF export failed for {phase.name}: {exc}. The full model is preserved in refinement.gpx.")
    # A self-contained archived project points at the actual inputs, not the source cache.
    archived = ProjectConfig(**{k: v for k, v in config.__dict__.items() if k not in {"phases", "powder_options"}})
    from .models import PhaseSpec
    archived.phases = [PhaseSpec(**(asdict(s) | {"cif_path": str(output / p["used_cif"]), "block_name": ""}))
                       for s, p in zip(config.phases, provenance)]
    archived.powder_path = str(inputs / "pattern.xye")
    archived.powder_options = ({"uncertainty": "constant", "constant_sigma": config.powder_options.get("constant_sigma", 1.)}
        if "constant sigma" in powder.weighting else {"uncertainty": "column", "sigma_col": 2})
    archived.instrument = type(config.instrument)(**(asdict(config.instrument) | {"instrument_file": str(inst_path)}))
    archived.recipe = type(config.recipe)(**(asdict(config.recipe) | {"background_mode": background_strategy(config)["effective_mode"]}))
    archived.save(output / "project.rsv.json")
    actual = gpx.histogram(0).InstrumentParameters
    write_actual_instrument(actual, output / "refined_instrument.instprm")
    np.savez_compressed(output / "covariance.npz", covariance=result.pop("_covariance"),
                        correlation=result.pop("_correlation"), labels=np.array(result["variable_names"], dtype=str))
    np.savez_compressed(output / "profile.npz", **result.pop("_profile"))
    (output / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False), encoding="utf-8")
    _emit(callback, kind="export", message="Writing report, plots, tables, and Origin export package")
    from .reports import export_bundle
    export_bundle(output)
    _emit(callback, kind="complete", output_dir=str(output), statistics=result["statistics"])
    return output


def _extract(gpx, config, powder, requested_mask, provenance, warnings, history, initial_cells):
    hist = gpx.histogram(0)
    cov = _cov(gpx)
    arrays = {name: np.asarray(np.ma.getdata(hist.getdata(key)), dtype=float)
              for name, key in {"x": "X", "yobs": "Yobs", "ycalc": "Ycalc", "background": "Background", "weights": "Yweight"}.items()}
    if len(arrays["x"]) != len(powder.x) or not np.allclose(arrays["x"], powder.x, atol=1e-8, rtol=0):
        raise RuntimeError("The engine changed the powder grid; cannot safely align exclusions/statistics.")
    if not np.array_equal(arrays["yobs"], powder.y):
        raise RuntimeError("The engine changed observed intensities; results cannot be reported as a fit to the validated input.")
    if not np.allclose(arrays["weights"][requested_mask], (1. / powder.sigma**2)[requested_mask], rtol=1e-10, atol=1e-12):
        raise RuntimeError("The engine changed weights on included observations; check the input/engine adapter.")
    mask = requested_mask & ~np.ma.getmaskarray(hist.getdata("Yobs")) & (arrays["weights"] > 0)
    arrays["mask"] = mask
    arrays["residual"] = arrays["yobs"] - arrays["ycalc"]
    arrays["sigma"] = powder.sigma
    stats = profile_statistics(arrays["yobs"], arrays["ycalc"], arrays["weights"], mask, len(cov.get("varyList", [])))
    stats["statistical_interpretation"] = "descriptive_only" if "constant sigma" in powder.weighting else "conditional_on_declared_uncertainties"
    engine_rvals = json_safe(cov.get("Rvals", {}))
    # Numbers reported by the engine are retained separately from independently recomputed factors.
    residuals = hist.residuals
    if callable(residuals):
        residuals = residuals()
    correlations, correlation = correlation_diagnostics(cov.get("covMatrix", []), cov.get("varyList", []))
    if correlations:
        warnings.append(f"{len(correlations)} parameter pairs have |correlation| ≥ 0.90; inspect correlations.csv.")
    if engine_rvals.get("converged") is False:
        warnings.append("GSAS-II did not declare convergence for the final accepted model.")
    if engine_rvals.get("SVD0", 0):
        warnings.append(f"GSAS-II detected {engine_rvals['SVD0']} singular direction(s). Some parameters may be underdetermined.")
    if engine_rvals.get("msg"):
        warnings.append("GSAS-II: " + str(engine_rvals["msg"]))
    mass_fractions = {}
    if hasattr(hist, "ComputeMassFracs"):
        try:
            mass_fractions = hist.ComputeMassFracs()
        except Exception as exc:
            warnings.append(f"Weight-fraction uncertainties unavailable: {exc}")
    phase_rows, atom_rows, reflections = [], [], []
    parameter_uncertainties = dict(zip(cov.get("varyList", []), cov.get("sig", [])))
    for phase, spec in zip(gpx.phases(), config.phases):
        cell, esd = phase.get_cell_and_esd()
        cell_refined = bool(phase.data["General"]["Cell"][0])
        hap = phase.data["Histograms"][hist.name]
        density = getattr(phase, "density", None)
        try:
            fraction, fraction_su = mass_fractions[phase.name]
        except (KeyError, ValueError):
            fraction, fraction_su = (1.0, None) if len(gpx.phases()) == 1 else (None, None)
        phase_rows.append({"phase": phase.name, "space_group": phase.data["General"]["SGData"]["SpGrp"],
            "formula_from_cif": spec.formula, "cell": cell,
            "cell_su": {k: (v if cell_refined and v > 0 else None) for k, v in esd.items()},
            "cell_refined": cell_refined, "initial_cell": initial_cells[phase.name],
            "volume_change_percent": 100 * (cell["volume"] / initial_cells[phase.name]["volume"] - 1),
            "density_g_cm3": density, "weight_fraction": fraction, "weight_fraction_su": fraction_su,
            "R_F_percent": residuals.get(f"{phase.id}:{hist.id}:Rf"),
            "R_F2_percent": residuals.get(f"{phase.id}:{hist.id}:Rf^2"),
            "weight_fraction_basis": "normalized over modeled crystalline phases; amorphous content not determined",
            "scale": hap["Scale"][0], "size_um": hap["Size"][1][0] if any(hap["Size"][2]) else None,
            "size_su_um": parameter_uncertainties.get(f"{phase.id}:{hist.id}:Size;i"),
            "microstrain_ppm": hap["Mustrain"][1][0] if any(hap["Mustrain"][2]) else None,
            "microstrain_su_ppm": parameter_uncertainties.get(f"{phase.id}:{hist.id}:Mustrain;i"),
            "march_dollase": hap["Pref.Ori."][1] if hap["Pref.Ori."][2] else None,
            "march_dollase_su": parameter_uncertainties.get(f"{phase.id}:{hist.id}:MD")})
        for key, uncertainty_key in [("size_um", "size_su_um"), ("microstrain_ppm", "microstrain_su_ppm")]:
            value, uncertainty = phase_rows[-1][key], phase_rows[-1][uncertainty_key]
            if value is not None and uncertainty is not None and uncertainty > .5 * abs(value):
                warnings.append(f"{phase.name}: {key} has more than 50% relative standard uncertainty; it is poorly constrained.")
        for i, atom in enumerate(phase.atoms()):
            uiso = atom.uiso if atom.adp_flag == "I" else None
            dependent = cov.get("depSigDict", {})
            sigmas = dict(zip(cov.get("varyList", []), cov.get("sig", [])))
            def su_for(variable):
                if variable in sigmas:
                    return sigmas[variable]
                value = dependent.get(variable)
                return value[1] if isinstance(value, (tuple, list)) and len(value) > 1 and value[1] > 0 else None
            atom_rows.append({"phase": phase.name, "label": atom.label, "element": atom.element,
                "x": atom.coordinates[0], "y": atom.coordinates[1], "z": atom.coordinates[2],
                "x_su": su_for(f"{phase.id}::dAx:{i}"), "y_su": su_for(f"{phase.id}::dAy:{i}"),
                "z_su": su_for(f"{phase.id}::dAz:{i}"),
                "occupancy": atom.occupancy, "multiplicity": atom.mult, "Uiso_A2": uiso,
                "Uiso_su_A2": su_for(f"{phase.id}::AUiso:{i}") if uiso is not None else None,
                "Biso_A2": 8 * math.pi**2 * uiso if uiso is not None else None,
                "ADP_type": atom.adp_flag, "ADP_values": json_safe(atom.ADP),
                "refinement_flags": atom.refinement_flags,
                "uncertainties": "See parameters.csv for refined/dependent GSAS-II variable uncertainties."})
    inst = hist.InstrumentParameters
    wave = inst.get("Lam1", inst.get("Lam"))[1]
    for phase_name, data in hist.reflections().items():
        if data.get("Super"):
            raise ValueError("Superspace reflection arrays are not supported.")
        spec = next(s for s in config.phases if s.name == phase_name)
        for row in data["RefList"]:
            if row[3] <= 0 or not lohi(float(row[5]), arrays["x"][mask]):
                continue
            item = {"phase": phase_name, "h": int(row[0]), "k": int(row[1]), "l": int(row[2]),
                "multiplicity": int(row[3]), "d_A": float(row[4]), "two_theta": float(row[5]),
                "Fobs2": float(row[8]), "Fcalc2": float(row[9]), "Icalc": float(row[9] * row[11]),
                "component": "Kα1" if "Lam2" in inst else "monochromatic",
                "cod_id": spec.cod_id, "source_url": spec.source_url or "local CIF", "doi": spec.doi,
                "assignment_basis": "reflection calculated from confirmed structure with refined cell and engine position corrections"}
            reflections.append(item)
            if "Lam2" in inst:
                a1, a2 = wave / (2 * row[4]), inst["Lam2"][1] / (2 * row[4])
                if 0 < a1 < 1 and 0 < a2 < 1:
                    position2 = item["two_theta"] + 2 * math.degrees(math.asin(a2) - math.asin(a1))
                    reflections.append(item | {"two_theta": position2, "component": "Kα2",
                        "Icalc": item["Icalc"] * inst["I(L2)/I(L1)"][1],
                        "assignment_basis": "Bragg-law Kα2 position plus Kα1 position correction; intensity scaled by doublet ratio"})
    peak_matches = associate_peaks(arrays["x"], arrays["yobs"], arrays["background"], mask, reflections,
        tolerance=config.recipe.peak_tolerance_deg, prominence_fraction=config.recipe.peak_prominence_fraction)
    unassigned = sum(r["status"] == "unassigned" for r in peak_matches)
    if unassigned:
        warnings.append(f"{unassigned} detected observed peaks have no modeled reflection within tolerance. Inspect impurities, wavelength, and the selected model; these peaks have no automatic chemical identity.")
    if stats["Rwp_percent"] > 20:
        warnings.append("Rwp exceeds 20%. Its magnitude depends on background, intensity scale, and weights; inspect the full profile and residuals rather than applying a universal cutoff.")
    from .diagnostics import diagnose_fit
    fit_diagnostics = diagnose_fit(arrays, reflections, stats, powder.weighting)
    warnings.extend(fit_diagnostics["messages"])
    return {"schema_version": 1, "project_name": config.name, "statistics": stats,
        "engine_Rvals": engine_rvals, "engine_histogram_residuals": json_safe(residuals),
        "fit_diagnostics": fit_diagnostics,
        "weighting": powder.weighting, "phases": json_safe(phase_rows), "atoms": json_safe(atom_rows),
        "reflections": reflections, "peak_matches": peak_matches, "parameters": _parameters(gpx),
        "correlations": correlations, "variable_names": list(cov.get("varyList", [])),
        "instrument_actual": json_safe(inst), "sample_parameters_actual": json_safe(hist.SampleParameters),
        "background_actual": json_safe(hist.Background), "requested_settings": asdict(config),
        "provenance": provenance, "stage_history": history, "warnings": list(dict.fromkeys(warnings)),
        "_profile": arrays, "_covariance": np.asarray(cov.get("covMatrix", [])), "_correlation": correlation}


def lohi(position, x):
    return float(x[0]) <= position <= float(x[-1])


def restore_observations(histogram, powder):
    """The generic XYE reader suppresses y<=0 even with positive supplied sigma.

    Our input layer has validated the uncertainty model. Restore its observations
    and positive weights before refinement, including valid zero counts and
    negative/background-subtracted values; the explicit fit mask still applies.
    """
    grid = np.asarray(np.ma.getdata(histogram.getdata("X")), dtype=float)
    if len(grid) != len(powder.x) or not np.allclose(grid, powder.x, rtol=0, atol=1e-8):
        raise ValueError("The GSAS-II reader changed the input grid; cannot safely restore observations.")
    arrays = histogram.data["data"][1]
    arrays[1] = powder.y.copy()
    arrays[2] = 1. / powder.sigma**2


def write_actual_instrument(instrument, destination):
    lines = ["#GSAS-II instrument parameter file; fitted effective profile from Rietveld Studio"]
    for name, values in instrument.items():
        if isinstance(values, list) and len(values) >= 2:
            lines.append(f"{name}:{values[1]}")
    Path(destination).write_text("\n".join(lines) + "\n", encoding="utf-8")


def worker_main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("project", nargs="?")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--gsas-path", default=os.environ.get("GSASII_PATH", ""))
    args = parser.parse_args(argv)
    if args.doctor:
        result = doctor(args.gsas_path)
        print("RS_EVENT " + json.dumps({"kind": "doctor", **result}), flush=True)
        return 0 if result["ok"] else 1
    if not args.project:
        parser.error("project file required")
    config = ProjectConfig.load(args.project)
    log = Path(config.output_dir) / "engine.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    # stdout is streamed to the GUI; the same lines are retained for traceability.
    class Tee:
        def __init__(self, original, file):
            self.original, self.file = original, file
        def write(self, message):
            self.file.write(message)
            self.file.flush()
            self.original.write(message)
            self.original.flush()
            return len(message)
        def flush(self):
            self.file.flush()
            self.original.flush()
        def __getattr__(self, name):
            return getattr(self.original, name)
    with log.open("w", encoding="utf-8") as stream:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = Tee(old_out, stream), Tee(old_err, stream)
        try:
            run_refinement(config, lambda event: print("RS_EVENT " + json.dumps(event, allow_nan=False), flush=True))
        except Exception as exc:
            traceback.print_exc()
            print("RS_EVENT " + json.dumps({"kind": "error", "message": str(exc)}), flush=True)
            return 1
        finally:
            sys.stdout, sys.stderr = old_out, old_err
    return 0


if __name__ == "__main__":
    raise SystemExit(worker_main())

