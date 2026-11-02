"""Generate a deterministic *synthetic* dataset using the actual GSAS-II forward model."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np

from rietveld_studio.engine import load_gsas, write_instrument
from rietveld_studio.models import InstrumentConfig, ProjectConfig
from rietveld_studio.structures import inspect_cif, phase_from_cif


def generate(destination, gsas_path="", cif=None, name="NaCl", true_a=5.6402):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    g2 = load_gsas(gsas_path)
    source = Path(cif or Path(__file__).resolve().parents[1] / "examples" / "NaCl_start.cif")
    instrument = InstrumentConfig(u=3, v=-1, w=7, x=0.5, y=0.5)
    instfile = destination / "synthetic_instrument.instprm"
    write_instrument(instrument, instfile)
    gpx = g2.G2Project(newgpx=str(destination / "synthetic_truth.gpx"))
    hist = gpx.add_simulated_powder_histogram("SYNTHETIC test pattern", str(instfile), 15, 110,
                                            Tstep=.025, scale=30)
    phase = gpx.add_phase(str(source), phasename=name, histograms=[hist], fmthint="CIF")
    if name == "NaCl":
        phase.data["General"]["Cell"][1:4] = [true_a] * 3
        phase.data["General"]["Cell"][7] = true_a**3
    phase.set_refinements({"Cell": False, "Atoms": {"all": ""}})
    phase.set_HAP_refinements({"Scale": False})
    hist.set_refinements({"Background": {"no. coeffs": 3, "coeffs": [90., -15., 5.], "refine": False}})
    gpx.set_Controls("cycles", 0)
    gpx.do_refinements([{}])
    x = np.asarray(gpx.histogram(0).getdata("X"))
    expected = np.asarray(gpx.histogram(0).getdata("Ycalc"))
    if not np.max(expected) > 100:
        raise RuntimeError("GSAS-II did not generate a useful simulation.")
    rng = np.random.default_rng(260631)
    observed = rng.poisson(np.maximum(expected, 1)).astype(float)
    sigma = np.sqrt(np.maximum(observed, 1))
    data = destination / "SYNTHETIC_NaCl.xye"
    np.savetxt(data, np.column_stack([x, observed, sigma]), fmt="%.10g",
               header="SYNTHETIC SOFTWARE TEST — not experimental data; 2theta intensity sigma")
    import shutil
    start_cif = destination / "NaCl_start.cif"
    if source.resolve() != start_cif:
        shutil.copy2(source, start_cif)
    config = ProjectConfig(name="SYNTHETIC NaCl validation", powder_path=str(data),
        powder_options={"uncertainty": "column", "sigma_col": 2},
        phases=[phase_from_cif(start_cif, inspect_cif(start_cif)[0])],
        instrument=InstrumentConfig(w=5, u=2, v=-1, x=.2, y=.2),
        output_dir=str(destination / "refined_run"), gsas_path=gsas_path)
    config.recipe.background_terms = 3
    config.save(destination / "demo.rsv.json")
    (destination / "TRUTH.json").write_text(json.dumps({"synthetic": True, "seed": 260631,
        "true_a_A": true_a, "true_space_group": "F m -3 m", "source": "GSAS-II forward simulation",
        "instrument": instrument.__dict__}, indent=2), encoding="utf-8")
    return destination / "demo.rsv.json"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destination", default="examples/synthetic_nacl")
    p.add_argument("--gsas-path", default="")
    args = p.parse_args()
    print(generate(args.destination, args.gsas_path))

