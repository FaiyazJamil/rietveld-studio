from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PhaseSpec:
    name: str
    cif_path: str
    block_name: str = ""
    formula: str = ""
    space_group: str = ""
    cod_id: str = ""
    source_url: str = ""
    doi: str = ""
    citation: str = ""
    sha256: str = ""
    retrieved_utc: str = ""
    refine_cell: bool = True
    initial_size_um: float | None = None
    initial_strain_ppm: float | None = None
    initial_march_dollase: float | None = None


@dataclass
class InstrumentConfig:
    instrument_file: str = ""
    wavelength: float = 1.540593
    wavelength2: float | None = None
    ka2_ratio: float = 0.5
    geometry: str = "Bragg-Brentano"
    radius_mm: float = 200.0
    polarization: float = 0.5
    u: float = 2.0
    v: float = -1.0
    w: float = 5.0
    x: float = 0.0
    y: float = 0.0
    shl: float = 0.002
    calibrated: bool = False

    def validate(self) -> None:
        if self.instrument_file and not Path(self.instrument_file).is_file():
            raise ValueError("Instrument parameter file does not exist.")
        if not math.isfinite(self.wavelength) or not 0.05 <= self.wavelength <= 5:
            raise ValueError("Wavelength must be 0.05–5 Å.")
        if self.wavelength2 is not None and not 0.05 <= self.wavelength2 <= 5:
            raise ValueError("Second wavelength must be 0.05–5 Å.")
        if self.geometry not in {"Bragg-Brentano", "Debye-Scherrer"}:
            raise ValueError("Unsupported geometry.")
        if self.radius_mm <= 0 or not 0 <= self.polarization <= 1:
            raise ValueError("Invalid goniometer radius or polarization.")
        if not 0 < self.ka2_ratio <= 1:
            raise ValueError("Kα2/Kα1 ratio must be greater than zero and at most one.")


@dataclass
class RecipeConfig:
    background_terms: int = 6
    cycles: int = 12
    refine_cell: bool = True
    position_correction: str = "none"  # none, zero, displacement
    profile_mode: str = "instrument"  # fixed, instrument, sample
    refine_size: bool = False
    refine_strain: bool = False
    preferred_orientation: bool = False
    orientation_axis: list[int] = field(default_factory=lambda: [0, 0, 1])
    refine_positions: bool = False
    refine_uiso: bool = False
    min_two_theta: float | None = None
    max_two_theta: float | None = None
    excluded_ranges: list[list[float]] = field(default_factory=list)
    peak_tolerance_deg: float = 0.15
    peak_prominence_fraction: float = 0.025
    max_stage_rwp_increase: float = 0.02
    max_passes: int = 6
    min_passes: int = 2
    stable_passes: int = 2
    rwp_relative_tolerance: float = 1e-4
    shift_su_tolerance: float = 0.10
    start_trials: int = 3
    auto_initialize: bool = True
    cell_search_percent: float = 2.0
    background_mode: str = "auto"  # auto, raw, subtracted
    refine_asymmetry: bool = False

    def validate(self, instrument: InstrumentConfig) -> None:
        if not 1 <= self.min_passes <= self.max_passes <= 30 or not 1 <= self.stable_passes <= 5:
            raise ValueError("Choose 1–30 passes, min passes <= max passes, and 1–5 stable passes.")
        if not 1 <= self.start_trials <= 9:
            raise ValueError("Choose 1–9 independent refinement starts.")
        if not 1e-8 <= self.rwp_relative_tolerance <= .02 or not .001 <= self.shift_su_tolerance <= 1:
            raise ValueError("Invalid Rwp stability or shift/standard-uncertainty convergence threshold.")
        if not 0 <= self.cell_search_percent <= 5:
            raise ValueError("Initial lattice search must be between 0 and 5% in length.")
        if self.background_mode not in {"auto", "raw", "subtracted"}:
            raise ValueError("Background mode must be auto, raw, or subtracted.")
        if not 1 <= self.background_terms <= 24 or not 1 <= self.cycles <= 100:
            raise ValueError("Background terms must be 1–24 and cycles 1–100.")
        if self.position_correction not in {"none", "zero", "displacement"}:
            raise ValueError("Choose one position correction.")
        if self.position_correction == "displacement" and instrument.geometry != "Bragg-Brentano":
            raise ValueError("Sample-height displacement is implemented for Bragg-Brentano geometry only.")
        if self.profile_mode not in {"fixed", "instrument", "sample"}:
            raise ValueError("Unknown profile mode.")
        if (self.refine_size or self.refine_strain) and self.profile_mode != "sample":
            raise ValueError("Size/strain refinement requires sample-profile mode (instrument profile held fixed).")
        if (self.refine_size or self.refine_strain) and not instrument.calibrated:
            raise ValueError("Quantitative size/strain requires a calibrated instrumental profile.")
        if self.preferred_orientation and (len(self.orientation_axis) != 3 or not any(self.orientation_axis)):
            raise ValueError("Preferred-orientation axis must be a nonzero [h k l] direction.")
        if self.min_two_theta is not None and self.max_two_theta is not None:
            if self.min_two_theta >= self.max_two_theta:
                raise ValueError("Fit minimum must be less than maximum.")
        for lo, hi in self.excluded_ranges:
            if not (math.isfinite(lo) and math.isfinite(hi) and lo < hi):
                raise ValueError("Excluded ranges must be finite increasing pairs.")
        if not 0 < self.peak_tolerance_deg <= 2:
            raise ValueError("Peak matching tolerance must be greater than 0 and at most 2°.")


@dataclass
class ProjectConfig:
    name: str = "Untitled refinement"
    powder_path: str = ""
    powder_options: dict[str, Any] = field(default_factory=dict)
    phases: list[PhaseSpec] = field(default_factory=list)
    instrument: InstrumentConfig = field(default_factory=InstrumentConfig)
    recipe: RecipeConfig = field(default_factory=RecipeConfig)
    output_dir: str = ""
    engine_python: str = ""
    gsas_path: str = ""
    schema_version: int = 1
    continued_from: str = ""

    def validate(self) -> None:
        if not self.phases:
            raise ValueError("Confirm at least one phase/CIF before refining.")
        names = [p.name for p in self.phases]
        if len(set(names)) != len(names) or any(not n.strip() for n in names):
            raise ValueError("Phase names must be unique and nonempty.")
        for phase in self.phases:
            if not Path(phase.cif_path).is_file():
                raise ValueError(f"Missing CIF: {phase.cif_path}")
        if not Path(self.powder_path).is_file():
            raise ValueError("Select an existing powder-data file.")
        if not self.output_dir:
            raise ValueError("Choose an output directory.")
        self.instrument.validate()
        self.recipe.validate(self.instrument)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        # Store relative references for portable project folders whenever possible.
        for phase in payload["phases"]:
            phase["cif_path"] = _relative(phase["cif_path"], path.parent)
        for key in ("powder_path", "output_dir"):
            payload[key] = _relative(payload[key], path.parent)
        payload["instrument"]["instrument_file"] = _relative(payload["instrument"]["instrument_file"], path.parent)
        path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> ProjectConfig:
        path = Path(path).resolve()
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version", 1) != 1:
            raise ValueError("Unsupported project format version.")
        for item in data.get("phases", []):
            item["cif_path"] = _absolute(item["cif_path"], path.parent)
        for key in ("powder_path", "output_dir"):
            data[key] = _absolute(data.get(key, ""), path.parent)
        inst = data.get("instrument", {})
        inst["instrument_file"] = _absolute(inst.get("instrument_file", ""), path.parent)
        data["phases"] = [PhaseSpec(**p) for p in data.get("phases", [])]
        data["instrument"] = InstrumentConfig(**inst)
        data["recipe"] = RecipeConfig(**data.get("recipe", {}))
        return cls(**data)


def _relative(value: str, base: Path) -> str:
    if not value:
        return ""
    try:
        return str(Path(value).resolve().relative_to(base.resolve()))
    except ValueError:
        return str(Path(value).resolve())


def _absolute(value: str, base: Path) -> str:
    return str((base / value).resolve()) if value else ""

