"""Explain residuals in measured units. Diagnostics do not modify the fitted objective."""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks, peak_widths

from .analysis import json_safe


def _prominent(x, values, mask, fraction=.025):
    threshold = max(float(np.ptp(values[mask])) * fraction, np.finfo(float).eps)
    indices, properties = find_peaks(values, prominence=threshold,
        distance=max(1, int(.07 / np.median(np.diff(x)))))
    valid = mask[indices]
    indices = indices[valid]
    if len(indices):
        widths, _, left, right = peak_widths(values, indices, rel_height=.5)
        widths = np.interp(right, np.arange(len(x)), x) - np.interp(left, np.arange(len(x)), x)
    else:
        widths = np.array([])
    return indices, widths


def diagnose_fit(profile, reflections, statistics, weighting):
    x, observed, calculated, background, weights, mask = [np.asarray(profile[key]) for key in
        ("x", "yobs", "ycalc", "background", "weights", "mask")]
    mask = mask.astype(bool)
    residual = observed - calculated
    net_calc = calculated - background
    net_obs = observed - background
    messages = []
    descriptive = "constant sigma" in weighting
    if descriptive:
        messages.append("Constant sigma was selected: reduced chi-square, Rexp and GOF depend on the chosen sigma/intensity units. Values near one do not establish a correct noise model or structure.")
    if np.any(observed[mask] < 0):
        messages.append("Negative/background-subtracted observations are retained. Rp/Rwp from such data are not directly comparable with R factors from an unsubtracted pattern; adding an intensity offset to lower them would be invalid.")
    baseline = mask & (net_calc < max(float(np.max(net_calc[mask])), 1e-12) * .02)
    for row in reflections:
        baseline &= abs(x - row["two_theta"]) > .12
    adjacent = baseline[1:] & baseline[:-1]
    differences = np.diff(observed)[adjacent]
    noise = None
    if len(differences) >= 30:
        mad = float(np.median(abs(differences - np.median(differences))))
        noise = mad / (.6744897501960817 * np.sqrt(2))
        if not np.isfinite(noise) or noise <= 0:
            noise = None
    approximate_rwp_noise = None
    if descriptive and noise is not None:
        approximate_rwp_noise = 100 * float(np.sqrt(np.sum(weights[mask]) * noise**2 /
                                                  np.sum(weights[mask] * observed[mask]**2)))
    observed_peaks, observed_widths = _prominent(x, net_obs, mask)
    model_peaks, model_widths = _prominent(x, net_calc, mask)
    offsets, width_ratios, pairs = [], [], []
    for model_index, model_width in zip(model_peaks, model_widths):
        if not len(observed_peaks):
            break
        nearest = int(np.argmin(abs(x[observed_peaks] - x[model_index])))
        obs_index, obs_width = observed_peaks[nearest], observed_widths[nearest]
        delta = float(x[obs_index] - x[model_index])
        if abs(delta) > .35:
            continue
        offsets.append(delta)
        if model_width > 0 and obs_width > 0:
            width_ratios.append(float(obs_width / model_width))
        pairs.append({"observed_two_theta": float(x[obs_index]), "calculated_two_theta": float(x[model_index]),
                      "delta_two_theta": delta, "observed_FWHM_deg": float(obs_width),
                      "calculated_FWHM_deg": float(model_width)})
    median_offset = float(np.median(offsets)) if len(offsets) >= 3 else None
    width_ratio = float(np.median(width_ratios)) if len(width_ratios) >= 3 else None
    if median_offset is not None and abs(median_offset) > .04:
        messages.append(f"Matched strong maxima have median observed-minus-calculated shift {median_offset:+.4f}°. Check wavelength, cell and the appropriate zero/sample-height correction.")
    if width_ratio is not None and width_ratio > 1.3:
        messages.append(f"Observed strong-peak widths are about {width_ratio:.2f} times calculated widths. The current profile may be too narrow; check instrument and calibrated sample broadening.")
    elif width_ratio is not None and width_ratio < .75:
        messages.append(f"Observed strong-peak widths are about {width_ratio:.2f} times calculated widths. The current profile may be too broad.")
    peak_region = mask & (net_calc >= max(float(np.max(net_calc[mask])), 1e-12) * .02)
    total_sse = float(np.sum(weights[mask] * residual[mask]**2))
    peak_sse = float(np.sum(weights[peak_region] * residual[peak_region]**2))
    dw = statistics.get("durbin_watson")
    if dw is not None and (dw < 1.2 or dw > 2.8):
        messages.append(f"Standardized residuals show serial structure (Durbin–Watson {dw:.3f}). Inspect systematic peak-shape/position errors and correlated processing noise.")
    if len(observed_peaks) and len(model_peaks) < max(1, len(observed_peaks) // 3):
        messages.append("The calculated profile has few of the observed prominent maxima. Recheck the confirmed phase model, wavelength and starting cell; additional iterations alone may not correct this.")
    messages.append("Assess radiation, symmetry/stoichiometry, impurities, texture and instrument calibration using the full observed/calculated/difference plot. A small R factor or a converged optimizer does not prove the structural model.")
    return json_safe({"messages": messages, "residual_RMSE_input_units": statistics["residual_RMSE_input_units"],
        "negative_observations": int(np.sum(observed[mask] < 0)),
        "baseline_noise_MAD_input_units": noise,
        "baseline_noise_assumption": "Diagnostic only: robust adjacent-difference estimate in modeled baseline; not propagated counting uncertainty and never used to change fit weights.",
        "approximate_homoscedastic_baseline_noise_Rwp_percent": approximate_rwp_noise,
        "median_peak_offset_deg": median_offset, "median_observed_calculated_FWHM_ratio": width_ratio,
        "strong_peak_comparisons": pairs, "modeled_peak_region_weighted_SSE_fraction": peak_sse / total_sse if total_sse > 0 else None,
        "statistical_interpretation": statistics.get("statistical_interpretation"),
        "strong_observed_maxima": int(len(observed_peaks)), "strong_calculated_maxima": int(len(model_peaks))})

