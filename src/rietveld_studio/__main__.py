from __future__ import annotations

import argparse
import os
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rietveld Studio — Python desktop XRD refinement with GSAS-II")
    parser.add_argument("--project", help="Open a saved .rsv.json project")
    parser.add_argument("--results", help="Open an existing result folder")
    parser.add_argument("--refine", metavar="PROJECT", help="Run a saved project without the GUI")
    parser.add_argument("--doctor", action="store_true", help="Check GSAS-II and compiled numerical modules")
    parser.add_argument("--gsas-path", default=os.environ.get("GSASII_PATH", ""))
    parser.add_argument("--origin", metavar="RESULT_FOLDER", help="Export an existing refinement to native .opju on Windows")
    args = parser.parse_args(argv)
    if args.doctor:
        from .engine import worker_main
        return worker_main(["--doctor", "--gsas-path", args.gsas_path])
    if args.refine:
        from .engine import worker_main
        if args.gsas_path:
            from .models import ProjectConfig
            project = ProjectConfig.load(args.refine)
            project.gsas_path = args.gsas_path
            # Retain original project; command-line override is saved in a new request file.
            path = Path(project.output_dir) / "cli_request.rsv.json"
            project.save(path)
            return worker_main([str(path)])
        return worker_main([args.refine])
    if args.origin:
        from .origin_export import main as export
        return export([args.origin])
    from .gui import launch
    return launch(project=args.project, results=args.results)


if __name__ == "__main__":
    raise SystemExit(main())

