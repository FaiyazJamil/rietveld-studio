"""Import with explicit uncertainty semantics; never smooth data used for fitting."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class PowderData:
    x: np.ndarray
    y: np.ndarray
    sigma: np.ndarray
    weighting: str
    source: str = ""
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.x = np.asarray(self.x, dtype=float)
        self.y = np.asarray(self.y, dtype=float)
        self.sigma = np.asarray(self.sigma, dtype=float)
        if len(self.x) < 30 or not (self.x.shape == self.y.shape == self.sigma.shape):
            raise ValueError("A powder pattern needs at least 30 rows with matching X, Y, and sigma lengths.")
        if not all(np.all(np.isfinite(a)) for a in (self.x, self.y, self.sigma)):
            raise ValueError("Powder data contain NaN or infinity.")
        if np.any(self.sigma <= 0):
            raise ValueError("All standard uncertainties (sigma) must be positive.")
        if np.any(np.diff(self.x) <= 0):
            raise ValueError("2θ must be strictly increasing with no duplicate positions.")
        if self.x[0] <= 0 or self.x[-1] >= 180:
            raise ValueError("This version expects constant-wavelength XRD: 0 < 2θ < 180 degrees.")
        if np.max(self.y) <= 0:
            raise ValueError("No positive diffraction intensities were found.")

    def fit_mask(self, lo=None, hi=None, excluded=()) -> np.ndarray:
        mask = np.ones(len(self.x), dtype=bool)
        if lo is not None:
            mask &= self.x >= lo
        if hi is not None:
            mask &= self.x <= hi
        for a, b in excluded:
            mask &= ~((self.x >= a) & (self.x <= b))
        if mask.sum() < 30:
            raise ValueError("Fit range and exclusions leave fewer than 30 observations.")
        return mask

    def save_xye(self, path: str | Path) -> None:
        np.savetxt(path, np.column_stack((self.x, self.y, self.sigma)), fmt="%.12g",
                   header="2theta_degrees intensity sigma; normalized by Rietveld Studio")


def load_powder(path: str | Path, *, x_col: int = 0, y_col: int = 1, sigma_col: int | None = None,
                uncertainty: str = "poisson", delimiter: str = "auto", skip_rows: int = 0,
                sort_x: bool = False, constant_sigma: float = 1.0) -> PowderData:
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Powder file does not exist: {path}")
    if path.stat().st_size > 100 * 1024**2:
        raise ValueError("Powder input exceeds the 100 MiB desktop import limit.")
    warnings = []
    if path.suffix.lower() == ".xrdml":
        x, y, sigma, weighting, notes = _load_xrdml(path)
        warnings.extend(notes)
        return PowderData(x, y, sigma, weighting, str(path.resolve()), warnings)
    if path.suffix.lower() in {".raw", ".brml", ".gpx", ".rasx", ".nxs"}:
        raise ValueError("Export this vendor/binary file as XY/XYE/CSV first. XRDML is supported directly.")
    if min(x_col, y_col) < 0 or x_col == y_col or (sigma_col is not None and sigma_col < 0):
        raise ValueError("Select distinct, nonnegative X/Y column indices.")
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("This appears to be a binary or non-UTF8 file; export numeric XY/XYE first.") from exc
    if "\x00" in content:
        raise ValueError("Binary powder data are not supported; export numeric XY/XYE.")
    rows, started, skipped_header = [], False, 0
    max_col = max(x_col, y_col, sigma_col if sigma_col is not None and uncertainty == "column" else 0)
    for line_number, line in enumerate(content.splitlines()[skip_rows:], start=skip_rows + 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!", ";", "//")):
            continue
        if delimiter == "auto":
            parts = re.split(r"[\s,;]+", stripped)
        elif delimiter in {"space", "whitespace"}:
            parts = stripped.split()
        else:
            parts = stripped.split({"tab": "\t", "comma": ",", "semicolon": ";"}.get(delimiter, delimiter))
        try:
            if len(parts) <= max_col:
                raise ValueError("too few columns")
            row = [float(p.replace("D", "E").replace("d", "e")) for p in parts]
        except ValueError as exc:
            if not started:
                skipped_header += 1
                continue
            raise ValueError(f"Invalid numeric row at line {line_number}; check delimiter/columns.") from exc
        started = True
        rows.append(row)
    if len(rows) < 30:
        raise ValueError("Fewer than 30 numeric rows found; check delimiter, skip rows, and columns.")
    x = np.array([r[x_col] for r in rows])
    y = np.array([r[y_col] for r in rows])
    if uncertainty == "column":
        if sigma_col is None or sigma_col in {x_col, y_col}:
            raise ValueError("Choose a distinct sigma column; enter standard deviations, not variances or weights.")
        sigma = np.array([r[sigma_col] for r in rows])
        weighting = "supplied standard uncertainties; w=1/sigma²"
    elif uncertainty == "poisson":
        if np.any(y < 0):
            raise ValueError("Negative intensities require supplied sigma or explicitly chosen constant weights.")
        sigma = np.sqrt(np.maximum(y, 1.0))
        weighting = "estimated Poisson sigma=sqrt(max(counts,1)); w=1/sigma²"
        warnings.append("Poisson weighting assumes unnormalized, unprocessed counts. Use supplied sigma for CPS, normalized, or subtracted data.")
    elif uncertainty == "constant":
        if not np.isfinite(constant_sigma) or constant_sigma <= 0:
            raise ValueError("Constant sigma must be positive and finite.")
        sigma = np.full(len(x), constant_sigma)
        weighting = f"constant sigma={constant_sigma:g}; descriptive fit statistics only"
        warnings.append("Constant weights do not establish a statistically interpretable reduced chi-square.")
    else:
        raise ValueError("Uncertainty mode must be poisson, column, or constant.")
    if skipped_header:
        warnings.append(f"Skipped {skipped_header} nonnumeric header lines before the data.")
    if sort_x:
        order = np.argsort(x, kind="stable")
        x, y, sigma = x[order], y[order], sigma[order]
        warnings.append("Rows were sorted by increasing 2θ; duplicate positions are still rejected.")
    return PowderData(x, y, sigma, weighting, str(path.resolve()), warnings)


def _load_xrdml(path):
    # ElementTree does not resolve external entities. Cap input before parsing.
    root = ET.fromstring(path.read_bytes())
    def local(element):
        return element.tag.split("}")[-1]
    scans = [e for e in root.iter() if local(e) == "scan"]
    if len(scans) != 1:
        raise ValueError("XRDML must contain one scan. Export separate patterns for multiscans.")
    scan = scans[0]
    positions = next((e for e in scan.iter() if local(e) == "positions" and
                      e.attrib.get("axis", "").lower() in {"2theta", "2theta-omega"}), None)
    if positions is None:
        raise ValueError("No 2Theta axis found in XRDML.")
    children = {local(e): (e.text or "").strip() for e in positions}
    intensity = next((e for e in scan.iter() if local(e) in {"intensities", "counts"}), None)
    if intensity is None:
        raise ValueError("No intensity/counts block in XRDML.")
    y = np.fromstring(intensity.text or "", sep=" ")
    if "listPositions" in children:
        x = np.fromstring(children["listPositions"], sep=" ")
    else:
        x = np.linspace(float(children["startPosition"]), float(children["endPosition"]), len(y))
    unit = intensity.attrib.get("unit", "counts").lower()
    notes = []
    if unit in {"cps", "counts/s"}:
        time_node = next((e for e in scan.iter() if local(e) == "commonCountingTime"), None)
        if time_node is None or float(time_node.text or 0) <= 0:
            raise ValueError("CPS XRDML requires a positive commonCountingTime to propagate counting uncertainty.")
        seconds = float(time_node.text)
        sigma = np.sqrt(np.maximum(y * seconds, 1)) / seconds
        weighting = f"XRDML CPS: sigma=sqrt(max(CPS*t,1))/t; t={seconds:g} s"
    elif unit in {"counts", "count"}:
        sigma = np.sqrt(np.maximum(y, 1))
        weighting = "XRDML counts: Poisson sigma=sqrt(max(counts,1))"
    else:
        raise ValueError(f"Unsupported XRDML intensity unit: {unit}")
    if np.any(y < 0):
        raise ValueError("XRDML contains negative counts/CPS; supply XY-sigma instead.")
    notes.append("XRDML radiation metadata are not applied automatically; confirm instrument wavelength/geometry.")
    return x, y, sigma, weighting, notes

