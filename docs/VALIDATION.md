# Version 0.2 validation

The complete automated suite passed **48 tests** on Linux x86_64, Python 3.12.14, using the real GSAS-II revision 5846 and official compiled profile/symmetry modules. NumPy 2.3.5, SciPy 1.17.0, Gemmi 0.7.5, PySide6 6.12.0 and PyCifRW 5.0.1 were used. The preserved [version 0.1 validation](VALIDATION_v0_1.md) describes the original release separately.

## Controlled comparison against the original program

Both programs fitted exactly the same synthetic NaCl observations, sigma values, 2theta interval, phase model, radiation and geometry. The simulation used a true lattice parameter of **5.640200 Å**. The starting CIF was deliberately moved to **5.720000 Å** so a narrow starting profile had poor peak overlap.

| Quantity | Original v0.1 | Updated v0.2 |
| --- | ---: | ---: |
| Rp (%) | 17.837882 | 7.927237 |
| Rwp (%) | 31.094278 | 10.201582 |
| Reduced chi-square | 9.602063 | 1.034930 |
| Refined a (Å) | 5.71778254 | 5.64015096 |

The original program remained near a wrong local solution. Repeating the original start alone also remained there; the bounded CIF-derived alignment start recovered the correct cell. The selected updated result met the configured convergence checks, with maximum final-cycle shift/su about **0.0177**. Three independent starts and 43 completed refinement calls were recorded.

This is a synthetic robustness demonstration, not a promise that this Rwp will be obtained for a real cathode sample. The algorithm does not establish a global minimum or verify that a user-selected chemical structure is correct.

## Actual uploaded XY import audit

The actual two-column file with an initial comment header was loaded through the real GSAS-II reader. It contained **2316 observations**, including **766 negative values** and two zeros.

| Check | Original generic-reader path | Updated adapter |
| --- | ---: | ---: |
| Negative observations retained | 0 | 766 |
| Positive fitting weights | 1548 | 2316 |

After a GPX save/reload, every intensity and every declared weight matched the validated original input exactly. The original experimental file has not been added to this software distribution. This was an import audit, not a refinement of the actual sample: its confirmed CIF and full experimental configuration were not supplied.

## Regression coverage

The suite covers the original unit and numerical integration tests plus bounded initial alignment, fixed-zero behavior, invalid optimizer controls, simultaneous objective/shift convergence, invariance of Rp/Rwp under a consistent intensity rescaling, the dependence of constant-weight chi-square on arbitrary units, processed/negative data preservation through actual refinement, background-mode behavior, archived uncertainty provenance and continuation from an exported refined result.

The real-engine tests also exercise two-phase fractions, Kalpha doublets, exclusions, calibrated domain size/microstrain, covariance export, failed-stage rollback and the actual Qt-to-worker-to-results pipeline. A maximum-call stop is distinguished from established convergence.

## Limits

Native Windows Origin COM export and PowerShell execution are not available in the Linux validation environment. Origin export code uses the existing published API and adds the iteration/trial tables and a convergence graph, but still needs local verification in licensed Origin. No measured cathode refinement or materials-specific structural conclusion has been validated from a metrics-only screenshot.

Complete benchmark numbers are in ITERATIVE_VALIDATION.json. Updated synthetic sample results, including iteration/trial histories and convergence plots, are included under examples/synthetic_nacl/refined_run.
