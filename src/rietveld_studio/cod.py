from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from platformdirs import user_cache_path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .chemistry import composition_distance, parse_formula

COD_BASE = "https://www.crystallography.net/cod"


@dataclass
class CODCandidate:
    cod_id: str
    formula: str = ""
    name: str = ""
    space_group: str = ""
    a: str = ""
    b: str = ""
    c: str = ""
    year: str = ""
    doi: str = ""
    citation: str = ""
    distance: float | None = None

    @property
    def source_url(self):
        return f"{COD_BASE}/{self.cod_id}.html"


class CODClient:
    def __init__(self, cache_dir: str | Path | None = None):
        self.cache_dir = Path(cache_dir or user_cache_path("RietveldStudio", "RietveldStudio"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.7, status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"], respect_retry_after_header=False)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers["User-Agent"] = "RietveldStudio/0.1 (research desktop crystallography client)"
        self.last_notice = ""

    def _get(self, endpoint: str, params=None, maximum_bytes=12 * 1024**2) -> bytes:
        try:
            with self.session.get(f"{COD_BASE}/{endpoint}", params=params, timeout=(8, 30), stream=True) as response:
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > maximum_bytes:
                        raise ValueError("COD response is too large. Narrow the formula/keyword search.")
                    chunks.append(chunk)
                return b"".join(chunks)
        except requests.RequestException as exc:
            raise ConnectionError("COD could not be reached. Retry, use cached results, or import a local CIF.") from exc

    def search(self, query: str, *, mode="formula", exact_elements=True, limit=250,
               use_cache=True) -> list[CODCandidate]:
        query = query.strip()
        if not query:
            raise ValueError("Enter a chemistry, compound name, or COD ID.")
        params = {"format": "json"}
        target = None
        if mode == "id":
            if not re.fullmatch(r"\d{7}", query):
                raise ValueError("A COD ID is seven digits.")
            params["id"] = query
        elif mode == "keyword":
            params["text"] = query[:180]
        else:
            target = parse_formula(query)
            if len(target) > 8:
                raise ValueError("COD element search supports up to eight required elements.")
            params.update({f"el{i}": e for i, e in enumerate(sorted(target), 1)})
            if exact_elements:
                params.update(strictmin=str(len(target)), strictmax=str(len(target)))
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
        cache = self.cache_dir / f"search-{key}.json"
        self.last_notice = ""
        # Fresh responses are preferred; cached results are an explicit network-failure fallback.
        try:
            data = json.loads(self._get("result", params))
            if not isinstance(data, list):
                raise ValueError("Unexpected COD response; try a narrower search.")
            cache.write_text(json.dumps({"retrieved": datetime.now(timezone.utc).isoformat(), "data": data}), encoding="utf-8")
        except (ConnectionError, json.JSONDecodeError):
            if not use_cache or not cache.is_file():
                raise
            cached = json.loads(cache.read_text(encoding="utf-8"))
            data = cached["data"]
            self.last_notice = f"Offline cached search from {cached['retrieved']}."
        results = []
        for row in data:
            cod_id = str(row.get("file", row.get("id", "")))
            if not re.fullmatch(r"\d{7}", cod_id):
                continue
            formula = str(row.get("formula", "")).strip("- ")
            distance = None
            if target:
                try:
                    distance = composition_distance(target, parse_formula(formula))
                except ValueError:
                    pass
            citation = "; ".join(str(row.get(k, "") or "") for k in ("authors", "title", "journal", "year")
                                 if row.get(k))
            results.append(CODCandidate(cod_id=cod_id, formula=formula,
                name=str(row.get("chemname", row.get("mineral", "")) or row.get("title", "") or ""),
                space_group=str(row.get("sg", "") or row.get("spacegroup", "")),
                a=str(row.get("a", "")), b=str(row.get("b", "")), c=str(row.get("c", "")),
                year=str(row.get("year", "") or ""), doi=str(row.get("doi", "") or ""),
                citation=citation, distance=distance))
        # Tie-breakers prioritize an identifiable publication, not a claim of model correctness.
        results.sort(key=lambda c: (c.distance if c.distance is not None else 10,
            0 if c.doi else 1, -int(c.year) if c.year.isdigit() else 0, c.cod_id))
        if len(results) > limit:
            self.last_notice += f" Showing the best {limit} of {len(results)} returned entries. Narrow the search to inspect others."
        return results[:limit]

    def download(self, candidate: CODCandidate) -> tuple[Path, dict]:
        if not re.fullmatch(r"\d{7}", candidate.cod_id):
            raise ValueError("Invalid COD ID.")
        path = self.cache_dir / f"{candidate.cod_id}.cif"
        metadata_path = path.with_suffix(".source.json")
        self.last_notice = ""
        try:
            content = self._get(f"{candidate.cod_id}.cif", maximum_bytes=10 * 1024**2)
            if b"data_" not in content or b"<html" in content[:1000].lower():
                raise ValueError("COD returned a non-CIF document.")
            from .structures import inspect_cif
            # Validate before accepting a cache write.
            inspect_cif(content.decode("utf-8-sig"), text=True)
            path.write_bytes(content)
            metadata = asdict(candidate) | {"source_url": candidate.source_url,
                "download_url": f"{COD_BASE}/{candidate.cod_id}.cif",
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(content).hexdigest()}
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        except ConnectionError:
            if not path.is_file() or not metadata_path.is_file():
                raise
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if hashlib.sha256(path.read_bytes()).hexdigest() != metadata.get("sha256"):
                raise ValueError("Cached CIF checksum mismatch; remove the cache entry and download again.")
            self.last_notice = f"Offline cached CIF from {metadata.get('retrieved_utc', 'unknown date')}."
        return path, metadata

