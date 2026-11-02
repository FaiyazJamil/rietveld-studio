"""Install the tested GSAS-II source and official platform binaries without a compiler.

This script downloads from AdvancedPhotonSource's official GitHub repositories only.
Run it using the same Python interpreter selected for the refinement worker.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

GSAS_COMMIT = "eca9e6be4f33e0633676c6051939f5cc2d477107"
SOURCE_URL = f"https://codeload.github.com/AdvancedPhotonSource/GSAS-II/zip/{GSAS_COMMIT}"


def fetch(url, destination):
    request = urllib.request.Request(url, headers={"User-Agent": "RietveldStudio-EngineSetup/0.1"})
    with urllib.request.urlopen(request, timeout=60) as source, Path(destination).open("wb") as output:
        shutil.copyfileobj(source, output)


def install(destination):
    import numpy as np
    destination = Path(destination).expanduser().resolve()
    source_marker = destination / "RIETVELD_SOURCE.json"
    if sys.version_info[:2] not in {(3, 11), (3, 12), (3, 13)}:
        raise RuntimeError("Use Python 3.11, 3.12, or 3.13 for this tested engine installer.")
    if (destination / "GSASII" / "GSASIIscriptable.py").exists():
        metadata = source_marker if source_marker.exists() else destination / "RIETVELD_ENGINE_INSTALL.json"
        if not metadata.exists() or json.loads(metadata.read_text(encoding="utf-8")).get("source_commit") != GSAS_COMMIT:
            raise ValueError("An existing GSAS-II source tree has no matching installer record. Select it directly in the app, or choose a fresh bootstrap directory.")
    else:
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("Engine target is nonempty and not recognized as GSAS-II. Choose an empty directory.")
        destination.mkdir(parents=True, exist_ok=True)
        print(f"Downloading GSAS-II source at {GSAS_COMMIT}…", flush=True)
        with tempfile.TemporaryDirectory(prefix="rietveld-engine-") as temp:
            archive = Path(temp) / "gsas.zip"
            fetch(SOURCE_URL, archive)
            with zipfile.ZipFile(archive) as data:
                for entry in data.infolist():
                    relative = Path(*Path(entry.filename).parts[1:])
                    if not relative.parts:
                        continue
                    target = (destination / relative).resolve()
                    if not target.is_relative_to(destination):
                        raise ValueError("Unsafe path in source archive.")
                    if entry.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with data.open(entry) as source, target.open("wb") as output:
                            shutil.copyfileobj(source, output)
            source_marker.write_text(json.dumps({"source_commit": GSAS_COMMIT, "source_url": SOURCE_URL,
                "source_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}, indent=2), encoding="utf-8")
    sys.path.insert(0, str(destination))
    g2path = importlib.import_module("GSASII.GSASIIpath")
    # Use the official release listing, with bounded requests rather than unbounded retries.
    request = urllib.request.Request(g2path.G2binURL + "/releases", headers={"User-Agent": "RietveldStudio/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            releases = json.load(response)
        options = {}
        for release in reversed(releases):
            for asset in release.get("assets", []):
                name = asset["name"]
                if name.endswith(".tgz"):
                    options[name[:-4]] = asset["browser_download_url"]
    except Exception as exc:
        print(f"Release listing unavailable ({exc}); trying the official source cache.", flush=True)
        options = {}
        cache = destination / "GSASII" / "inputs" / "BinariesCache.txt"
        for line in cache.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                options[key.strip()] = value.strip()
    prefix = g2path.GetBinaryPrefix()
    versions = {}
    for name, url in options.items():
        if name.startswith(prefix):
            version = tuple(map(int, name.split("_n")[-1].split(".")[:2]))
            versions[version] = url
    if not versions:
        raise RuntimeError(f"No official binary available for {prefix}. Use a supported Python/platform or a normal GSAS-II installation.")
    numpy_version = tuple(map(int, np.__version__.split(".")[:2]))
    eligible = [v for v in versions if v <= numpy_version and v[0] == numpy_version[0]]
    if not eligible:
        raise RuntimeError(f"No ABI-compatible binary for NumPy {np.__version__}. The setup scripts use NumPy 2.2.6.")
    url = versions[max(eligible)]
    if not url.startswith("https://github.com/AdvancedPhotonSource/GSAS-II-buildtools/releases/download/"):
        raise RuntimeError("Refusing an unexpected binary download URL.")
    bindir = destination / "GSASII" / "bindist"
    bindir.mkdir(exist_ok=True)
    print(f"Downloading official binaries for Python {platform.python_version()}, NumPy {np.__version__}…", flush=True)
    with tempfile.TemporaryDirectory(prefix="rietveld-binaries-") as temp:
        archive = Path(temp) / "binaries.tgz"
        fetch(url, archive)
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        with tarfile.open(archive) as data:
            for member in data.getmembers():
                # Binaries are flat files. Do not permit paths, links, devices, or traversal.
                if not member.isfile() or Path(member.name).name != member.name or "\\" in member.name:
                    continue
                source = data.extractfile(member)
                if source is None:
                    continue
                target = bindir / member.name
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)
        (destination / "RIETVELD_ENGINE_INSTALL.json").write_text(json.dumps({"source_commit": GSAS_COMMIT,
            "source_url": SOURCE_URL, "binary_url": url, "binary_archive_sha256": checksum,
            "source_archive_sha256": json.loads(source_marker.read_text()).get("source_archive_sha256") if source_marker.exists() else None,
            "python": sys.version, "numpy": np.__version__}, indent=2), encoding="utf-8")
    # Import only after binaries are installed; a failed import caches the failed discovery.
    importlib.invalidate_caches()
    source = Path(__file__).resolve().parents[1] / "src"
    sys.path.insert(0, str(source))
    from rietveld_studio.engine import doctor
    result = doctor(str(destination))
    print(json.dumps(result, indent=2), flush=True)
    if not result["ok"]:
        raise RuntimeError("Engine verification failed: " + result.get("error", "unknown error"))
    print("Engine ready. Launch Rietveld Studio and use this source folder in Engine settings.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", default=str(Path(__file__).resolve().parents[1] / ".engine" / "GSAS-II"))
    args = parser.parse_args()
    try:
        install(args.destination)
    except Exception as exc:
        print(f"SETUP FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)

