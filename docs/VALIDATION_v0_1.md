# Version 0.1 validation (historical)

This release was developed and checked on **Linux x86_64, Python 3.12.14**, with the actual GSAS-II numerical modules loaded. The checks below describe what was exercised; they do not establish general scientific validity for arbitrary experimental data.

## Tested engine and dependencies

- GSAS-II source: `eca9e6be4f33e0633676c6051939f5cc2d477107`, revision 5846.
- Official compiled modules: `linux_64_p3.12_n2.2` from AdvancedPhotonSource's GSAS-II-buildtools release v1.0.1.
- NumPy 2.3.5; SciPy 1.17.0; pandas 2.2.3; Matplotlib 3.10.8.
- PySide6 6.12.0; Gemmi 0.7.5; PyCifRW 5.0.1; openpyxl 3.1.5.
- The provided setup scripts select **Python 3.11 / NumPy 2.2.6** as a conservative local installation target supported by official binaries. That separate Windows environment was not executed here.

The bootstrap installer was tested independently by downloading the pinned official source archive and matching compiled modules into a fresh directory, then successfully running the engine doctor. A full numerical run was also performed using that fresh bootstrap installation.

## Numerical recovery tests

### Single-phase known-cell recovery

GSAS-II generated a forward-model NaCl pattern with Poisson counting noise. Starting a differs deliberately from the simulation truth.

| Quantity | Value |
| --- | --- |
| True a | 5.640200 Å |
| Starting a | 5.650000 Å |
| Recovered a | 5.640151 Å |
| Standard uncertainty of a | 0.000043 Å |
| Recovered cell volume | 179.420591 Å³ |
| Number of observations | 3,801 |
| Number of refined independent variables | 10 |
| Rp | 7.927498% |
| Rwp | 10.201637% |
| Rexp | 10.027946% |
| Reduced χ² | 1.034941 |
| GOF | 1.017321 |
| Durbin–Watson | 2.000882 |

The app's independently recomputed Rwp agrees with GSAS-II's weighted profile factor. The recovered cell lies within the test's stated tolerance and within five reported standard uncertainties of the known value. These numerical values are from synthetic data, not a measured sample.

### Doublet and two-phase mixture

A separate synthetic NaCl/KCl mixture exercised Cu Kα1/Kα2 radiation, two linked phases, global/relative phase scales, relative crystalline mass fractions and propagated uncertainties, optional zero correction, two independently refined cubic cells, a limited fit interval, and an excluded interval.

Checks required recovery of the known phase fraction within 2.5 absolute percentage points, a KCl cell within 0.001 Å, a unit sum of mass fractions, a nonempty fraction uncertainty, both radiation components in the reflection list, the exact number of included observations after range/exclusions, and reduced χ² below 1.4.

### Calibrated sample broadening

A high-count synthetic pattern with a fixed known instrumental profile exercised isotropic domain size and microstrain. The test required recovery of the true **0.080 µm** size within 15% and true **250 ppm** microstrain within 20%, a positive microstrain standard uncertainty, agreement with truth within four standard uncertainties, and reduced χ² below 1.4.

An exploratory lower-count version demonstrated the intended uncertainty behavior: it gave size ≈0.0796 µm and strain ≈185 ±84 ppm, with a size/strain correlation ≈0.94. The correct microstrain was compatible with its broad uncertainty; a visually good fit did not make strain precisely determined. The application exports these uncertainties and flags strong correlations.

### Rollback and actual GUI worker

An injected failure deliberately corrupted a candidate stage's cell before raising an exception. The real refinement workflow restored the previous accepted checkpoint, completed later stages, recovered the correct lattice, and recorded the rejected stage and reason.

The actual Qt interface was also driven through loading a project, asynchronously validating the powder data, checking the engine via QProcess, launching a real refinement worker, reading its progress/log stream, loading its results and updating plots/tables/statistics. All six workflow pages were rendered with Qt's offscreen platform.

## Automated suite

**34 tests passed** with GSASII_PATH set. The suite covers:

- Formula parsing, aliases, nested groups/hydrates, invalid syntax, Hill notation, composition ranking.
- Correct COD element filters and explicit cached-search fallback behavior.
- Supplied sigma preservation, counting/CPS uncertainty propagation, negative/invalid/duplicate data handling.
- Fit-range/exclusion masks, R-factor/χ² identities, covariance-to-correlation conversion, unassigned and overlapping peak handling.
- CIF inspection, selected blocks, F-centered systematic absences, JSON validity, portable project paths.
- Known-cell numerical recovery, doublet/multiphase fitting, calibrated size/strain, failed-stage recovery.
- Native GSAS-II model/refined CIF exports, plots, XLSX/CSV tables, report, covariance and portable archived project.
- Qt page rendering, project settings, and the real GUI-to-worker-to-results path.

Static code checks and Python compilation also passed. The application was successfully installed in editable mode from its own pyproject configuration.

## Online behavior

A live `LiFePO4` COD search returned **19 candidate structures** spanning different compositions/settings/publications. CIF retrieval and Gemmi validation were exercised on a returned COD entry. Later requests for some different COD entries encountered server timeouts/503 responses; the app reports failures and provides local-CIF/cache alternatives. Continuous COD availability is not guaranteed.

## Not executed in this environment

- Native **Origin/OriginPro COM automation and `.opju` creation**: requires Windows with a licensed Origin installation. The exporter uses the published originpro API and was checked against OriginLab's Python package source/documentation, but its COM calls and graph appearance need local verification.
- The PowerShell/Windows launcher and macOS GUI/runtime dependencies.
- Real laboratory powder measurements, instrument calibration, phase-identification benchmarking against independent standards, and materials-specific constrained atom/occupancy models.

The program is a tested initial **source release**. Review the residuals, experimental configuration, scientific diagnostics and model assumptions before relying on any automatic refinement result.

