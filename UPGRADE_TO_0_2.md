# Upgrade to Rietveld Studio 0.2

## Install the updated code

Close the application, then extract the updated ZIP into your existing program folder. Keep your `.venv-rietveld`, `.venv`, `.engine`, and experimental result folders; these are not replaced by the archive.

From PowerShell inside the extracted `rietveld-studio` folder, use the environment you created earlier:

```powershell
.\.venv-rietveld\Scripts\python.exe -m pip install -e ".[origin]"
.\.venv-rietveld\Scripts\python.exe -m rietveld_studio
```

If your environment is named `.venv`, substitute `.venv` in those commands. The updated `launch_windows.bat` recognizes both names. Native Origin export still needs licensed Origin on Windows.

If you are installing into a new folder, follow START_HERE.md. A manual isolated Python 3.13 setup remains supported by the engine bootstrap; the original automatic installer targets Python 3.11.

## Important import correction

The original adapter used the GSAS-II generic XYE reader directly. That reader zeros nonpositive intensities and their weights, even when the XYE file includes positive supplied sigma values. This behavior is unsuitable for retaining a background-subtracted pattern.

Version 0.2 restores the exact validated observations and weights after import and before any calculation. Legitimate zero counts and negative/background-subtracted observations now enter the requested fit mask. The final arrays and weights are checked for preservation in regression tests.

For the provided background-subtracted XY file, an import audit found:

| Check | Original reader path | Corrected adapter |
| --- | ---: | ---: |
| Total rows in source | 2,316 | 2,316 |
| Negative intensities retained | 0 | 766 |
| Positive fitting weights | 1,548 | 2,316 |

The correction changes the fitted observations and degrees of freedom compared with an old run. Old and new R factors are therefore not directly comparable for a scan containing nonpositive intensities. The correction can raise or lower reported R factors; it is necessary for a faithful fit.

## Iterative fitting

The default optimizer uses three independent starts and up to six GSAS-II calls per stage, with up to twelve internal cycles per call. It keeps the confirmed chemistry, measurement data, declared weights, fit interval and exclusions fixed across all starts.

Initial starts include the original cell and bounded CIF-derived peak-alignment/profile-width alternatives. Position offsets are searched only when the user has enabled instrument-zero refinement. Fixed/calibrated profiles are not broadened as a starting-search shortcut. A common cell-scale search is used only when all included phase cells are allowed to vary.

Each stage stops when the relative change in Rwp is below the selected tolerance **and** maximum final-cycle shift/standard-uncertainty is below its threshold for the requested number of successive calls. Defaults are relative Rwp change `0.0001`, shift/su `0.10`, and two stable calls. Small Rwp improvement without small parameter shifts is not declared convergence. Stage failures/nonphysical parameters are rolled back, and the best valid completed starting trial is retained.

The result contains `iteration_history.csv`, `trial_history.csv`, a convergence plot, parameter shifts, the selected trial and stopping reason. A convergence limit is reported honestly instead of presenting a completed run as necessarily converged.

## Background-subtracted scans

For your two-column background-subtracted XY file, use:

| Input | Setting |
| --- | --- |
| X/intensity columns | 1 / 2 |
| Delimiter | Auto or whitespace |
| Header rows | Auto or skip 1 |
| Weighting when no experimental sigma is available | Constant sigma, descriptive |
| Background treatment | Background already subtracted |

The selected background-subtracted mode fits at most three low-order residual-background coefficients. It does not clip negative observations, smooth fitting data, add an intensity offset, change weights, exclude troublesome peaks, change the confirmed phase chemistry, or change the radiation to obtain a smaller R factor.

With constant sigma, Rexp, reduced χ² and GOF depend on the arbitrary sigma and intensity units. Values near one are not a statistical quality certificate. The GUI/report labels these values as descriptive and reports residual RMSE in the input intensity units. For physically interpretable uncertainty statistics, use raw counts or properly propagated experimental sigma.

## Continue from a result

Use **Continue from this result** on the Results page to prepare a new run from the exported refined CIF(s), fitted effective instrument profile, and available sample broadening parameters. This creates a new output folder and preserves the previous run. Constant-weight provenance is retained, including when opening an older result whose archived XYE file had been labeled as supplied sigma.

This is continuation from the exported structural/profile parameters, not a full arbitrary-GSAS-II constraint/session editor. Occupancies remain fixed, and the instrument calibration declaration is not changed simply because an effective profile was fitted.

## What can still keep R factors high

Further cycles cannot establish the correct model when the CIF, radiation/doublet treatment, calibration, or modeled phase mixture is wrong. Unmodeled impurities, preferred orientation, anisotropic broadening, site chemistry and preprocessing correlations can remain important. Review the entire fit and difference plot, residual diagnostics, source CIF and actual instrument settings.

Useful references: [IUCr Rietveld guidelines](https://journals.iucr.org/j/issues/1999/01/00/gl0561/), [GSAS-II scripting](https://gsas-ii.readthedocs.io/en/latest/GSASIIscriptable.html), and [International Tables: Rietveld refinement](https://onlinelibrary.wiley.com/iucr/itc/Ha/ch4o7v0001/).

