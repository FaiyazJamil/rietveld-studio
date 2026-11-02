"""Synchronize release/citation metadata locally; never publish or mint a DOI.

Only the Python standard library is required. Real repository/ORCID/DOI values
must come from the maintainer and the respective services.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEGIN_CITATION = "<!-- BEGIN GENERATED CITATION -->"
END_CITATION = "<!-- END GENERATED CITATION -->"
BEGIN_URLS = "# BEGIN GENERATED PROJECT URLS"
END_URLS = "# END GENERATED PROJECT URLS"


def quoted(value):
    # JSON double-quoted strings are valid YAML scalars and TOML basic strings
    # for the ordinary bibliographic strings written here.
    return json.dumps(value, ensure_ascii=False)


def normalize_doi(value):
    value = value.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    if value and not re.fullmatch(r"10\.5281/zenodo\.[1-9]\d*", value):
        raise ValueError("Use the real production Zenodo DOI, copied from your record (not a sandbox DOI).")
    return value


def normalize_orcid(value):
    value = value.strip().removeprefix("https://orcid.org/")
    if not value:
        return ""
    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", value):
        raise ValueError("ORCID must be your actual identifier in 0000-0000-0000-0000 form.")
    digits = value.replace("-", "")
    total = 0
    for digit in digits[:-1]:
        total = (total + int(digit)) * 2
    check = (12 - total % 11) % 11
    if digits[-1] != ("X" if check == 10 else str(check)):
        raise ValueError("ORCID checksum is invalid.")
    return value


def validate_metadata(metadata):
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", metadata["version"]):
        raise ValueError("Version must be a Python release version such as 0.2.1.")
    date.fromisoformat(metadata["release_date"])
    if metadata["license"] != "MIT":
        raise ValueError("This release tooling expects the repository's MIT license.")
    author = metadata["author"]
    for field in ["given_names", "family_names", "affiliation"]:
        if not author.get(field, "").strip():
            raise ValueError(f"Author {field} must not be empty.")
    author["orcid"] = normalize_orcid(author.get("orcid", ""))
    repository = metadata.get("repository_url", "").strip().rstrip("/").removesuffix(".git")
    if repository and (not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
                       or "YOUR-" in repository.upper() or "YOUR_" in repository.upper()):
        raise ValueError("Use your actual https://github.com/OWNER/REPOSITORY URL.")
    metadata["repository_url"] = repository
    for field in ["version_doi", "concept_doi"]:
        metadata[field] = normalize_doi(metadata.get(field, ""))
    if metadata["version_doi"] and metadata["version_doi"] == metadata["concept_doi"]:
        raise ValueError("The version DOI and concept DOI must be different identifiers.")
    if not metadata["title"].strip() or not metadata["description"].strip():
        raise ValueError("Title and description must not be empty.")
    return metadata


def author_name(metadata):
    author = metadata["author"]
    return f"{author['given_names']} {author['family_names']}"


def citation_text(metadata):
    author = metadata["author"]
    text = (f"{author['family_names']}, {author['given_names']}. ({metadata['release_date'][:4]}). "
            f"{metadata['title']} (Version {metadata['version']}) [Computer software].")
    if metadata["version_doi"]:
        text += f" Zenodo. https://doi.org/{metadata['version_doi']}"
    elif metadata["repository_url"]:
        text += f" {metadata['repository_url']}"
    return text


def render_cff(metadata):
    author = metadata["author"]
    lines = ["cff-version: 1.2.0", "type: software",
             'message: "If you use Rietveld Studio, please cite this software and the GSAS-II engine."',
             f"title: {quoted(metadata['title'])}", f"version: {quoted(metadata['version'])}",
             f"date-released: {quoted(metadata['release_date'])}", "license: MIT", "authors:",
             f"  - family-names: {quoted(author['family_names'])}",
             f"    given-names: {quoted(author['given_names'])}",
             f"    affiliation: {quoted(author['affiliation'])}"]
    if author["orcid"]:
        lines.append(f"    orcid: {quoted('https://orcid.org/' + author['orcid'])}")
    if metadata["repository_url"]:
        lines.extend([f"url: {quoted(metadata['repository_url'])}",
                      f"repository-code: {quoted(metadata['repository_url'])}"])
    if metadata["version_doi"]:
        lines.append(f"doi: {quoted(metadata['version_doi'])}")
    lines.extend([f"abstract: {quoted(metadata['description'])}", "keywords:"])
    lines.extend(f"  - {quoted(keyword)}" for keyword in metadata["keywords"])
    return "\n".join(lines) + "\n"


def render_bibtex(metadata):
    author = metadata["author"]
    fields = [("author", f"{author['family_names']}, {author['given_names']}"),
              ("title", metadata["title"]), ("version", metadata["version"]),
              ("year", metadata["release_date"][:4]), ("date", metadata["release_date"]),
              ("license", metadata["license"])]
    if metadata["version_doi"]:
        fields.extend([("publisher", "Zenodo"), ("doi", metadata["version_doi"]),
                       ("url", "https://doi.org/" + metadata["version_doi"])])
    elif metadata["repository_url"]:
        fields.append(("url", metadata["repository_url"]))
    lines = [f"@software{{Jamil_Rietveld_Studio_{metadata['release_date'][:4]},"]
    lines.extend(f"  {key} = {{{value}}}," for key, value in fields)
    return "\n".join(lines + ["}", ""])


def render_zenodo(metadata):
    author = metadata["author"]
    creator = {"name": f"{author['family_names']}, {author['given_names']}",
               "affiliation": author["affiliation"]}
    if author["orcid"]:
        creator["orcid"] = author["orcid"]
    result = {"title": metadata["title"], "upload_type": "software", "creators": [creator],
              "description": "<p>" + html.escape(metadata["description"]) + "</p>",
              "version": metadata["version"], "publication_date": metadata["release_date"],
              "license": "mit", "access_right": "open", "language": "eng",
              "keywords": metadata["keywords"]}
    if metadata["repository_url"]:
        result["related_identifiers"] = [{"identifier": metadata["repository_url"],
                                           "relation": "isSupplementTo", "scheme": "url"}]
    # Do not feed an old DOI back into the automatic GitHub archive creation.
    # The version DOI belongs to citations; Zenodo assigns each release's DOI.
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def render_init(metadata):
    constants = {"__version__": metadata["version"], "__author__": author_name(metadata),
                 "__license__": metadata["license"], "__release_date__": metadata["release_date"],
                 "__title__": metadata["title"], "__doi__": metadata["version_doi"],
                 "__repository__": metadata["repository_url"], "__citation__": citation_text(metadata)}
    lines = ['"""Rietveld Studio: an inspectable GSAS-II workflow, not a replacement solver."""', ""]
    lines.extend(f"{key} = {quoted(value)}" for key, value in constants.items())
    lines.extend(["", "", "def software_citation(version=None):",
                  '    """Do not attach the current release DOI to another version\'s result."""',
                  "    if not version or version == __version__:", "        return __citation__",
                  '    return f"{__author__}. {__title__} (Version {version}) [Computer software]."', ""])
    return "\n".join(lines)


def replace_section(text, begin, end, body):
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError(f"Expected exactly one {begin} / {end} section.")
    before, remainder = text.split(begin, 1)
    _, after = remainder.split(end, 1)
    return before + begin + "\n" + body.rstrip() + "\n" + end + after


def rendered_files(metadata, root):
    citation = citation_text(metadata)
    readable = ("# Cite Rietveld Studio\n\n" + citation + "\n\n"
                "Please also cite GSAS-II and the actual CIF/source publications used in your analysis.\n"
                "See THIRD_PARTY_NOTICES.md and docs/REFERENCES.bib.\n\n")
    if not metadata["version_doi"]:
        readable += ("No Zenodo DOI has been assigned in this package. After publishing the GitHub release,\n"
                     "copy its real version DOI into scripts/prepare_release.py --doi as described in\n"
                     "PUBLISH_ON_GITHUB_ZENODO.md. Do not treat this as an already published Zenodo record.\n")
    else:
        readable += "This citation identifies the specific version above.\n"
    block = citation + "\n\n"
    if metadata["concept_doi"]:
        doi = metadata["concept_doi"]
        block += f"[![DOI](https://zenodo.org/badge/DOI/{doi}.svg)](https://doi.org/{doi})\n\n"
    block += ("Use [CITATION.cff](CITATION.cff), [BibTeX](CITATION.bib), or "
              "[the citation instructions](CITATION.md). "
              "The badge, when present, links to all versions; the citation identifies this version.\n")
    if not metadata["version_doi"]:
        block += "\nZenodo DOI pending: publish a release before adding a DOI; no DOI is invented here.\n"
    readme = replace_section((root / "README.md").read_text(encoding="utf-8"),
                             BEGIN_CITATION, END_CITATION, block)
    readme = re.sub(r"\*\*Public-release package [^*]+ — MIT open source\.\*\*",
                    f"**Public-release package {metadata['version']} — MIT open source.**", readme, count=1)
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    project, count = re.subn(r'(?m)^version = "[^"]+"$', f'version = "{metadata["version"]}"', project, count=1)
    if count != 1:
        raise ValueError("Could not find project version in pyproject.toml.")
    author = quoted(author_name(metadata))
    project = re.sub(r'(?m)^authors = .*$', f'authors = [{{name = {author}}}]', project)
    project = re.sub(r'(?m)^maintainers = .*$', f'maintainers = [{{name = {author}}}]', project)
    urls = ""
    if metadata["repository_url"]:
        repository = metadata["repository_url"]
        urls = (f'[project.urls]\nRepository = {quoted(repository)}\n'
                f'Issues = {quoted(repository + "/issues")}\n'
                f'Documentation = {quoted(repository + "#readme")}\n')
    if BEGIN_URLS not in project:
        project = project.replace("[project.optional-dependencies]",
                                  BEGIN_URLS + "\n" + END_URLS + "\n\n[project.optional-dependencies]", 1)
    project = replace_section(project, BEGIN_URLS, END_URLS, urls)
    return {"CITATION.cff": render_cff(metadata), "CITATION.bib": render_bibtex(metadata),
            "CITATION.md": readable, ".zenodo.json": render_zenodo(metadata),
            "src/rietveld_studio/__init__.py": render_init(metadata),
            "README.md": readme, "pyproject.toml": project}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check generated files without changing them")
    parser.add_argument("--repo-url", help="Actual GitHub repository URL")
    parser.add_argument("--orcid", help="Author's actual ORCID; optional")
    parser.add_argument("--release-date", help="Actual publication date, YYYY-MM-DD")
    parser.add_argument("--version", help="New version; clears the previous version DOI automatically")
    parser.add_argument("--doi", help="Assigned DOI of this specific Zenodo version")
    parser.add_argument("--concept-doi", help="Assigned Zenodo DOI representing all versions")
    parser.add_argument("--clear-doi", action="store_true", help="Remove the current version DOI")
    args = parser.parse_args(argv)
    overrides = [args.repo_url, args.orcid, args.release_date, args.version, args.doi, args.concept_doi]
    if args.check and (any(value is not None for value in overrides) or args.clear_doi):
        parser.error("--check cannot be combined with changes")
    if args.clear_doi and args.doi:
        parser.error("Choose --clear-doi or --doi, not both")
    metadata_path = ROOT / "release-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if args.version and args.version != metadata["version"]:
        metadata["version_doi"] = ""
    for argument, field in [(args.repo_url, "repository_url"), (args.release_date, "release_date"),
                            (args.version, "version"), (args.doi, "version_doi"),
                            (args.concept_doi, "concept_doi")]:
        if argument is not None:
            metadata[field] = argument
    if args.orcid is not None:
        metadata["author"]["orcid"] = args.orcid
    if args.clear_doi:
        metadata["version_doi"] = ""
    try:
        validate_metadata(metadata)
        files = rendered_files(metadata, ROOT)
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))
    if args.check:
        mismatches = [name for name, text in files.items()
                      if not (ROOT / name).is_file() or (ROOT / name).read_text(encoding="utf-8") != text]
        if mismatches:
            print("Out-of-sync metadata: " + ", ".join(mismatches))
            return 1
        print(f"Metadata consistent: {metadata['version']}; author {author_name(metadata)}; license MIT.")
        print("Version DOI: " + (metadata["version_doi"] or "not yet assigned"))
        return 0
    for name, text in files.items():
        (ROOT / name).write_text(text, encoding="utf-8", newline="\n")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {metadata['version']}; synchronized {len(files)} files. No publication was performed.")
    if not metadata["repository_url"]:
        print("Next: provide the actual repository URL with --repo-url before uploading to GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
