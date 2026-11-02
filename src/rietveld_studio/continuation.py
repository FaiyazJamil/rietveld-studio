"""Prepare a new independent run from exported refined structural/profile parameters."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .engine import _slug
from .models import ProjectConfig
from .structures import inspect_cif


def continuation_project(directory):
    directory = Path(directory).resolve()
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    project = ProjectConfig.load(directory / "project.rsv.json")
    for spec, summary in zip(project.phases, result["phases"]):
        path = directory / result.get("refined_cifs", {}).get(spec.name, f"refined_{_slug(spec.name)}.cif")
        if not path.is_file():
            raise ValueError(f"Refined CIF unavailable for {spec.name}; inspect the previous export log.")
        record = inspect_cif(path)[0]
        spec.cif_path, spec.block_name = str(path), record["block_name"]
        spec.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        spec.initial_size_um = summary.get("size_um")
        spec.initial_strain_ppm = summary.get("microstrain_ppm")
        spec.initial_march_dollase = summary.get("march_dollase")
    instrument = directory / "refined_instrument.instprm"
    if not instrument.is_file():
        from .engine import write_actual_instrument
        write_actual_instrument(result["instrument_actual"], instrument)
    project.instrument.instrument_file = str(instrument)
    project.name += " · continuation"
    project.continued_from = str(directory)
    project.recipe.auto_initialize = False
    project.recipe.start_trials = 1
    project.recipe.background_mode = result.get("convergence", {}).get("background_strategy", {}).get(
        "effective_mode", project.recipe.background_mode)
    # Older archives labeled every normalized XYE as supplied sigma, including artificial constants.
    # Retain the actual original uncertainty provenance when continuing these results.
    if "constant sigma" in result["weighting"]:
        original = result["requested_settings"]["powder_options"]
        project.powder_options = {"uncertainty": "constant", "constant_sigma": original.get("constant_sigma", 1.)}
    return project

