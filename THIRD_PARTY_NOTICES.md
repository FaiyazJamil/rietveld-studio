# Third-party software, data, and scientific credit

The MIT license in LICENSE covers Rietveld Studio's application code and
documentation. It does not relicense external software, crystal structures,
papers, or user-supplied data. This source distribution does not bundle GSAS-II
source/binaries, the Qt runtime, or Origin/OriginPro. Dependencies are installed
separately and retain their own license notices and conditions.

| Component | Role and attribution |
| --- | --- |
| [GSAS-II](https://github.com/AdvancedPhotonSource/GSAS-II) | Numerical profile calculation, crystallography, least squares, and covariance. Retains the upstream GSAS-II license. Cite Toby and Von Dreele (2013), DOI: [10.1107/S0021889813003531](https://doi.org/10.1107/S0021889813003531). |
| [Crystallography Open Database](https://www.crystallography.net/cod/) | Structural models and source-publication metadata. Retain the source COD identifier/URL and cite the actual structure publication(s). See the COD's own [data policy](https://www.crystallography.net/cod/). General database reference: Gražulis et al. (2009), DOI: [10.1107/S0021889809016690](https://doi.org/10.1107/S0021889809016690). |
| [Qt for Python / PySide6](https://doc.qt.io/qtforpython-6/) | GUI. Qt/PySide6 licensing is separate from this application's MIT license; consult the license files supplied with the installed distribution and [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html). |
| [Origin/OriginPro and originpro](https://docs.originlab.com/python/) | Optional native Origin project automation. Origin/OriginPro is a separate commercial product requiring a license. Neither Origin itself nor a license for it is supplied by this repository. Consult OriginLab's terms for the integration package. |
| NumPy, SciPy, Matplotlib, pandas, Gemmi, Requests, openpyxl, platformdirs | Numerical, structural, plotting, HTTP, workbook, and platform support. Each installed distribution retains its own upstream copyright and license files. |
| PyCifRW, GitPython and engine dependencies | Used by the separately installed GSAS-II engine/bootstrap. Their upstream terms remain applicable. |

Scientific bibliography is provided in [docs/REFERENCES.bib](docs/REFERENCES.bib).
The repository's own citation is in CITATION.cff and CITATION.bib. Please cite
both the application and the scientific engine when describing analyses that
use them; no citation substitutes for acknowledging the actual input structure.

Included NaCl patterns are labeled synthetic. Existing example results retain
the generating application/engine versions in their result.json files; a
documentation release does not relabel old numerical results as newly run.
Experimental data are not included in the public release package.
