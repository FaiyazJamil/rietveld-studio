from __future__ import annotations

import math

import numpy as np
from scipy.signal import find_peaks


def profile_statistics(yobs, ycalc, weights, mask, n_parameters: int) -> dict:
    """Conventional full-profile R factors including background, on included points."""
    yobs, ycalc, weights = [np.asarray(a, dtype=float) for a in (yobs, ycalc, weights)]
    mask = np.asarray(mask, dtype=bool)
    mask &= np.isfinite(yobs) & np.isfinite(ycalc) & np.isfinite(weights) & (weights > 0)
    n = int(mask.sum())
    dof = n - n_parameters
    if dof <= 0:
        raise ValueError("No residual degrees of freedom; reduce parameters or increase fit observations.")
    obs, calc, w = yobs[mask], ycalc[mask], weights[mask]
    residual = obs - calc
    sse = float(np.dot(w, residual**2))
    denominator = float(np.dot(w, obs**2))
    absolute_denominator = float(np.abs(obs).sum())
    if denominator <= 0 or absolute_denominator <= 0:
        raise ValueError("R factors are undefined for this pattern.")
    rwp = 100 * math.sqrt(sse / denominator)
    rexp = 100 * math.sqrt(dof / denominator)
    standardized = np.zeros_like(yobs)
    standardized[mask] = (yobs[mask] - ycalc[mask]) * np.sqrt(weights[mask])
    adjacent = mask[1:] & mask[:-1]
    dw = float(np.sum(np.diff(standardized)[adjacent]**2) / sse) if sse > 0 else None
    return {"Rp_percent": float(100 * np.abs(residual).sum() / absolute_denominator),
            "Rwp_percent": rwp, "Rexp_percent": rexp, "chi2_reduced": sse / dof,
            "weighted_SSE": sse, "goodness_of_fit": math.sqrt(sse / dof),
            "n_observations": n, "n_parameters": int(n_parameters), "degrees_of_freedom": dof,
            "durbin_watson": dw,
            "residual_RMSE_input_units": float(np.sqrt(np.mean(residual**2))),
            "mean_absolute_residual_input_units": float(np.mean(np.abs(residual))),
            "weighted_RMS_input_units": float(np.sqrt(sse / w.sum())),
            "definition": "Full profile including background; only included points, w=1/sigma². chi2_reduced=(Rwp/Rexp)²; GOF=sqrt(chi2_reduced)."}


def correlation_diagnostics(covariance, labels, threshold=0.9) -> tuple[list[dict], np.ndarray]:
    matrix = np.asarray(covariance, dtype=float)
    if matrix.shape != (len(labels), len(labels)):
        return [], np.empty((0, 0))
    sd = np.sqrt(np.maximum(np.diag(matrix), 0))
    denominator = np.outer(sd, sd)
    correlations = np.divide(matrix, denominator, out=np.zeros_like(matrix), where=denominator > 0)
    rows = [{"parameter_1": labels[i], "parameter_2": labels[j], "correlation": float(correlations[i, j])}
            for i in range(len(labels)) for j in range(i + 1, len(labels))
            if np.isfinite(correlations[i, j]) and abs(correlations[i, j]) >= threshold]
    return sorted(rows, key=lambda r: -abs(r["correlation"])), correlations


def associate_peaks(x, y, background, mask, reflections, *, tolerance=0.15, prominence_fraction=0.025):
    """Geometric associations to confirmed phases, never independent phase identification."""
    x, y, background = [np.asarray(a, dtype=float) for a in (x, y, background)]
    signal = y - background
    active = signal[np.asarray(mask, dtype=bool)]
    if len(active) < 3:
        return []
    threshold = max(float(np.ptp(active)) * prominence_fraction, np.finfo(float).eps)
    spacing = float(np.median(np.diff(x)))
    # No smoothing or intensity changes: these are observed local maxima.
    indices, properties = find_peaks(signal, prominence=threshold, distance=max(1, int(0.06 / spacing)))
    result = []
    allowed = [r for r in reflections if r.get("Icalc", r.get("intensity", 0)) > 0]
    for p, prominence in zip(indices, properties["prominences"]):
        if not mask[p]:
            continue
        matches = [r for r in allowed if abs(r["two_theta"] - x[p]) <= tolerance]
        matches.sort(key=lambda r: abs(r["two_theta"] - x[p]))
        if matches:
            best = matches[0]
            assignments = "; ".join(f"{r['phase']} ({r['h']} {r['k']} {r['l']}) {r.get('component', 'Kα1')}" for r in matches)
            sources = "; ".join(dict.fromkeys(r.get("source_url", "local CIF") or "local CIF" for r in matches))
            result.append({"observed_two_theta": float(x[p]), "height_above_background": float(signal[p]),
                "prominence": float(prominence), "status": "ambiguous/overlap" if len(matches) > 1 else "associated",
                "assignments": assignments, "nearest_calculated_two_theta": best["two_theta"],
                "delta_two_theta": float(x[p] - best["two_theta"]), "source_urls": sources})
        else:
            result.append({"observed_two_theta": float(x[p]), "height_above_background": float(signal[p]),
                "prominence": float(prominence), "status": "unassigned", "assignments": "",
                "nearest_calculated_two_theta": None, "delta_two_theta": None, "source_urls": ""})
    return result


def json_safe(value):
    """Never emit nonstandard NaN/Infinity JSON or stringify numeric arrays."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [json_safe(x) for x in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)

