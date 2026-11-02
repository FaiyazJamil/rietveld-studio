# Contributing

Open an issue describing the scientific or usability problem before a large
change. For a refinement issue, include the application/GSAS-II versions,
instrument and weighting settings, stopping reason, relevant engine.log excerpt,
and a small reproducible pattern and CIF when you can share them. Synthetic
examples or public COD entries are useful for reproducibility.

Contributions should preserve measured observations, declared weights, source
provenance, physical parameter constraints, and honest convergence reporting.
A smaller R factor alone is not evidence that a scientific change is correct.

In a private Python environment, install development and release tools:

```bash
python -m pip install -e '.[dev,release]'
python scripts/prepare_release.py --check
cffconvert --validate
python -m ruff check src scripts tests
python -m pytest -q -m 'not integration and not network'
```

Real numerical integration tests also need the separately installed GSAS-II
engine; set GSASII_PATH to its source directory and run the full test suite.
Native Origin automation needs a licensed Windows installation and must be
checked there. Do not report skipped integration/Origin checks as passing.

Submit a focused pull request with the problem, change, scientific rationale,
and validation. Contributions are licensed under this repository's MIT license.
Significant new authorship should be discussed with the maintainer and reflected
consistently in AUTHORS.md and citation metadata when appropriate.
