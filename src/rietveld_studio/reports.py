from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from . import software_citation

COLORS = ["#238276", "#8c62ad", "#c48a29", "#278abd", "#a55662"]


def refinement_figure(result, profile, *, annotate=True):
    fig = Figure(figsize=(12.4, 7.4), layout="constrained", facecolor="white")
    ax, axr = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [4, 1]})
    x, obs, calc, bkg, mask = [profile[k] for k in ("x", "yobs", "ycalc", "background", "mask")]
    mask = mask.astype(bool)
    span = max(float(np.ptp(obs[mask])), 1)
    ax.plot(x, np.where(mask, obs, np.nan), "o", ms=2.2, mfc="none", mec="#253446", mew=.65, label="Observed")
    ax.plot(x, np.where(mask, calc, np.nan), color="#d24a48", lw=1.25, label="Calculated")
    ax.plot(x, np.where(mask, bkg, np.nan), color="#9aa8b7", lw=.9, label="Background")
    baseline = min(float(np.min(obs[mask])), 0) - span * .13
    ax.plot(x, np.where(mask, obs - calc + baseline, np.nan), color="#246aab", lw=.85, label="Difference (offset)")
    ax.axhline(baseline, color="#bec9d3", lw=.6)
    for i, phase in enumerate(result["phases"]):
        refs = [r for r in result["reflections"] if r["phase"] == phase["phase"] and r["component"] != "Kα2"]
        y = baseline - span * .085 * (i + 1)
        ax.vlines([r["two_theta"] for r in refs], y - span * .016, y + span * .016,
                  color=COLORS[i % len(COLORS)], lw=.85)
        ax.text(.994, y, phase["phase"], color=COLORS[i % len(COLORS)], va="center", ha="right",
                transform=ax.get_yaxis_transform(), fontsize=9,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": .85, "pad": 1})
    if annotate:
        candidates = sorted([r for r in result["reflections"] if r["component"] != "Kα2"],
                            key=lambda r: -r["Icalc"])
        marked = []
        for r in candidates:
            pos = r["two_theta"]
            if len(marked) >= 10 or any(abs(pos - p) < (x[-1] - x[0]) * .035 for p in marked):
                continue
            index = int(np.argmin(abs(x - pos)))
            if not mask[index]:
                continue
            marked.append(pos)
            ax.annotate(f"({r['h']} {r['k']} {r['l']})", (pos, calc[index]), xytext=(0, 8),
                        textcoords="offset points", rotation=90, ha="center", va="bottom", fontsize=8, color="#596778")
    stats = result["statistics"]
    descriptive = stats.get("statistical_interpretation") == "descriptive_only"
    ax.text(.985, .975, f"$R_{{wp}}$ = {stats['Rwp_percent']:.2f}%\n$R_p$ = {stats['Rp_percent']:.2f}%\n"
            f"$χ^2_{{red}}$ = {stats['chi2_reduced']:.3f}" + ("\n(descriptive weights)" if descriptive else ""), transform=ax.transAxes, ha="right", va="top", fontsize=10,
            bbox={"facecolor": "white", "edgecolor": "#d7e0e9", "boxstyle": "round,pad=0.55", "alpha": .96})
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.015), borderaxespad=0,
              frameon=False, fontsize=10, ncol=4)
    # Leave room for vertical hkl labels above the strongest peak.
    ax.set_ylim(top=max(float(np.max(obs[mask])), float(np.max(calc[mask]))) + span * .32)
    ax.set_ylabel("Intensity (input units)", fontsize=13)
    ax.set_title(result["project_name"], loc="left", fontsize=15, pad=40, weight="bold")
    axr.plot(x, np.where(mask, (obs - calc) * np.sqrt(profile["weights"]), np.nan), color="#246aab", lw=.75)
    axr.axhline(0, color="#697889", lw=.65)
    axr.set_ylabel("ΔI / σ", fontsize=12)
    axr.set_xlabel("2θ (degree)", fontsize=13)
    for axis in (ax, axr):
        axis.tick_params(labelsize=11, direction="in", top=True, right=True)
        axis.spines[["top", "right"]].set_visible(True)
        axis.margins(x=0)
    ax.set_xlim(float(x[mask].min()), float(x[mask].max()))
    # Shade exclusions as gaps; outside the fit interval is excluded by x limits.
    excluded = ~mask
    changes = np.diff(np.r_[False, excluded, False].astype(int))
    for first, last in zip(np.where(changes == 1)[0], np.where(changes == -1)[0]):
        for axis in (ax, axr):
            axis.axvspan(x[first], x[min(last, len(x) - 1)], color="#dfe5ed", alpha=.45, zorder=-5)
    return fig


def convergence_figure(result):
    fig = Figure(figsize=(10.5, 5.2), layout="constrained", facecolor="white")
    axis = fig.add_subplot()
    rows = result.get("iteration_history", [])
    if not rows:
        axis.set_axis_off()
        axis.text(.5, .5, "Refinement-pass history will appear here", ha="center", va="center", color="#64798c", fontsize=14)
        return fig
    best = np.inf
    best_values, step = [], np.arange(1, len(rows) + 1)
    for row in rows:
        if row.get("accepted"):
            best = min(best, row["Rwp_percent"])
        best_values.append(best if np.isfinite(best) else np.nan)
    trials = sorted({row["trial"] for row in rows})
    for number in trials:
        indices = [i for i, row in enumerate(rows) if row["trial"] == number]
        axis.plot(step[indices], [rows[i]["Rwp_percent"] for i in indices], "o-", ms=3.5, lw=1,
                  color=COLORS[(number - 1) % len(COLORS)], label=f"Start {number}")
    axis.plot(step, best_values, color="#203a54", lw=1.7, linestyle="--", label="Best valid Rwp so far")
    axis.set_xlabel("Completed GSAS-II refinement call", fontsize=12)
    axis.set_ylabel("Rwp (%) — fixed data and weights", fontsize=12)
    axis.set_title("Refinement convergence across independent starts", loc="left", fontsize=14)
    axis.tick_params(direction="in", labelsize=10)
    axis.legend(frameon=False, fontsize=9)
    axis.grid(alpha=.15)
    return fig


def _dataframe(rows, columns):
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=columns)


def _safe_csv(df, path):
    # Prevent text imported from CIF/COD from becoming spreadsheet formulas.
    frame = df.copy()
    for col in frame.select_dtypes(include=["object", "string"]).columns:
        frame[col] = frame[col].map(lambda value: "'" + value if isinstance(value, str) and
                                  value.startswith(("=", "+", "-", "@")) else value)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame


def export_bundle(output):
    output = Path(output)
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    with np.load(output / "profile.npz", allow_pickle=False) as source:
        profile = {k: source[k] for k in source.files}
    frames = {}
    frames["profile"] = pd.DataFrame({"two_theta_deg": profile["x"], "observed": profile["yobs"],
        "calculated": profile["ycalc"], "background": profile["background"], "difference": profile["residual"],
        "sigma": profile["sigma"], "weight": profile["weights"], "included": profile["mask"].astype(int)})
    cell_rows = []
    for phase in result["phases"]:
        for key, value in phase["cell"].items():
            cell_rows.append({"phase": phase["phase"], "parameter": key, "value": value,
                "standard_uncertainty": phase["cell_su"].get(key),
                "unit": "Å³" if key == "volume" else "degree" if "angle" in key else "Å",
                "refined": phase["cell_refined"]})
    frames["lattice_parameters"] = pd.DataFrame(cell_rows)
    frames["phase_results"] = pd.json_normalize(result["phases"]).drop(columns=[c for c in pd.json_normalize(result["phases"]).columns if c.startswith(("cell.", "cell_su.", "initial_cell."))])
    frames["atoms"] = _dataframe(result["atoms"], ["phase", "label", "element", "x", "y", "z", "occupancy", "Uiso_A2"])
    frames["parameters"] = _dataframe(result["parameters"], ["parameter", "value", "standard_uncertainty"])
    frames["reflections"] = _dataframe(result["reflections"], ["phase", "h", "k", "l", "two_theta", "d_A", "Icalc", "component", "source_url"])
    frames["peak_associations"] = _dataframe(result["peak_matches"], ["observed_two_theta", "status", "assignments", "source_urls"])
    frames["statistics"] = pd.DataFrame([{"metric": k, "value": v} for k, v in result["statistics"].items()])
    frames["correlations"] = _dataframe(result["correlations"], ["parameter_1", "parameter_2", "correlation"])
    frames["provenance"] = pd.DataFrame(result["provenance"])
    frames["stage_history"] = pd.DataFrame(result["stage_history"])
    frames["diagnostics"] = pd.DataFrame({"diagnostic": result["warnings"]})
    frames["iteration_history"] = _dataframe(result.get("iteration_history", []), ["trial", "stage", "pass", "Rwp_percent", "max_shift_over_su"])
    frames["trial_history"] = _dataframe(result.get("trial_history", []), ["trial", "name", "Rwp_percent", "selected"])
    frames["convergence"] = pd.json_normalize(result.get("convergence", {}))
    diagnostic_values = result.get("fit_diagnostics", {})
    frames["fit_diagnostics"] = pd.DataFrame([{"diagnostic": k, "value": v} for k, v in diagnostic_values.items()
                                            if k not in {"messages", "strong_peak_comparisons"}])
    if frames["fit_diagnostics"].empty:
        frames["fit_diagnostics"] = pd.DataFrame(columns=["diagnostic", "value"])
    frames["strong_peak_comparisons"] = _dataframe(diagnostic_values.get("strong_peak_comparisons", []),
        ["observed_two_theta", "calculated_two_theta", "delta_two_theta", "observed_FWHM_deg", "calculated_FWHM_deg"])
    instrument_rows = []
    for parameter, values in result["instrument_actual"].items():
        if isinstance(values, list) and len(values) >= 2:
            instrument_rows.append({"parameter": parameter, "value": values[1], "initial_value": values[0],
                "refined": bool(values[2]) if len(values) > 2 else False})
    frames["instrument_parameters"] = pd.DataFrame(instrument_rows)
    requested = result["requested_settings"]
    included_profile = frames["profile"][frames["profile"]["included"] == 1]
    settings = {"geometry": result["sample_parameters_actual"].get("Type"),
        "goniometer_radius_mm": result["sample_parameters_actual"].get("Gonio. radius"),
        "instrument_calibrated_user_declaration": requested["instrument"]["calibrated"],
        "background_type": result["background_actual"][0][0],
        "background_coefficients": result["background_actual"][0][2],
        "actual_fit_min_two_theta_deg": included_profile["two_theta_deg"].min(),
        "actual_fit_max_two_theta_deg": included_profile["two_theta_deg"].max(),
        "excluded_ranges_deg": str(requested["recipe"]["excluded_ranges"]),
        "profile_mode": requested["recipe"]["profile_mode"],
        "requested_position_correction": requested["recipe"]["position_correction"],
        "peak_match_tolerance_deg": requested["recipe"]["peak_tolerance_deg"],
        "weighting": result["weighting"], "GSAS_II_version": result["engine"].get("gsas_version", "")}
    frames["model_settings"] = pd.DataFrame([{"setting": k, "value": v} for k, v in settings.items()])
    safe_frames = {name: _safe_csv(frame, output / f"{name}.csv") for name, frame in frames.items()}
    with pd.ExcelWriter(output / "refinement_tables.xlsx", engine="openpyxl") as writer:
        for name, frame in safe_frames.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
            sheet = writer.sheets[name[:31]]
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(54, max(14, len(str(column[0].value)) + 3))
    fig = refinement_figure(result, profile)
    fig.savefig(output / "refinement.png", dpi=300, bbox_inches="tight")
    fig.savefig(output / "refinement.svg", bbox_inches="tight")
    fig.savefig(output / "refinement.pdf", bbox_inches="tight")
    if result.get("iteration_history"):
        progress = convergence_figure(result)
        progress.savefig(output / "convergence.png", dpi=200, bbox_inches="tight")
        progress.savefig(output / "convergence.svg", bbox_inches="tight")
    _write_report(output, result, frames)
    from . import origin_export
    shutil.copy2(origin_export.__file__, output / "export_to_origin.py")
    (output / "OPEN_IN_ORIGIN.txt").write_text(
        "Native editable Origin project export\n\n"
        "Requires Windows, licensed Origin 2021+, and external Python with numpy, pandas, originpro.\n"
        "From a terminal in this result folder:\n"
        "  python -m pip install numpy pandas originpro\n"
        "  python export_to_origin.py\n\n"
        "Creates refinement.opju with editable graphs and source worksheets.\n"
        "The app also provides an Export Origin button and optional automatic export on Windows.\n"
        "Existing OPJU files are never overwritten. Select another filename with --output.\n"
        "The exporter starts and closes its own Origin instance; existing sessions are not attached.\n",
        encoding="utf-8")


def _write_report(output, result, frames):
    esc = html.escape
    stats = result["statistics"]
    descriptive = stats.get("statistical_interpretation") == "descriptive_only"
    statistical_note = ("Constant sigma was used: χ², Rexp and GOF are descriptive values tied to the chosen sigma and intensity units. They do not establish that a fit is statistically adequate."
        if descriptive else "Statistical interpretation is conditional on the declared experimental intensity uncertainties and model.")
    convergence_note = result.get("convergence", {})
    convergence_text = ("Convergence criteria met" if convergence_note.get("converged") else "Convergence not established / not recorded")
    convergence_image = '<h2>Iteration history</h2><img src="convergence.svg" alt="Rwp versus completed refinement calls">' if result.get("iteration_history") else ""
    metrics = "".join(f'<div class="metric"><span>{esc(label)}</span><b>{stats[key]:.4g}{suffix}</b></div>'
        for label, key, suffix in [("Rwp", "Rwp_percent", "%"), ("Rp", "Rp_percent", "%"),
                                  ("Rexp", "Rexp_percent", "%"), ("Reduced χ²", "chi2_reduced", ""),
                                  ("Goodness of fit", "goodness_of_fit", "")])
    diagnostics = "".join(f"<li>{esc(str(w))}</li>" for w in result["warnings"])
    citations = []
    for p in result["provenance"]:
        source = p.get("source_url", "")
        link = f'<a href="{esc(source, quote=True)}">{esc(source)}</a>' if source.startswith("https://") else "Local CIF"
        doi = p.get("doi", "")
        doi_link = f' · <a href="https://doi.org/{esc(doi, quote=True)}">DOI: {esc(doi)}</a>' if doi else ""
        citations.append(f"<li><b>{esc(p['name'])}</b>: {link}{doi_link}<br>{esc(p.get('citation', ''))}<br>"
                         f"Input SHA256: <code>{esc(p['used_sha256'])}</code></li>")
    sections = []
    for title, key in [("Lattice parameters and standard uncertainties", "lattice_parameters"),
                       ("Measurement and model settings", "model_settings"),
                       ("Actual fitted instrument parameters", "instrument_parameters"),
                       ("Phase results", "phase_results"), ("Atomic model", "atoms"),
                       ("Refinement stages", "stage_history"), ("Strong parameter correlations", "correlations"),
                       ("Independent starting trials", "trial_history"), ("Convergence criteria", "convergence"),
                       ("Residual diagnostics", "fit_diagnostics"),
                       ("Observed peak associations", "peak_associations")]:
        frame = frames[key]
        table = frame.head(200).to_html(index=False, escape=True, na_rep="—", float_format=lambda n: f"{n:.6g}") if len(frame) else "<p>None reported.</p>"
        sections.append(f"<h2>{title}</h2><div class='table-wrap'>{table}</div>" +
                        ("<p>First 200 rows shown; complete values are in the CSV/XLSX.</p>" if len(frame) > 200 else ""))
    text = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(result['project_name'])} — Rietveld report</title><style>
body{{font:15px/1.65 system-ui,sans-serif;color:#263446;background:#f2f5f8;margin:0}}main{{max-width:1180px;margin:40px auto;padding:40px;background:white;border-radius:18px}}
h1{{font-size:32px;letter-spacing:-.8px;margin-bottom:8px}}h2{{margin-top:36px;font-size:20px}}.eyebrow{{color:#217e75;font-size:12px;letter-spacing:2px;font-weight:700}}
.metrics{{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}}.metric{{padding:16px 22px;background:#f2f6f9;border:1px solid #e2e8ef;border-radius:12px;min-width:130px}}.metric span{{display:block;color:#637488;font-size:13px}}.metric b{{font-size:24px}}
img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{text-align:left;border-bottom:1px solid #e4eaf0;padding:9px 12px}}th{{background:#eef4f7}}.table-wrap{{overflow:auto}}code{{font-size:11px;word-break:break-all}}a{{color:#166f93}}.note{{background:#f7f5ec;padding:18px;border-radius:10px}}li{{margin-bottom:9px}}@media print{{body{{background:white}}main{{padding:0;margin:0}}h2{{break-after:avoid}}.table-wrap{{overflow:visible}}}}
</style></head><body><main><div class="eyebrow">RIETVELD STUDIO · GSAS-II</div>
<h1>{esc(result['project_name'])}</h1><p>{esc(result['finished_utc'])} · {esc(str(stats['n_observations']))} observations · {stats['n_parameters']} refined variables</p>
<div class="metrics">{metrics}</div><img src="refinement.svg" alt="Observed, calculated, difference, phase ticks and standardized residual">
<div class="note"><b>Weight interpretation:</b> {esc(statistical_note)}<br><b>Optimizer:</b> {esc(convergence_text)}. {esc(str(convergence_note.get('stop_reason') or ''))}</div>
{convergence_image}
<div class="note"><b>Interpretation:</b> a lower Rwp alone does not establish a correct chemical or structural model. Review residuals, convergence, correlations, phase selection, wavelength, and instrument calibration. Phase fractions are relative to the modeled crystalline phases; amorphous content, oxidation state, dopant-site identity, and Li occupancy are not established by this automated fit.</div>
<h2>Diagnostics and assumptions</h2><ul>{diagnostics or '<li>No automatic diagnostic flags.</li>'}</ul>
<p><b>Weighting:</b> {esc(result['weighting'])}</p><p>{esc(stats['definition'])}</p>
{''.join(sections)}<h2>Peak assignment basis</h2><p>hkl positions are calculated from each confirmed CIF and the refined model. Associations are based on a user-set angular tolerance and observed local maxima. Overlaps remain ambiguous; unmatched peaks have no automatic chemical identity. These are not independent database-card matches. Local CIFs have no externally verified online provenance unless supplied in the source metadata. Kα2 positions use Bragg-law shifts; their exported intensities are approximate ratio-scaled Kα1 intensities.</p>
<h2>Sources and reproducibility</h2><ul>{''.join(citations)}</ul>
<p>The folder includes the original powder input, selected CIF blocks, instrument parameters, checksums, settings, engine log, accepted/rejected-stage history, covariance, refined CIFs and the native GSAS-II project.</p>
<h2>References</h2><ul><li>{esc(software_citation(result.get('application', {}).get('version')))}</li>
<li><a href="https://gsas-ii.readthedocs.io/en/latest/GSASIIscriptable.html">GSAS-II scripting API</a> · Toby &amp; Von Dreele, J. Appl. Cryst. 46 (2013), <a href="https://doi.org/10.1107/S0021889813003531">529–531</a>.</li>
<li><a href="https://wiki.crystallography.net/RESTful_API/">Crystallography Open Database API</a>.</li>
<li><a href="https://docs.originlab.com/python/">OriginLab Python automation</a>.</li></ul>
<h2>Origin project</h2><p>On Windows with licensed Origin, use the app's Export Origin action or run <code>python export_to_origin.py</code> in this folder. This creates a native <code>.opju</code> with editable graphs and data tables. A ZIP, workbook, or image is never mislabeled as an OPJU.</p>
</main></body></html>'''
    (output / "report.html").write_text(text, encoding="utf-8")

