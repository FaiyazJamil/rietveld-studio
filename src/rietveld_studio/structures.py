from __future__ import annotations

import hashlib
import math
from pathlib import Path

import gemmi

from .models import PhaseSpec


def _value(block, *keys):
    for key in keys:
        value = block.find_value(key)
        if value and value not in {"?", "."}:
            return gemmi.cif.as_string(value)
    return ""


def inspect_cif(source: str | Path, *, text=False) -> list[dict]:
    document = gemmi.cif.read_string(str(source)) if text else gemmi.cif.read_file(str(source))
    records = []
    for block in document:
        if not block.find_value("_cell_length_a"):
            continue
        structure = gemmi.make_small_structure_from_block(block)
        if not structure.sites:
            continue
        if not structure.spacegroup:
            structure.determine_and_set_spacegroup("prefer_hm")
        if not structure.spacegroup:
            raise ValueError(f"CIF block {block.name}: space group is missing or cannot be resolved.")
        cell = structure.cell
        values = [cell.a, cell.b, cell.c, cell.alpha, cell.beta, cell.gamma, cell.volume]
        if not all(math.isfinite(v) and v > 0 for v in values) or cell.volume > 1e7:
            raise ValueError(f"CIF block {block.name}: invalid or excessively large unit cell.")
        warnings = []
        for site in structure.sites:
            if site.element.atomic_number < 1:
                raise ValueError(f"Unrecognized element on site {site.label}.")
            if not 0 < site.occ <= 1.0001:
                warnings.append(f"Site {site.label} has occupancy {site.occ:g}; inspect the model.")
        records.append({"block_name": block.name,
            "formula": _value(block, "_chemical_formula_sum", "_chemical_formula_structural"),
            "name": _value(block, "_chemical_name_common", "_chemical_name_mineral", "_chemical_name_systematic") or block.name,
            "space_group": structure.spacegroup.xhm(), "cell": values,
            "doi": _value(block, "_journal_paper_doi"),
            "citation": _value(block, "_publ_section_title"),
            "sites": [{"label": s.label, "element": s.element.name, "x": s.fract.x, "y": s.fract.y,
                       "z": s.fract.z, "occupancy": s.occ, "u_iso": s.u_iso} for s in structure.sites],
            "warnings": warnings})
    if not records:
        raise ValueError("No usable small-molecule/inorganic crystal block with unit cell and atomic sites in CIF.")
    return records


def select_block(source: str | Path, block_name: str, destination: str | Path) -> Path:
    document = gemmi.cif.read_file(str(source))
    block = document.find_block(block_name) if block_name else document.sole_block()
    if block is None:
        raise ValueError(f"CIF block not found: {block_name}")
    selected = gemmi.cif.Document()
    selected.add_copied_block(block)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    selected.write_file(str(destination))
    return destination


def phase_from_cif(path: str | Path, record: dict, metadata: dict | None = None) -> PhaseSpec:
    metadata = metadata or {}
    return PhaseSpec(name=record["formula"] or record["name"], cif_path=str(Path(path).resolve()),
        block_name=record["block_name"], formula=record["formula"], space_group=record["space_group"],
        cod_id=metadata.get("cod_id", ""), source_url=metadata.get("source_url", ""),
        doi=metadata.get("doi", "") or record["doi"], citation=metadata.get("citation", "") or record["citation"],
        sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(), retrieved_utc=metadata.get("retrieved_utc", ""))


def preview_reflections(phase: PhaseSpec, wavelength: float, minimum: float = 5, maximum: float = 100) -> list[dict]:
    """Independent CIF-derived stick positions, not a refinement or reference-card intensity."""
    document = gemmi.cif.read_file(phase.cif_path)
    block = document.find_block(phase.block_name) if phase.block_name else document.sole_block()
    structure = gemmi.make_small_structure_from_block(block)
    if not structure.spacegroup:
        structure.determine_and_set_spacegroup("prefer_hm")
    structure.setup_cell_images()
    dmin = wavelength / (2 * math.sin(math.radians(maximum / 2)))
    hkls = gemmi.make_miller_array(structure.cell, structure.spacegroup, dmin)
    if len(hkls) > 20000:
        raise ValueError("Too many preview reflections; narrow the angle range.")
    calculator = gemmi.StructureFactorCalculatorX(structure.cell)
    operations = structure.spacegroup.operations()
    reflections = []
    for hkl in hkls:
        hkl = tuple(int(x) for x in hkl)
        if operations.is_systematically_absent(hkl):
            continue
        d = structure.cell.calculate_d(hkl)
        argument = wavelength / (2 * d)
        if not 0 < argument < 1:
            continue
        theta = math.asin(argument)
        position = math.degrees(theta) * 2
        if not minimum <= position <= maximum:
            continue
        equivalents = {tuple(op.apply_to_hkl(hkl)) for op in operations}
        equivalents |= {tuple(-v for v in h) for h in list(equivalents)}
        f2 = abs(calculator.calculate_sf_from_small_structure(structure, hkl)) ** 2
        lp = (1 + math.cos(2 * theta)**2) / max(math.sin(theta)**2 * math.cos(theta), 1e-12)
        reflections.append({"phase": phase.name, "h": hkl[0], "k": hkl[1], "l": hkl[2],
            "d_A": d, "two_theta": position, "intensity": f2 * len(equivalents) * lp,
            "source_url": phase.source_url, "cod_id": phase.cod_id})
    maximum_intensity = max((r["intensity"] for r in reflections), default=1) or 1
    for row in reflections:
        row["intensity"] = row["intensity"] / maximum_intensity * 100
    return sorted(reflections, key=lambda r: r["two_theta"])

