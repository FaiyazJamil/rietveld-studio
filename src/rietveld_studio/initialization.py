"""Bounded position/profile starting guesses. These never change observations or weights."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

from .structures import preview_reflections


def background_strategy(config):
    requested = config.recipe.background_mode
    name = Path(config.powder_path).name.lower().replace(" ", "_")
    indicators = ("bg_sub", "bg-sub", "bkg_sub", "background_sub", "background-subtracted")
    inferred = requested == "auto" and any(s in name for s in indicators)
    mode = "subtracted" if requested == "subtracted" or inferred else "raw"
    terms = min(3, config.recipe.background_terms) if mode == "subtracted" else config.recipe.background_terms
    return {"requested": requested, "effective_mode": mode, "effective_terms": terms,
            "inferred_from_filename": inferred}


def rank_alignment_starts(x, y, mask, d_spacings, intensities, wavelength, *,
                          search_percent=2., allow_zero=False, zero_window=.20):
    """Rank uniform cell-scale/allowed-zero guesses using unsmoothed observed maxima.

    Used only for initialization. This score is not a R factor or phase-identification score.
    The real GSAS-II full-profile objective selects between completed trials.
    """
    x, y, mask = np.asarray(x), np.asarray(y), np.asarray(mask, dtype=bool)
    d = np.asarray(d_spacings, dtype=float)
    intensity = np.asarray(intensities, dtype=float)
    if len(d) == 0:
        return [{"cell_scale": 1., "zero_offset_deg": 0., "alignment_score": None}]
    signal = y - np.quantile(y[mask], .20)
    prominence = max(np.ptp(signal[mask]) * .025, np.finfo(float).eps)
    indices, props = find_peaks(signal, prominence=prominence,
        distance=max(1, int(.06 / np.median(np.diff(x)))))
    valid = mask[indices]
    observed = x[indices[valid]]
    if len(observed) < 3:
        return [{"cell_scale": 1., "zero_offset_deg": 0., "alignment_score": None}]
    strength = np.sqrt(props["prominences"][valid])
    strength /= max(float(strength.max()), 1e-12)
    step = float(np.median(np.diff(x)))
    kernel_width = max(.065, 2.0 * step)
    reflection_weights = np.sqrt(np.maximum(intensity, 0))
    reflection_weights /= max(float(reflection_weights.sum()), 1e-12)
    scales = np.linspace(1 - search_percent / 100, 1 + search_percent / 100, 81) if search_percent else [1.]
    shifts = np.linspace(-zero_window, zero_window, 17) if allow_zero else [0.]
    ranked = []
    for scale in scales:
        argument = wavelength / (2 * d * scale)
        valid_ref = (argument > 0) & (argument < 1)
        positions = 2 * np.degrees(np.arcsin(np.clip(argument, 0, 1)))
        for shift in shifts:
            predicted = positions + shift
            usable = valid_ref & (predicted >= x[mask][0]) & (predicted <= x[mask][-1])
            sample_indices = np.clip(np.searchsorted(x, predicted), 0, len(x) - 1)
            usable &= mask[sample_indices]
            if not usable.any():
                continue
            distances = abs(predicted[:, None] - observed[None, :])
            matched = np.max(np.exp(-.5 * (distances / kernel_width)**2) * strength, axis=1)
            score = float(np.sum(reflection_weights[usable] * matched[usable]))
            # A weak prior avoids choosing an unnecessarily large correction on a flat/noisy score surface.
            score -= 1e-3 * abs(scale - 1) / max(search_percent / 100, 1e-6)
            ranked.append({"cell_scale": float(scale), "zero_offset_deg": float(shift),
                           "alignment_score": score})
    return sorted(ranked, key=lambda row: -row["alignment_score"])


def starting_trials(config, powder, mask, actual_instrument):
    baseline = {"name": "original", "cell_scale": 1., "zero_offset_deg": 0.,
                "width_factor": 1., "alignment_score": None}
    if not config.recipe.auto_initialize or config.recipe.start_trials == 1:
        return [baseline], []
    notes = []
    wavelength = actual_instrument.get("Lam1", actual_instrument.get("Lam"))[1]
    can_scale = config.recipe.refine_cell and any(p.refine_cell for p in config.phases)
    all_refs = []
    try:
        # A common cell scale is meaningful only when all active phases may change cell.
        # Otherwise retain their cells and rely on independent GSAS-II refinement.
        scale_search = config.recipe.cell_search_percent if can_scale and all(p.refine_cell for p in config.phases) else 0.
        for phase in config.phases:
            refs = preview_reflections(phase, wavelength, max(.2, float(powder.x[mask][0]) - 2),
                                       min(179., float(powder.x[mask][-1]) + 2))
            all_refs.extend(sorted(refs, key=lambda r: -r["intensity"])[:120])
        ranked = rank_alignment_starts(powder.x, powder.y, mask,
            [r["d_A"] for r in all_refs], [r["intensity"] for r in all_refs], wavelength,
            search_percent=scale_search, allow_zero=config.recipe.position_correction == "zero")
    except (ValueError, RuntimeError) as exc:
        ranked = []
        notes.append(f"CIF-based starting-position search unavailable: {exc}; using profile-width starts.")
    best = ranked[0] if ranked else {"cell_scale": 1., "zero_offset_deg": 0., "alignment_score": None}
    can_vary_width = config.recipe.profile_mode == "instrument" and not config.instrument.calibrated
    # Preserve one untouched start, then use a broader profile to improve initial overlap.
    candidates = [baseline, dict(best, name="aligned", width_factor=1.),
                  dict(best, name="aligned_broader", width_factor=2.5 if can_vary_width else 1.)]
    for width in ([.6, 1.5, 4.] if can_vary_width else [1.]):
        candidates.append(dict(best, name=f"aligned_width_{width:g}", width_factor=width))
    for row in ranked[1:]:
        if abs(row["cell_scale"] - best["cell_scale"]) < .001 and abs(row["zero_offset_deg"] - best["zero_offset_deg"]) < .05:
            continue
        candidates.append(dict(row, name="alternate_alignment", width_factor=1.))
        if len(candidates) >= 15:
            break
    selected, seen = [], set()
    for trial in candidates:
        key = (round(trial["cell_scale"], 6), round(trial["zero_offset_deg"], 5), trial["width_factor"])
        if key in seen:
            continue
        seen.add(key)
        selected.append(trial)
        if len(selected) >= config.recipe.start_trials:
            break
    return selected, notes


def apply_start(gpx, trial, config):
    factor = trial["cell_scale"]
    if factor != 1. and config.recipe.refine_cell:
        for phase, spec in zip(gpx.phases(), config.phases):
            if spec.refine_cell:
                cell = phase.data["General"]["Cell"]
                cell[1:4] = [value * factor for value in cell[1:4]]
                cell[7] *= factor**3
    hist = gpx.histogram(0)
    if config.recipe.position_correction == "zero":
        hist.InstrumentParameters["Zero"][1] += trial["zero_offset_deg"]
    width = trial["width_factor"]
    for key in ("U", "V", "W"):
        hist.InstrumentParameters[key][1] *= width**2
    for key in ("X", "Y", "Z"):
        if key in hist.InstrumentParameters:
            hist.InstrumentParameters[key][1] *= width


def initial_background_and_scale(gpx, powder, mask, terms, cycles):
    """One GSAS-II forward calculation, then a weighted linear global-scale estimate."""
    hist = gpx.histogram(0)
    background = float(np.quantile(powder.y[mask], .20))
    hist.set_refinements({"Background": {"no. coeffs": terms,
        "coeffs": [background] + [0.] * (terms - 1), "refine": False}})
    hist.SampleParameters["Scale"] = [1., True]
    gpx.set_Controls("cycles", 0)
    try:
        gpx.refine(makeBack=False)
        hist = gpx.histogram(0)
        net = np.asarray(np.ma.getdata(hist.getdata("Ycalc"))) - np.asarray(np.ma.getdata(hist.getdata("Background")))
        weights = 1 / powder.sigma[mask]**2
        denominator = float(np.sum(weights * net[mask]**2))
        if denominator > 0:
            scale = float(np.sum(weights * net[mask] * (powder.y[mask] - background)) / denominator)
            if math.isfinite(scale) and scale > 0:
                hist.SampleParameters["Scale"][0] = max(scale, 1e-9)
    finally:
        gpx.set_Controls("cycles", cycles)
        gpx.data["Covariance"]["data"] = {}

