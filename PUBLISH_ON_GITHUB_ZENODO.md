# Publish Rietveld Studio on GitHub, Zenodo, and Google Scholar

Prepared for **Md Faiyaz Jamil**, Department of Mechanical and Aerospace
Engineering, The Ohio State University. Instructions checked against official
GitHub, Zenodo, and Google Scholar documentation on **2026-11-02**.

This package prepares **version 0.2.1**. It has not been uploaded to your GitHub
account or published on Zenodo by this preparation step. It contains no invented
DOI, ORCID, or GitHub account name. The preparation date must be changed to the
actual release date if you publish on another day.

## What is included

| File | Purpose |
| --- | --- |
| `LICENSE` | MIT open-source license with your name and the retained existing notice |
| `AUTHORS.md` | Your authorship, affiliation, and the scope of the application's credit |
| `CITATION.cff` | Machine-readable software citation; GitHub uses it for “Cite this repository” |
| `CITATION.bib` / `CITATION.md` | BibTeX and readable citation, updated after a real DOI is available |
| `.zenodo.json` | Zenodo software record metadata naming you as creator |
| `release-metadata.json` | Local source of truth for author, version, date, repository and DOI fields |
| `scripts/prepare_release.py` | Synchronizes citation, Zenodo, package and runtime metadata; does not publish anything |
| `THIRD_PARTY_NOTICES.md` / `docs/REFERENCES.bib` | GSAS-II, COD, method and dependency credit |
| `.gitignore`, `MANIFEST.in`, `.github/workflows/ci.yml` | Repository hygiene, package inclusion, metadata/build/unit checks |
| `docs/RELEASE_NOTES_0_2_1.md` | Release description to paste into GitHub |

GitHub reads CITATION.cff. When both CITATION.cff and .zenodo.json exist,
**Zenodo uses .zenodo.json**. Keep the two synchronized with the supplied script.
MIT allows reuse, modification and redistribution subject to its notice
requirements. Scholarly citation is requested; no additional citation-only
restriction is added to MIT. Third-party products retain their own licenses.

## 1. Extract the package and identify the repository root

Extract `Rietveld_Studio.zip`. Open the inner **rietveld-studio** folder.
The correct repository root contains `README.md`, `LICENSE`, `CITATION.cff`,
`.zenodo.json`, `pyproject.toml`, `src`, and `scripts` directly beside each other.

Upload/commit those extracted files, including the dotfiles. Uploading only the
ZIP to GitHub does not expose the source tree or the root citation metadata.
The ZIP can be offered separately as a release asset if desired.

Keep existing virtual environments, `.engine`, personal input data and result
folders outside the files you commit. `.gitignore` excludes common local
environments and outputs. The tracked examples are synthetic. GitHub's website
uploader may not display hidden dotfiles conveniently; Git or GitHub Desktop is
the more reliable route for this package.

## 2. Create or select the GitHub repository

For a new repository, sign in at [GitHub](https://github.com/new), choose a name
such as **rietveld-studio**, set visibility to **Public**, and create it. Leave
the GitHub options to add a README, license and .gitignore unchecked; this
package supplies them. Copy its actual HTTPS URL.

If a repository already exists, clone it or open your existing local checkout.
Copy the updated extracted files into that checkout, preserving its `.git`
history and any unrelated files. Work in that checkout for the following steps.
Do not replace an existing history by creating a second nested repository.

## 3. Set the real repository URL and actual publication date

Open PowerShell in the repository root. The metadata helper needs only Python
3.11–3.13 and the standard library. Replace `YOUR-USERNAME` below with your
actual GitHub owner name and adjust the repository name if needed:

```powershell
python scripts/prepare_release.py --repo-url "https://github.com/YOUR-USERNAME/rietveld-studio" --release-date "2026-11-02"
python scripts/prepare_release.py --check
```

If publishing later, substitute that actual date. With the existing app
environment, you can use `.\.venv-rietveld\Scripts\python.exe` in place of
`python` in every Python command; `.venv` is also supported.

Your citation name is **Md Faiyaz Jamil** (`given-names: Md Faiyaz`,
`family-names: Jamil`). Review the affiliation in `release-metadata.json`.
If you prefer another consistent scholarly name spelling, edit the author
fields there, then rerun the helper. Review AUTHORS.md and LICENSE as well.

If you have an ORCID, add your **actual** identifier:

```powershell
python scripts/prepare_release.py --orcid "YOUR-ACTUAL-ORCID"
```

Omit this command if you do not have an ORCID. The helper checks its checksum.
DOI fields should remain empty before Zenodo assigns the DOI. The GitHub URL
and ORCID placeholders in these instructions are prompts for your own values;
they are not valid metadata and the helper rejects them.

## 4. Install/check the application and release metadata

For an existing installation, reinstall the updated source into your isolated
environment. For a new environment, see START_HERE.md. In that environment:

```powershell
python -m pip install -e ".[dev,release]"
python scripts/prepare_release.py --check
cffconvert --validate
python -m ruff check src scripts tests
python -m pytest -q -m "not integration and not network"
python -m build
python -m twine check dist/*
```

If the environment is not activated, use its full Python path for Python
commands and its `Scripts\cffconvert.exe` for CFF validation. `twine check`
checks package metadata locally; it does not upload to PyPI.

The GitHub CI workflow runs metadata, CFF, lint, unit and package-build checks.
It does **not** install the GSAS-II engine or validate native Origin automation.
To rerun real numerical tests, install/check GSAS-II as in START_HERE.md,
set `$env:GSASII_PATH` to that installation, and run `python -m pytest -q`.
The existing synthetic examples retain their actual original generating version.

## 5. Commit the extracted files and push them to GitHub

Install [Git](https://git-scm.com/downloads) if needed. In a new local source
folder that has no existing Git repository:

```powershell
git init -b main
git config user.name "Md Faiyaz Jamil"
git config user.email "YOUR-VERIFIED-GITHUB-EMAIL"
git add .
git status
git commit -m "Prepare Rietveld Studio 0.2.1 open-source software release"
git remote add origin https://github.com/YOUR-USERNAME/rietveld-studio.git
git push -u origin main
```

Use your GitHub-verified email or GitHub-provided private noreply address.
Authenticate through Git's supported browser/token flow; do not put a token
inside a remote URL or source file. `git status` lets you review what will be
published. Dotfiles are included by `git add .` unless ignored.

For an existing checkout, skip `git init` and `git remote add`; use its existing
branch/remote, then `git add .`, `git commit`, and `git push`. If the remote's
branch has new work, pull and reconcile it normally. No force push is needed.

Alternatively, GitHub Desktop can add/open the local repository, commit the
changes, and publish/push it. Keep the repository public. Confirm on GitHub that
the root files and dotfiles are present, “Cite this repository” appears, the
license is detected as MIT, and Actions completes successfully.

## 6. Connect Zenodo before creating a new GitHub release

For a new Zenodo software record, sign in to production
[Zenodo](https://zenodo.org/) and connect the GitHub account that owns or can
manage this repository. In the Zenodo profile menu, open **GitHub**, click
**Sync now**, find this repository, and enable its slider.

Enable the repository **before** publishing the release. A push or a draft
GitHub release is not the published release event that creates the archive.
Use production Zenodo for the permanent citation; the sandbox is for testing.

If you already have a published **manual Zenodo record for this same software**,
follow the existing-record route in section 10 instead of creating a duplicate
record through automatic integration. An existing unpublished draft can be
completed manually, or left unpublished while you choose the GitHub route;
do not publish the same release twice as unrelated records.

## 7. Publish the GitHub release

Check that the version is `0.2.1` in release-metadata.json, pyproject.toml,
CITATION.cff and .zenodo.json, and that the actual date is correct.

On GitHub, open **Releases → Draft a new release**. Create tag **v0.2.1** from
the checked main-branch commit. Set the release title to **Rietveld Studio
v0.2.1** and paste `docs/RELEASE_NOTES_0_2_1.md` into the description. Publish
a normal release when ready. If `v0.2.1` already exists, prepare the next unused
version rather than overwriting a published tag.

GitHub supplies source ZIP/tar archives automatically. Optionally attach your
locally built wheel/source distribution as convenience files. The archive
contains source code, not a standalone Windows executable or an Origin license.

Wait for processing in Zenodo's GitHub view. If a release fails, inspect its
reported metadata errors there before preparing a corrected new release.

## 8. Inspect the Zenodo record and copy both real DOIs

Open the resulting record. Verify:

- Resource type: **Software**.
- Title matches the software citation.
- Creator: **Jamil, Md Faiyaz**; affiliation and optional ORCID are correct.
- Version: **0.2.1**; publication date is the actual release date.
- License: **MIT License**; access is open.
- Archived files correspond to the release you intended, and the GitHub link is correct.

Zenodo gives the version a DOI and also gives the project an all-versions
**concept DOI**. Copy both from the record's DOI/version information:

| Identifier | Use |
| --- | --- |
| Version DOI | Cite the exact release used in an analysis; put this in CITATION.cff/CITATION.bib |
| Concept DOI | Link to the project across versions; used for the README DOI badge |

They are different identifiers. Do not guess them, append a `.v0.2.1` suffix,
or use the concept DOI as though it identifies a particular archived version.

## 9. Add the assigned DOI to the citations on the main branch

Back in the local checkout, replace the two placeholders below with the actual
DOI strings, or complete https://doi.org/ links, copied from Zenodo:

```powershell
python scripts/prepare_release.py --doi "YOUR-REAL-VERSION-DOI" --concept-doi "YOUR-REAL-CONCEPT-DOI"
python scripts/prepare_release.py --check
cffconvert --validate
git add .
git commit -m "Add assigned Zenodo citation and project DOI"
git push
```

This updates the CFF, BibTeX, readable citation, README badge and runtime citation.
Zenodo's creation metadata deliberately does not repeat an old DOI. Your
main-branch GitHub citation can now point to the archived version. The first
release archive can legitimately lack its own DOI in CITATION.cff because that
DOI was assigned after the archive was created. The Zenodo record itself still
has the complete citation.

Do not delete/recreate the tag just to put the assigned DOI back into that
immutable archive, or publish another release solely to chase this circular
problem. Future numerical changes should receive a new version.

To reproduce the exact scientific software snapshot, use the archived release
for the cited DOI. The later main-branch metadata commit adds citation links;
it does not retroactively change the archived release files.

## 10. Alternative: update an existing manual Zenodo record

If the software already has a published Zenodo record, open that record while
signed in and use **New version**. This preserves its existing version chain
and concept DOI. Prepare the GitHub version/tag as above, download its source
archive, and upload that archive to the new Zenodo version draft. Remove any
carried-over files from the draft that should not be in the new version.

Enter/check the software metadata from .zenodo.json **in the upload form**:
creator, title, description, resource type Software, version, publication date,
MIT license, open access, and repository link. A .zenodo.json inside a manually
uploaded ZIP is not automatically applied to the form. Review and publish the
new version, then follow section 9 with that version's actual DOI and the
existing concept DOI.

Choose one ongoing archival workflow. If you want to migrate an existing manual
version chain to automatic GitHub archiving, consult Zenodo about associating
that chain; entering its concept DOI in this helper does not perform a migration.
Do not enable an independent automatic record for the same release unintentionally.

## 11. Add the software to Google Scholar

A Zenodo DOI makes the software persistently identifiable and citable.
**It does not guarantee automatic Google Scholar indexing or citation counts.**
Google Scholar decides what it indexes. A manual profile entry and an indexed
Scholar search record are different things.

1. Sign in to your Google Scholar profile.
2. Use the **+ / Add** menu and **Add articles** to search for the exact software
   title or DOI, if it has already been indexed.
3. If it is not found, choose **Add article manually**. Select **Other** if the
   form offers it, and identify the work as computer software.
4. Enter the title exactly as in CITATION.cff, author **Md Faiyaz Jamil**, the
   actual publication year, and publisher/repository **Zenodo** where the form
   supports those fields. Use the version DOI URL in an available URL field.
   Do not invent journal volume, issue or page numbers for software.
5. Save and inspect the profile entry. If the form has no DOI/URL field, retain
   the exact title and author metadata so it can be matched; link the Zenodo
   software citation from your research website/CV as well.
6. If an automatically indexed duplicate appears later, use Scholar's **Merge**
   function to combine duplicate profile entries. Avoid separately counting
   minor software releases as multiple unrelated research articles.

The citation should be copied from the final generated CITATION.md or Zenodo's
citation export. Use the DOI of the release actually used in a publication.
Adding an entry manually does not guarantee that references to it will be found
or included in your Scholar metrics.

## 12. Release a future version correctly

For a genuine update, choose the next unused version, for example 0.2.2, and
set its actual date:

```powershell
python scripts/prepare_release.py --version "0.2.2" --release-date "YYYY-MM-DD"
python scripts/prepare_release.py --check
```

Replace YYYY-MM-DD with the actual date. Changing the version automatically
removes the preceding **version DOI** from its citations and retains the
project's concept DOI. Check/retest changes, update the changelog and release
notes, commit/push, and publish tag v0.2.2. The connected Zenodo workflow assigns
the new version DOI; add it afterward using section 9. For a manual record,
use its New version workflow each time instead.

Git commit authorship and software citation authorship are separate metadata.
If future contributors become software coauthors, update author lists
consistently in the release tooling, CFF, Zenodo metadata, AUTHORS.md and related
citations rather than relying on GitHub contributor statistics.

## Official references

- [GitHub: add locally hosted code](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
- [GitHub: CITATION files](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files)
- [GitHub: manage releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [Zenodo: enable a GitHub repository](https://help.zenodo.org/docs/github/enable-repository/)
- [Zenodo: archive a GitHub release](https://help.zenodo.org/docs/github/archive-software/github-upload/)
- [Zenodo: describe software and metadata precedence](https://help.zenodo.org/docs/github/describe-software/)
- [Zenodo: DOI versioning](https://support.zenodo.org/help/en-gb/1-upload-deposit/97-what-is-doi-versioning)
- [Google Scholar: profile help, manual entries and merging](https://scholar.google.com/intl/en/scholar/citations.html)
- [Google Scholar: inclusion guidelines](https://scholar.google.com/intl/en/scholar/inclusion.html)

Service menus can change. The official guides above are the reference for the
current interface. Your actual DOI, repository ownership and publication state
are established by the services, not by the local preparation script.

