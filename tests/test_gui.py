from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QProcess, QSettings
from PySide6.QtWidgets import QApplication

from rietveld_studio.gui import STYLE, MainWindow
from rietveld_studio.models import ProjectConfig


def _pump(app, predicate, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(.01)
    raise AssertionError("Qt operation timed out")


def test_gui_project_state_roundtrip_and_pages(tmp_path):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "settings"))
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    project = ProjectConfig()
    project.recipe.excluded_ranges = [[10, 11], [15, 16]]
    project.recipe.refine_positions = True
    # A no-file project can be represented by the widgets without trying to load data.
    window.project_name.setText("Round trip")
    window.exclusions.setText("10:11;15:16")
    window.refine_positions.setChecked(True)
    actual = window.gather()
    assert actual.recipe.excluded_ranges == project.recipe.excluded_ranges
    assert actual.recipe.refine_positions
    for i in range(6):
        window.navigate(i)
        app.processEvents()
        assert window.pages.currentIndex() == i
    window.close()


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("GSASII_PATH"), reason="GSASII_PATH required")
def test_gui_drives_real_worker_and_loads_results(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("generate_gui_demo", root / "scripts" / "generate_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = module.generate(tmp_path / "example", os.environ["GSASII_PATH"])
    project = ProjectConfig.load(path)
    window = MainWindow()
    errors = []
    monkeypatch.setattr(window, "show_error", lambda message: errors.append(str(message)))
    window.show()
    window.apply_project(project)
    window.engine_python.setText(sys.executable)
    window.auto_origin.setChecked(False)
    _pump(app, lambda: not window.tasks)
    assert window.powder is not None
    window.check_engine()
    _pump(app, lambda: window.process.state() == QProcess.ProcessState.NotRunning)
    assert window.engine_ok, window.log.toPlainText()
    window.run()
    _pump(app, lambda: window.process.state() == QProcess.ProcessState.NotRunning)
    assert not errors, errors
    assert window.result is not None, window.log.toPlainText()
    assert window.progress.value() == 100
    assert window.pages.currentIndex() == 4
    assert window.lattice_table.rowCount() == 7
    assert window.reflections_table.rowCount() >= 10
    window.close()

