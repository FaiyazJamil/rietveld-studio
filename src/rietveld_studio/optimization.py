"""Repeated GSAS-II stages with bounded independent starts and complete audit history."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .analysis import json_safe
from .initialization import apply_start, background_strategy, initial_background_and_scale, starting_trials


def max_shift_su(cov):
    shifts = cov.get("Rvals", {}).get("lastShifts", {})
    ratios = [abs(float(shifts[name]) / float(su)) for name, su in
              zip(cov.get("varyList", []), cov.get("sig", []))
              if name in shifts and su is not None and float(su) > 0 and math.isfinite(float(su))]
    return max(ratios) if ratios else None


def stability(previous_rwp, rwp, cov, recipe):
    relative = abs(rwp - previous_rwp) / max(abs(previous_rwp), 1e-12) if previous_rwp is not None else None
    shift = max_shift_su(cov)
    stable = relative is not None and relative <= recipe.rwp_relative_tolerance
    # Parameter convergence is separate from a nearly unchanged objective.
    parameters_stable = shift is not None and shift <= recipe.shift_su_tolerance
    return stable and parameters_stable, relative, shift


def _write_histories(output, trials, iterations):
    for name, payload in (("trial_history.json", trials), ("iteration_history.json", iterations)):
        target = Path(output) / name
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(json_safe(payload), indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(target)


def optimize(g2, base_project, config, powder, mask, initial_cells, stages, apply_stage, physical_issues,
             emit):
    output = Path(config.output_dir)
    base = output / "starting_model.gpx"
    base_project.save(str(base))
    trials, notes = starting_trials(config, powder, mask, base_project.histogram(0).InstrumentParameters)
    background = background_strategy(config)
    if background["effective_mode"] == "subtracted":
        notes.append(f"Background-subtracted mode: fit at most {background['effective_terms']} residual-background coefficients. Negative observations are retained.")
    iterations, summaries = [], []
    winner = None
    winner_score = math.inf
    winner_history = []
    winner_notes = []
    for trial_number, trial in enumerate(trials, 1):
        directory = output / "trials" / f"{trial_number:02d}_{trial['name']}"
        directory.mkdir(parents=True, exist_ok=True)
        filename = directory / "refinement.gpx"
        checkpoint_dir = directory / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)
        history, trial_notes = [], []
        emit(kind="trial", trial=trial_number, trial_total=len(trials), message=f"Starting trial {trial_number}/{len(trials)}: {trial['name']}")
        summary = dict(trial, trial=trial_number, success=False)
        try:
            gpx = g2.G2Project(str(base), newgpx=str(filename))
            apply_start(gpx, trial, config)
            if config.recipe.auto_initialize:
                initial_background_and_scale(gpx, powder, mask, background["effective_terms"], config.recipe.cycles)
            gpx.save(str(filename))
            last_accepted = None
            for stage_number, stage in enumerate(stages, 1):
                emit(kind="stage", stage=stage, index=stage_number, total=len(stages),
                     trial=trial_number, trial_total=len(trials), message=f"Trial {trial_number}/{len(trials)} · {stage.replace('_', ' ')}")
                before = checkpoint_dir / f"{stage_number:02d}_before_{stage}.gpx"
                best_file = checkpoint_dir / f"{stage_number:02d}_best_{stage}.gpx"
                gpx.save(str(before))
                gpx.save(str(filename))
                stage_best = math.inf
                best_pass = None
                previous_pass = None
                stable_count = 0
                stopped = "maximum passes"
                accepted_passes = 0
                try:
                    apply_stage(gpx, stage, config)
                    for pass_number in range(1, config.recipe.max_passes + 1):
                        gpx.data["Covariance"]["data"] = {}
                        gpx.refine(makeBack=False)
                        cov = gpx.data.get("Covariance", {}).get("data", {})
                        if not cov.get("Rvals") or not len(cov.get("varyList", [])):
                            raise RuntimeError("GSAS-II did not produce a new covariance/result.")
                        rwp = float(gpx.histogram(0).get_wR())
                        if not math.isfinite(rwp):
                            raise RuntimeError("Nonfinite Rwp.")
                        issues = physical_issues(gpx, initial_cells, powder.x[mask])
                        if issues:
                            raise RuntimeError("; ".join(issues))
                        limit = last_accepted * (1 + config.recipe.max_stage_rwp_increase) if last_accepted is not None else math.inf
                        accepted = rwp <= limit and (not math.isfinite(stage_best) or rwp <= stage_best * (1 + config.recipe.max_stage_rwp_increase))
                        converged, relative, shift = stability(previous_pass, rwp, cov, config.recipe)
                        row = {"trial": trial_number, "trial_name": trial["name"], "stage": stage,
                               "pass": pass_number, "Rwp_percent": rwp,
                               "weighted_SSE": float(cov["Rvals"]["chisq"]),
                               "n_parameters": len(cov["varyList"]), "max_shift_over_su": shift,
                               "relative_Rwp_change": relative, "engine_converged": cov["Rvals"].get("converged"),
                               "accepted": accepted, "best_in_stage": False}
                        if not accepted:
                            row["reason"] = "Objective worsened beyond the rollback threshold"
                            iterations.append(row)
                            emit(kind="iteration", **row)
                            stopped = row["reason"]
                            break
                        accepted_passes += 1
                        # Save the smallest objective; permit tiny numerical plateaus when the later
                        # covariance/parameter shifts are better determined.
                        numerical_plateau = math.isfinite(stage_best) and abs(rwp - stage_best) <= max(1e-8, stage_best * 1e-6)
                        if rwp < stage_best or numerical_plateau and shift is not None and shift <= config.recipe.shift_su_tolerance:
                            stage_best = min(stage_best, rwp)
                            gpx.save(str(best_file))
                            gpx.save(str(filename))
                            best_pass = pass_number
                            row["best_in_stage"] = True
                        stable_count = stable_count + 1 if converged else 0
                        iterations.append(row)
                        emit(kind="iteration", **row, best_Rwp_percent=min(stage_best, winner_score))
                        _write_histories(output, summaries, iterations)
                        previous_pass = rwp
                        if pass_number >= config.recipe.min_passes and stable_count >= config.recipe.stable_passes:
                            stopped = "Rwp and parameter shifts converged"
                            break
                    if accepted_passes == 0 or not best_file.exists():
                        raise RuntimeError(stopped)
                    gpx = g2.G2Project(str(best_file), newgpx=str(filename))
                    gpx.save()
                    last_accepted = float(gpx.histogram(0).get_wR())
                    selected_cov = gpx.data["Covariance"]["data"]
                    history.append({"stage": stage, "accepted": True, "Rwp_percent": last_accepted,
                        "passes": pass_number, "selected_pass": best_pass,
                        "n_parameters": len(selected_cov["varyList"]),
                        "max_shift_over_su": max_shift_su(selected_cov),
                        "converged": stopped == "Rwp and parameter shifts converged",
                        "message": stopped})
                except Exception as exc:
                    if accepted_passes and best_file.exists():
                        gpx = g2.G2Project(str(best_file), newgpx=str(filename))
                        gpx.save()
                        last_accepted = float(gpx.histogram(0).get_wR())
                        history.append({"stage": stage, "accepted": True, "Rwp_percent": last_accepted,
                            "passes": accepted_passes, "selected_pass": best_pass, "converged": False,
                            "message": f"Later pass failed; kept best valid pass: {exc}"})
                    elif last_accepted is None:
                        raise RuntimeError(f"Initial background/scale refinement failed: {exc}") from exc
                    else:
                        gpx = g2.G2Project(str(before), newgpx=str(filename))
                        gpx.save()
                        history.append({"stage": stage, "accepted": False, "Rwp_percent": last_accepted,
                            "converged": False, "message": str(exc)})
                    trial_notes.append(f"Stage {stage}: {history[-1]['message']}")
                emit(kind="stage_done", **history[-1], trial=trial_number, trial_total=len(trials))
                (directory / "stage_history.json").write_text(json.dumps(json_safe(history), indent=2), encoding="utf-8")
            score = float(gpx.histogram(0).get_wR())
            summary.update(success=True, Rwp_percent=score, weighted_SSE=float(gpx.data["Covariance"]["data"]["Rvals"]["chisq"]),
                           project=str(filename.relative_to(output)), stages_accepted=sum(row["accepted"] for row in history))
            if score < winner_score:
                winner_score, winner = score, filename
                winner_history, winner_notes = list(history), list(trial_notes)
        except Exception as exc:
            summary["error"] = str(exc)
            emit(kind="trial_failed", trial=trial_number, message=str(exc))
        summaries.append(summary)
        _write_histories(output, summaries, iterations)
    if winner is None:
        raise RuntimeError("All starting trials failed. " + "; ".join(s.get("error", "") for s in summaries))
    gpx = g2.G2Project(str(winner), newgpx=str(output / "refinement.gpx"))
    gpx.save()
    for row in summaries:
        row["selected"] = row.get("project") == str(winner.relative_to(output))
    _write_histories(output, summaries, iterations)
    (output / "stage_history.json").write_text(json.dumps(json_safe(winner_history), indent=2), encoding="utf-8")
    cov = gpx.data["Covariance"]["data"]
    shift = max_shift_su(cov)
    final = winner_history[-1]
    convergence = {"converged": bool(final.get("converged")) and shift is not None and shift <= config.recipe.shift_su_tolerance,
        "max_shift_over_su": shift, "shift_su_tolerance": config.recipe.shift_su_tolerance,
        "rwp_relative_tolerance": config.recipe.rwp_relative_tolerance,
        "stop_reason": final.get("message"), "selected_trial": next(r["trial"] for r in summaries if r["selected"]),
        "attempted_trials": len(summaries), "completed_refinement_passes": len(iterations),
        "background_strategy": background}
    return gpx, winner_history, notes + winner_notes, summaries, iterations, convergence

