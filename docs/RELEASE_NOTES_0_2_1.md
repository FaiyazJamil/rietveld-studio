# Rietveld Studio v0.2.1

**Author and maintainer:** Md Faiyaz Jamil  
**License:** MIT

Rietveld Studio is a Python desktop GUI for constant-wavelength powder X-ray
Rietveld refinement using GSAS-II. It supports COD structure search with user
confirmation, local CIFs, powder-data validation, iterative staged refinement
with independent starts, convergence/residual diagnostics, structural and
profile exports, and optional native Origin project export on Windows.

This release adds public-repository packaging, author attribution, software
citation metadata, Zenodo metadata, and a full GitHub/Zenodo/Google Scholar
publication guide. The numerical refinement algorithm is unchanged from 0.2.0.

See START_HERE.md for installation and PUBLISH_ON_GITHUB_ZENODO.md for publication.
Use CITATION.cff, CITATION.bib or the Zenodo record to cite this application.
Please also cite GSAS-II and the publications for the structures used.

Python 3.11 is recommended for the supplied installers. GSAS-II is installed
separately by the supplied bootstrap. Native Origin export requires licensed
Origin on Windows. Constant-weight chi-squared values are descriptive; review
the actual residuals, parameter plausibility and uncertainty model.
