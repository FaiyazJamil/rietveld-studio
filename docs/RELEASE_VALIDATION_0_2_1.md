# Release preparation validation — 0.2.1

Prepared on 2026-11-02 for Md Faiyaz Jamil. This is a local packaging/citation
validation record, not a claim that GitHub or Zenodo publication has occurred.

| Check | Result |
| --- | --- |
| Full application suite, including the real GSAS-II engine | **55 passed** on Python 3.12.14/Linux |
| Release-identity tests after final helper edits | **7 passed** |
| CITATION.cff schema validation | Passed CFF 1.2.0 validation using cffconvert 2.0.0 |
| Metadata synchronization | Passed `python scripts/prepare_release.py --check` |
| Python lint | Passed `python -m ruff check src scripts tests` |
| Source and wheel distributions | Built successfully and passed `twine check` |

The numerical integration checks use the separately installed GSAS-II source
commit `eca9e6be4f33e0633676c6051939f5cc2d477107` and matching official Linux
compiled modules. The 0.2.1 update changes attribution and release packaging;
the refinement algorithm is unchanged from 0.2.0. Synthetic result files retain
their original application version and generating provenance.

The test run emitted Matplotlib/Qt deprecation warnings about a high-DPI
attribute. They did not fail the GUI or numerical tests. Native Origin COM
automation was not executable on this Linux environment. The GitHub CI workflow
is supplied but has not been run in the user's repository; it intentionally
does not claim GSAS-II/Origin integration coverage.

The release helper was checked for stale citation detection, rejection of
placeholder/sandbox identifiers and invalid ORCID checksums, clearing a prior
version DOI when a new version is prepared, preserving the concept DOI, and
avoiding attachment of the current DOI to an older result version.

No real GitHub repository URL, ORCID, version DOI, or concept DOI has been
supplied for this release preparation, so those metadata fields remain empty.
The maintainer must set the actual repository/date, publish the release, and
then add its assigned DOI following PUBLISH_ON_GITHUB_ZENODO.md.
