# Changelog

## 0.2.1 — prepared 2026-11-02

Public-release packaging and citation update. The numerical refinement algorithm
is unchanged from 0.2.0.

- Name Md Faiyaz Jamil as project author and maintainer in package metadata,
  citation files, the About dialog, and newly generated reports.
- Retain MIT licensing and existing notices, with explicit third-party credit.
- Add synchronized CITATION.cff, BibTeX, human-readable citation, and Zenodo
  software metadata. No DOI, ORCID, or GitHub account is invented.
- Add release-metadata tooling, metadata checks, source/wheel packaging support,
  GitHub CI, contribution guidance, and GitHub/Zenodo/Google Scholar instructions.
- Keep the existing synthetic numerical examples and their original provenance.

The release date is a preparation date until a release is actually published.
Set the actual date with scripts/prepare_release.py before creating a tag.

## 0.2.0 — iterative refinement update

- Preserve zero/negative observations and declared weights after GSAS-II import.
- Add bounded independent starts, repeated staged refinement, convergence checks,
  checkpoints, diagnostics, and continuation from exported refined parameters.
- Add iteration/convergence exports and explicit descriptive-weight labels.

## 0.1.0 — initial application

Guided CIF selection, COD search, powder-data validation, GSAS-II refinement,
structural/profile reports, and optional native Origin export.
