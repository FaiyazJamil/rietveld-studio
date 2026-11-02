# Rietveld Studio

**Author and maintainer: Md Faiyaz Jamil**  
Department of Mechanical and Aerospace Engineering, The Ohio State University.

**Public-release package 0.2.1 — MIT open source.** For GitHub upload, Zenodo DOI
registration, citation metadata, and Google Scholar instructions, start with
[PUBLISH_ON_GITHUB_ZENODO.md](PUBLISH_ON_GITHUB_ZENODO.md). This is a packaging
and attribution update; the numerical refinement algorithm is unchanged from
0.2.0. DOI, repository URL, and ORCID fields remain unset until real identifiers
are supplied. See [AUTHORS.md](AUTHORS.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Cite this software

<!-- BEGIN GENERATED CITATION -->
Jamil, Md Faiyaz. (2026). Rietveld Studio: A Python GUI for reproducible powder X-ray Rietveld refinement with GSAS-II (Version 0.2.1) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.23877058

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23877059.svg)](https://doi.org/10.5281/zenodo.23877059)

Use [CITATION.cff](CITATION.cff), [BibTeX](CITATION.bib), or [the citation instructions](CITATION.md). The badge, when present, links to all versions; the citation identifies this version.
<!-- END GENERATED CITATION -->

Please also cite **GSAS-II**, the numerical engine, and the actual structure
publication(s) used for your CIF models. Scholarly citation is requested; it is
not an extra condition of the MIT license. See [docs/REFERENCES.bib](docs/REFERENCES.bib).

**Version 0.2:** repeated convergence checks, independent starting trials, convergence plots, continuation from a refined result, descriptive-weight labels, and a correction that preserves nonpositive observations/declared weights through GSAS-II import. See [UPGRADE_TO_0_2.md](UPGRADE_TO_0_2.md) before repeating a background-subtracted fit.

A guided Python desktop workspace for **constant-wavelength powder X-ray Rietveld refinement**. Numerical least squares, crystallographic symmetry, structure factors, reflection intensities, and covariance are computed by **GSAS-II**, not an independently improvised peak-fitting algorithm.

Read [START_HERE.md](START_HERE.md) for installation and the first run.

## What the application does

- Searches the **Crystallography Open Database (COD)** from a chemical formula, selected battery-material aliases, compound/mineral name, or COD ID.
- Ranks formula-search results by normalized composition distance, with publication/DOI metadata as tie-breakers. The actual structures are never automatically selected or substituted.
- Displays candidate formulas, space groups, lattice parameters, publication year, and DOI/name. You review CIF blocks, lattice dimensions, atomic sites, and occupancies before confirming each phase.
- Accepts local single- or multiblock CIFs. Selected blocks are archived exactly as used. Supports more than one confirmed phase.
- Imports XY/XYE, comma/tab/space/semicolon-delimited numeric text, and single-scan XRDML with counts or CPS counting times.
- Previews the unchanged experimental data and calculated starting-CIF Bragg sticks.
- Accepts an actual GSAS-II instrument file or a user-entered constant-wavelength PXC profile, geometry, radius, polarization, and optional Kα doublet.
- Refines background/scale, cell, profile, optional position correction, calibrated sample broadening, preferred orientation, and selected atomic properties in repeated stages. Each stage checks objective stability and parameter shifts; independent starts explore bounded cell alignment and initial widths.
- Saves accepted-stage checkpoints, rolls failed/nonphysical stages back, and retains a full numerical log and settings.
- Reports independently checked **Rp, Rwp, Rexp, reduced χ², GOF, weighted SSE, degrees of freedom, and Durbin–Watson residual diagnostic**.
- Exports lattice parameters and model-conditional standard uncertainties, cell volume, density, relative crystalline weight fractions and uncertainties, atomic coordinates/ADPs, sample size/strain when enabled, parameter covariance and strong correlations, and per-phase GSAS-II R_F/R_F² values.
- Calculates reflection hkl/d/2θ from the confirmed structures. Associates observed maxima with these reflections, preserving source COD URLs and DOIs. Overlaps stay ambiguous; unmodeled peaks stay unassigned.
- Creates scientific refinement plots with observed/calculated/background/difference curves, phase ticks, hkl annotations, residuals, and fit statistics.
- Creates a native **editable Origin `.opju`** through Origin's official Windows automation API when licensed Origin is installed.

## Supported scope

This release supports **one constant-wavelength X-ray powder pattern per project**, with one or more nonmagnetic, nonmodulated inorganic/small-molecule phases. Each project/run has independent inputs and outputs. Cu/Co/Mo wavelength presets are conveniences; confirm your actual radiation setup.

Not implemented in this GUI: neutron/TOF/energy-dispersive data, magnetic/superspace structures, area-detector integration, batch/sequential refinements, arbitrary constraints/restraints editors, texture spherical harmonics, automatic occupancy refinement, complex anisotropic size/strain models, microabsorption correction, amorphous quantification with an internal standard, quantitative phase identification from unknown peaks, or instrument-standard calibration itself. The exported `.gpx` allows further work in the full GSAS-II GUI.

Binary vendor formats such as RAW/BRML/RASX/NXS must first be exported to numeric XY/XYE. Input X must be **2θ in degrees**, strictly increasing, with no duplicate positions. Decimal points are required. No smoothing, background subtraction, interpolation, or peak stripping is applied to fitting data.

## Installation

Python **3.11** is the recommended target for the supplied Windows/Linux/macOS scripts. Python 3.12/3.13 are supported by the engine bootstrap if matching official binaries are available. The app itself is installable with:

```bash
python -m pip install -e .
```

On Windows, add the Origin integration with:

```powershell
python -m pip install -e '.[origin]'
```

GSAS-II is deliberately not a PyPI dependency; the official source/binaries are installed separately:

```bash
python -m pip install -r requirements-engine.txt
python scripts/bootstrap_engine.py
```

The bootstrap uses the tested GSAS-II source commit `eca9e6be4f33e0633676c6051939f5cc2d477107` and official AdvancedPhotonSource binary releases. The chosen source, binary URL, NumPy/Python versions, and archive SHA256 are recorded in the engine installation. Dependencies retain their own licenses. Origin itself is not downloaded or bundled.

For a normal pre-existing GSAS-II installation, you can select its separate Python executable and source folder in the GUI. The worker loads the application source via PYTHONPATH, so that interpreter also needs the application's non-GUI numerical/reporting dependencies. The simplest setup is the shared environment created by the supplied scripts.

## Launch and CLI

```bash
python -m rietveld_studio
python -m rietveld_studio --project /path/to/project.rsv.json
python -m rietveld_studio --results /path/to/result_folder
python -m rietveld_studio --doctor --gsas-path /path/to/GSAS-II
python -m rietveld_studio --refine /path/to/project.rsv.json
python -m rietveld_studio --origin /path/to/result_folder
```

The installed console command is `rietveld-studio`. `GSASII_PATH` can point to either the GSAS-II repository root or its GSASII subdirectory. The GUI remembers the selected engine interpreter/source and output root. Saved project input paths are relative where possible.

## Workflow and defensible defaults

1. Confirm your **chemical/structural phase model**. Formula matches alone do not establish polymorph, synthesis product, symmetry, site occupancy, or oxidation state. Multiple CIFs may describe differing temperatures or experimental conditions.
2. Provide **raw powder counts and their uncertainties**. Poisson estimates use σ = √max(I,1). CPS XRDML uses σ = √max(CPS·t,1)/t. Processed/normalized data should include measured σ; explicitly selected constant weights give descriptive statistics.
3. Confirm **actual radiation and geometry**. A loaded `.instprm` controls the numerical radiation/profile. Geometry/radius are declared separately. A profile is treated as calibrated only when you explicitly declare that it was calibrated.
4. The first phase scale is held, the histogram scale is refined, and additional phase scales are refined. This avoids the global-scale/phase-scale degeneracy. GSAS-II's own scale convention and covariance propagation determine relative crystalline mass fractions.
5. Background and cell/profile variables are released progressively. A user selects **one** position correction (none, zero, or Bragg–Brentano sample height); the GUI never refines zero and sample height simultaneously.
6. Choose an effective instrumental profile fit **or** fixed calibrated instrument plus sample size/strain. The app prevents simultaneous free instrument and sample broadening refinement. Size is coherent diffraction-domain size, not necessarily particle size.
7. Atomic coordinates and isotropic displacement refinements are opt-in. Site fractions/occupancies remain fixed; there is no generic occupancy-fitting shortcut that can silently invent Li vacancies or dopant-site assignments.
8. Stages with invalid cell/ADP/scale/broadening or an Rwp increase of more than 2% relative to the preceding stage are rejected and restored from a checkpoint. This is a numerical guard, not proof that the selected model is scientifically correct. Nonconvergence, singularity messages, correlations, and unmatched peaks are reported for review.

## Output folder

| File | Contents |
| --- | --- |
| `report.html` | Readable report with fit plot, lattice/phase/atomic results, diagnostics, peak associations, sources, and methods |
| `refinement.png`, `.svg`, `.pdf` | 300 dpi raster and vector scientific plots |
| `refinement_tables.xlsx` | All output tables in separate worksheets |
| `profile.csv`, `profile.npz` | Full grid: observed, calculated, background, difference, sigma, weights, inclusion mask |
| `lattice_parameters.csv` | a/b/c/α/β/γ/V with model-conditional standard uncertainties and units |
| `phase_results.csv` | Density, relative crystalline mass fractions, broadening, optional texture, phase R factors |
| `atoms.csv`, `parameters.csv` | Atomic model, available coordinate/Uiso uncertainties, refined variables and uncertainties, solver shifts |
| `reflections.csv` | Calculated hkl, d, 2θ, F², intensity, radiation component, COD/source/DOI |
| `peak_associations.csv` | Observed maxima, all within-tolerance assignments, ambiguity and unassigned peaks |
| `statistics.csv`, `correlations.csv` | Fit metrics and parameter pairs with \|correlation\| ≥ 0.90 |
| `instrument_parameters.csv`, `model_settings.csv` | Actual radiation/profile values, geometry, radius, background, range, exclusions and weighting |
| `covariance.npz` | Full covariance/correlation matrices and variable names; no Python pickle required |
| `provenance.csv`, `diagnostics.csv` | Sources/checksums and scientific diagnostic messages |
| `stage_history.csv`, `.json` | Accepted/rejected refinement stages and Rwp progression |
| `iteration_history.csv`, `.json`, `trial_history.csv`, `.json` | Every recorded refinement pass, independent starts, shifts and selected result |
| `convergence.png`, `.svg`, `convergence.csv` | Rwp history and the requested convergence criteria/stopping reason |
| `fit_diagnostics.csv`, `strong_peak_comparisons.csv` | Residual RMSE, baseline-noise diagnostic, strong-peak offsets and width comparisons |
| `refined_instrument.instprm` | Actual fitted effective instrument parameters for continuing a run |
| `refined_*.cif` | GSAS-II-exported refined crystal structure(s) |
| `refinement.gpx`, `refinement.lst`, `engine.log` | Full GSAS-II project, numerical listing, and complete worker log |
| `inputs/`, `trials/*/checkpoints/` | Original/normalized powder data, used CIF blocks, instrument parameters, per-trial stage checkpoints |
| `project.rsv.json` | Archived portable project referencing the actual used input files |
| `export_to_origin.py`, `OPEN_IN_ORIGIN.txt` | Standalone native Origin exporter and instructions |
| `refinement.opju` | Created only by the optional licensed Windows Origin export |

The observed minus calculated difference is preserved without a display offset in CSV/NPZ; offset curves in plots are for readability. The inclusion mask defines which observations enter statistics. CIF/COD text is escaped in HTML and protected against spreadsheet-formula interpretation in exported tables.

## Peak identification and online references

COD provides openly accessible structural models and their associated publications. This app preserves those sources and calculates reflections from the **user-confirmed structural model and refined lattice**. It compares calculated positions with raw observed local maxima using the selected angular tolerance. A peak can have multiple plausible contributing reflections and multiple phases; all matches are retained.

This is **model-based reflection association**, not an independent search-match/unknown-phase-identification engine. ICDD/JCPDS card numbers or intensities are not invented or scraped; those databases require separate access/licensing. Reflections from a local CIF have local provenance unless you supply an appropriate online source. Unassigned observed peaks are flagged rather than assigned a speculative chemistry.

For Kα doublets, GSAS-II performs the actual profile calculation. Exported Kα2 stick positions are obtained from the Bragg-law shift plus the corresponding Kα1 position correction; their table/stick intensities use the doublet ratio as an approximation. The actual fitted full profile remains GSAS-II's result.

## Origin project details

Requires licensed Origin 2021+ on Windows and `originpro` in the Python interpreter used for export. The app uses its GUI Python for Origin export, even when the refinement runs in another interpreter. The native project contains editable data-backed observed/calculated/background/difference plots, phase Bragg ticks, a standardized-residual graph, and structural/fit/source tables.

The exporter creates its own `OriginExt.Application()` instance through `originpro`; it never attaches to a user's open session or calls a project-reset command. It refuses to overwrite an existing OPJU filename. Source worksheets preserve hkl and phase/source information for further labeling/customization in Origin. Third-party graph templates, COM registration, and Origin version differences may require local adjustment; native COM execution could not be tested in the Linux development environment.

## Tests and example

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
# Include the actual numerical integration tests:
GSASII_PATH=/path/to/GSAS-II python -m pytest -q
```

For Windows PowerShell:

```powershell
$env:GSASII_PATH = (Resolve-Path .engine/GSAS-II).Path
.venv\Scripts\python.exe -m pytest -q
```

Unit tests cover composition parsing/ranking, COD query/filter/cache behavior, powder uncertainties, malformed data, exclusions, R-factor definitions, correlation handling, systematic absences, and project portability. Integration tests use the **actual GSAS-II engine**, including a known-cell NaCl pattern, a doublet/two-phase mixture, calibrated sample broadening, and artifact exports. GUI smoke checks render the interface without a display.

Regenerate the deterministic synthetic example with:

```bash
python scripts/generate_demo.py --destination examples/synthetic_nacl --gsas-path .engine/GSAS-II
```

Every included simulated pattern is explicitly marked **SYNTHETIC**. See [docs/VALIDATION.md](docs/VALIDATION.md) for actual checks performed and limits.

Version 0.2 has **48 passing tests**, including preservation of negative/zero observations through the real engine and a deliberately difficult starting-cell recovery. The unchanged observations/declared weights are restored immediately after the generic XYE reader, which otherwise suppresses nonpositive values. Old processed-data results should be rerun with the correction; a numerically lower R factor is not guaranteed or required by this correction.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| GSAS-II import or compiled-module check fails | Run the bootstrap in the selected engine Python; use the tested Python/NumPy versions and correct CPU architecture |
| An existing separate engine Python is missing pandas/gemmi/etc. | Install this application's numerical/reporting dependencies in that interpreter or use the supplied shared environment |
| COD timeout/503/429 | Retry later, narrow the search, use cached results, or import a local CIF; network failures are surfaced |
| No chemistry matches | Try the compound/mineral name, a parent formula you explicitly select, relax the exact element set, or upload a CIF |
| Bad numerical row | Check delimiter, skip rows, columns, UTF-8 text encoding, and decimal points; data rows are never silently dropped |
| Duplicate or decreasing 2θ | Export a single scan; sorting is opt-in, duplicates are rejected |
| Wrong peak positions | Verify 2θ units, wavelength/doublet treatment, CIF polymorph/setting, calibration and sample height |
| Stage rejected | Inspect the log, check model/geometry/profile/data, and simplify the recipe; the previous accepted model was restored |
| Excellent Rwp but suspicious structural result | Review correlations, uncertainties, peak associations, chemistry, background and calibration; do not use Rwp alone |
| Origin export fails | Check Windows, Origin license/COM registration, and `originpro` in the export interpreter; the complete non-Origin results remain available |
| Linux Qt launch fails | Install your distribution's Qt/XCB runtime libraries or use a supported desktop environment; headless CLI refinement does not need Qt |

## Scientific references

- B. H. Toby & R. B. Von Dreele, **GSAS-II: the genesis of a modern open-source all purpose crystallography software package**, J. Appl. Cryst. 46 (2013), 529–531. [DOI](https://doi.org/10.1107/S0021889813003531).
- [Official GSAS-II scripting API](https://gsas-ii.readthedocs.io/en/latest/GSASIIscriptable.html).
- [Official GSAS-II installation guidance](https://advancedphotonsource.github.io/GSAS-II-tutorials/install-pip.html).
- [COD REST API](https://wiki.crystallography.net/RESTful_API/) and the individual selected structure/publication.
- [OriginLab Python automation documentation](https://docs.originlab.com/python/).

The application code is MIT-licensed; see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). GSAS-II, Qt/PySide6, COD datasets, Origin/OriginPro, and all dependencies retain their respective licenses. Scientific results require assessment of the actual model, uncertainties, and experimental conditions.

