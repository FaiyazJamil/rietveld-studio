"""Rietveld Studio: an inspectable GSAS-II workflow, not a replacement solver."""

__version__ = "0.2.1"
__author__ = "Md Faiyaz Jamil"
__license__ = "MIT"
__release_date__ = "2026-11-02"
__title__ = "Rietveld Studio: A Python GUI for reproducible powder X-ray Rietveld refinement with GSAS-II"
__doi__ = ""
__repository__ = "https://github.com/FaiyazJamil/rietveld-studio"
__citation__ = "Jamil, Md Faiyaz. (2026). Rietveld Studio: A Python GUI for reproducible powder X-ray Rietveld refinement with GSAS-II (Version 0.2.1) [Computer software]. https://github.com/FaiyazJamil/rietveld-studio"


def software_citation(version=None):
    """Do not attach the current release DOI to another version's result."""
    if not version or version == __version__:
        return __citation__
    return f"{__author__}. {__title__} (Version {version}) [Computer software]."
