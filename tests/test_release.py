"""Protect release identity across citation updates and future versions."""
from __future__ import annotations

import importlib.util
import json
import runpy
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def release_tool(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("prepare_release", ROOT / "scripts/prepare_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ["release-metadata.json", "CITATION.cff", "CITATION.bib", "CITATION.md", ".zenodo.json",
                 "README.md", "pyproject.toml", "src/rietveld_studio/__init__.py"]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module, tmp_path


def test_next_version_does_not_reuse_previous_version_doi(release_tool):
    tool, root = release_tool
    # Deliberately artificial syntax fixtures, never assigned to the real package.
    version_doi = "10.5281/zenodo.999999999999901"
    concept_doi = "10.5281/zenodo.999999999999902"
    assert tool.main(["--doi", version_doi, "--concept-doi", concept_doi]) == 0
    assert version_doi in (root / "CITATION.cff").read_text()
    assert "doi" not in json.loads((root / ".zenodo.json").read_text())
    current_version = json.loads((root / "release-metadata.json").read_text())["version"]
    major, minor, patch = current_version.split(".")
    next_version = f"{major}.{minor}.{int(patch) + 1}"
    assert tool.main(["--version", next_version, "--release-date", "2026-11-03"]) == 0
    metadata = json.loads((root / "release-metadata.json").read_text())
    assert metadata["version_doi"] == ""
    assert metadata["concept_doi"] == concept_doi
    assert version_doi not in (root / "CITATION.cff").read_text()
    assert version_doi not in (root / "CITATION.bib").read_text()
    assert tool.main(["--check"]) == 0


def test_check_detects_metadata_drift_without_overwriting_it(release_tool):
    tool, root = release_tool
    assert tool.main(["--check"]) == 0
    path = root / "CITATION.cff"
    edited = path.read_text().replace('family-names: "Jamil"', 'family-names: "Unintended edit"')
    path.write_text(edited)
    assert tool.main(["--check"]) == 1
    assert path.read_text() == edited


def test_current_doi_is_not_attached_to_an_older_result(release_tool):
    tool, root = release_tool
    version_doi = "10.5281/zenodo.999999999999901"
    assert tool.main(["--doi", version_doi]) == 0
    namespace = runpy.run_path(str(root / "src/rietveld_studio/__init__.py"))
    citation = namespace["software_citation"]
    assert version_doi in citation(namespace["__version__"])
    old_citation = citation("0.0.0")
    assert "0.0.0" in old_citation
    assert version_doi not in old_citation


@pytest.mark.parametrize("field,value", [
    ("repository_url", "https://github.com/YOUR-USERNAME/rietveld-studio"),
    ("version_doi", "YOUR-REAL-VERSION-DOI"),
    ("version_doi", "10.5072/zenodo.12345"),
])
def test_placeholder_and_sandbox_identifiers_are_rejected(release_tool, field, value):
    tool, root = release_tool
    metadata = json.loads((root / "release-metadata.json").read_text())
    metadata[field] = value
    with pytest.raises(ValueError):
        tool.validate_metadata(metadata)


def test_orcid_checksum_is_checked_before_writing_metadata(release_tool):
    tool, root = release_tool
    metadata = json.loads((root / "release-metadata.json").read_text())
    metadata["author"]["orcid"] = "0000-0000-0000-0000"
    with pytest.raises(ValueError, match="checksum"):
        tool.validate_metadata(metadata)
