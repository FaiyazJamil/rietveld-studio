"""Standalone native Origin exporter. This file is also copied into each result bundle.

Run with an external Windows Python, originpro installed, and licensed Origin 2021+.
Never attaches to or resets an existing user session.
"""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd


def export_origin(run_dir, destination=None, *, show=True):
    run_dir = Path(run_dir).resolve()
    destination = Path(destination or run_dir / "refinement.opju").resolve()
    if platform.system() != "Windows":
        raise RuntimeError("Native .opju export requires Windows and an installed, licensed Origin 2021+.")
    if destination.suffix.lower() != ".opju":
        raise ValueError("Choose an .opju destination.")
    if destination.exists():
        raise FileExistsError(f"Origin project already exists: {destination}. Choose a new filename.")
    try:
        import originpro as op
    except ImportError as exc:
        raise RuntimeError("Install Origin automation in this Python: python -m pip install originpro") from exc
    if not op.oext:
        raise RuntimeError("Run this exporter from external Python. It creates a dedicated Origin instance to protect existing sessions.")
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    profile = pd.read_csv(run_dir / "profile.csv")
    warnings = []
    saved = False
    try:
        # originpro uses OriginExt.Application() for a new instance by default.
        # Do NOT call attach(), ApplicationSI(), or new() here.
        op.set_show(show)
        book = op.new_book("w", lname="Rietveld refinement results")
        sheets = {}
        for index, (filename, name) in enumerate([
            ("profile.csv", "Profile"), ("lattice_parameters.csv", "Lattice"),
            ("phase_results.csv", "Phases"), ("atoms.csv", "Atoms"),
            ("parameters.csv", "Parameters"), ("reflections.csv", "Reflections"),
            ("peak_associations.csv", "Peak associations"), ("statistics.csv", "Fit statistics"),
            ("correlations.csv", "Correlations"), ("provenance.csv", "Sources"),
            ("stage_history.csv", "Fit stages"), ("diagnostics.csv", "Diagnostics"),
            ("instrument_parameters.csv", "Instrument"), ("model_settings.csv", "Model settings"),
            ("iteration_history.csv", "Iterations"), ("trial_history.csv", "Starting trials"),
            ("fit_diagnostics.csv", "Fit diagnostics"),
        ]):
            if not (run_dir / filename).is_file():
                warnings.append(f"Table unavailable in this older result: {filename}")
                continue
            sheet = book[0] if index == 0 else book.add_sheet()
            sheet.name = name
            df = pd.read_csv(run_dir / filename)
            sheet.from_df(df)
            sheets[name] = sheet
        x = profile["two_theta_deg"].to_numpy()
        included = profile["included"].to_numpy().astype(bool)
        obs = profile["observed"].to_numpy()
        calc = profile["calculated"].to_numpy()
        background = profile["background"].to_numpy()
        residual = obs - calc
        span = max(float(np.ptp(obs[included])), 1.0)
        baseline = min(float(np.min(obs[included])), 0.0) - 0.18 * span
        plot_df = pd.DataFrame({"2theta": x, "Observed": np.where(included, obs, np.nan),
            "Calculated": np.where(included, calc, np.nan), "Background": np.where(included, background, np.nan),
            "Difference (offset)": np.where(included, residual + baseline, np.nan),
            "Zero for difference": np.full(len(x), baseline)})
        plot_sheet = book.add_sheet()
        plot_sheet.name = "Plot data"
        plot_sheet.from_df(plot_df)
        graph = op.new_graph(lname="Rietveld observed, calculated, difference and Bragg ticks", template="line")
        layer = graph[0]
        for col, color, kind in [(1, "#263142", "scatter"), (2, "#d24a48", "line"),
                                  (3, "#95a1ae", "line"), (4, "#246aab", "line"), (5, "#b9c4cf", "line")]:
            plot = layer.add_plot(plot_sheet, coly=col, colx=0, type=kind)
            plot.color = color
            try:
                if kind == "scatter":
                    plot.symbol_size = 2
                else:
                    plot.set_float("line.width", 1.2)
            except Exception as exc:
                warnings.append(f"Plot style property unavailable: {exc}")
        colors = ["#238276", "#8c62ad", "#c48a29", "#278abd", "#a55662"]
        references = pd.read_csv(run_dir / "reflections.csv")
        tick_book = op.new_book("w", lname="Bragg reflection tick data")
        for i, phase in enumerate(result["phases"]):
            selected = references[(references["phase"] == phase["phase"]) & (references["component"] != "Kα2")]
            positions = selected["two_theta"].to_numpy()
            center = baseline - (i + 1) * span * .085
            tick_x = np.repeat(positions, 3).astype(float)
            tick_y = np.tile([center - span * .015, center + span * .015, np.nan], len(positions))
            tick_x[2::3] = np.nan
            sheet = tick_book[0] if i == 0 else tick_book.add_sheet()
            sheet.name = f"Phase {i+1}"
            sheet.from_df(pd.DataFrame({"2theta": tick_x, phase["phase"]: tick_y}))
            ticks = layer.add_plot(sheet, coly=1, colx=0, type="line")
            ticks.color = colors[i % len(colors)]
        layer.axis("x").title = "2θ (degree)"
        layer.axis("y").title = "Intensity (counts or input units)"
        layer.rescale()
        layer.set_xlim(float(x[included].min()), float(x[included].max()))
        # Human-readable legend retains phase names and does not invent card numbers.
        legend = layer.label("Legend")
        if legend:
            legend.text = "\\l(1) Observed\n\\l(2) Calculated\n\\l(3) Background\n\\l(4) Difference (offset)"
            legend.set_int("fsize", 16)
        residual_graph = op.new_graph(lname="Standardized residual", template="line")
        residual_sheet = book.add_sheet()
        residual_sheet.name = "Residual diagnostics"
        residual_sheet.from_df(pd.DataFrame({"2theta": x,
            "(Observed - Calculated) / sigma": np.where(included, residual / profile["sigma"].to_numpy(), np.nan)}))
        residual_graph[0].add_plot(residual_sheet, coly=1, colx=0, type="line")
        residual_graph[0].axis("x").title = "2θ (degree)"
        residual_graph[0].axis("y").title = "(Yobs − Ycalc) / σ"
        residual_graph[0].rescale()
        history_file = run_dir / "iteration_history.csv"
        if history_file.is_file():
            history = pd.read_csv(history_file)
            if len(history) and "Rwp_percent" in history:
                progress_sheet = book.add_sheet()
                progress_sheet.name = "Convergence data"
                progress_sheet.from_df(pd.DataFrame({"Call": np.arange(1, len(history) + 1),
                    "Rwp across starts": history["Rwp_percent"],
                    "Best valid Rwp": history["Rwp_percent"].where(history["accepted"].astype(bool)).cummin().ffill()}))
                progress_graph = op.new_graph(lname="Refinement convergence across starts", template="line")
                progress_graph[0].add_plot(progress_sheet, coly=1, colx=0, type="line")
                progress_graph[0].add_plot(progress_sheet, coly=2, colx=0, type="line").color = "#238276"
                progress_graph[0].axis("x").title = "Completed GSAS-II refinement call"
                progress_graph[0].axis("y").title = "Rwp (%)"
                progress_graph[0].rescale()
        # Worksheets, data-backed editable graphs, and phase ticks are stored natively.
        if not op.save(str(destination)):
            raise RuntimeError("Origin reported that saving the project failed.")
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("Origin did not create the requested OPJU file.")
        saved = True
        return {"path": str(destination), "warnings": warnings}
    finally:
        # This process owns the new automation instance. Never close an attached session.
        if op.oext:
            try:
                op.exit()
            except Exception as exc:
                warnings.append(f"Origin automation shutdown reported: {exc}")
        if not saved and destination.exists() and destination.stat().st_size == 0:
            destination.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", nargs="?", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--output")
    parser.add_argument("--hidden", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = export_origin(args.run_dir, args.output, show=not args.hidden)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(f"Origin export failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

