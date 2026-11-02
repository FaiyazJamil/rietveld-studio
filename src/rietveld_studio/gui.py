from __future__ import annotations

import json
import os
import platform
import sys
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import __author__, __citation__, __version__
from .cod import CODClient
from .models import InstrumentConfig, ProjectConfig, RecipeConfig
from .powder import load_powder
from .reports import convergence_figure, refinement_figure
from .structures import inspect_cif, phase_from_cif, preview_reflections

STYLE = """
QMainWindow, QDialog {background:#f3f6fa;color:#253345;}
QWidget {font-family:'Segoe UI','Arial';font-size:13px;color:#253345;}
QLabel#Brand {font-size:23px;font-weight:700;letter-spacing:-0.5px;color:#102c42;}
QLabel#Eyebrow {font-size:11px;font-weight:700;color:#238276;letter-spacing:2px;}
QLabel#Title {font-size:26px;font-weight:700;color:#173248;}
QLabel#Subtitle {color:#687a8d;font-size:13px;}
QFrame#Sidebar {background:#132f43;border:0;}
QFrame#Sidebar QLabel {color:#e1ebf2;}
QFrame#Sidebar QLabel#Brand {font-size:20px;color:white;}
QListWidget#Navigation {background:transparent;border:0;outline:0;color:#bdcdd9;font-size:14px;}
QListWidget#Navigation::item {padding:15px 10px;margin:4px 0;border-radius:7px;}
QListWidget#Navigation::item:selected {background:#285369;color:white;}
QListWidget#Navigation::item:hover {background:#20475b;}
QGroupBox {background:white;border:1px solid #dce5ed;border-radius:10px;margin-top:16px;padding:18px 13px 12px;font-weight:600;}
QGroupBox::title {subcontrol-origin:margin;left:13px;padding:0 5px;color:#39576c;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox {background:white;border:1px solid #cdd9e3;border-radius:6px;min-height:28px;padding:3px 8px;selection-background-color:#238276;}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus {border:1px solid #25897d;}
QPushButton {background:white;border:1px solid #cbd8e3;border-radius:7px;padding:9px 14px;font-weight:600;}
QPushButton:hover {background:#eaf2f6;border-color:#9db8c9;}
QPushButton:disabled {color:#9eacb8;background:#edf1f5;border-color:#dbe3e9;}
QPushButton#Primary {background:#218376;border:1px solid #218376;color:white;}
QPushButton#Primary:hover {background:#176f64;}
QPushButton#Primary:disabled {background:#96bdb7;border-color:#96bdb7;}
QPushButton#Danger {background:#fff4f2;color:#b54944;border-color:#e4bab6;}
QTableWidget {background:white;border:1px solid #dce5ed;border-radius:7px;gridline-color:#edf1f5;alternate-background-color:#f7f9fb;selection-background-color:#d7eee9;selection-color:#173248;}
QHeaderView::section {background:#edf3f7;color:#456176;border:0;border-bottom:1px solid #dce5ed;padding:9px;font-weight:600;}
QTabWidget::pane {border:1px solid #dce5ed;background:white;border-radius:7px;}
QTabBar::tab {background:#e8eef4;padding:10px 15px;border:0;margin-right:3px;}
QTabBar::tab:selected {background:white;color:#218376;font-weight:700;}
QPlainTextEdit,QTextBrowser {background:white;border:1px solid #dce5ed;border-radius:7px;padding:8px;}
QCheckBox {spacing:7px;padding:3px;}
QProgressBar {border:0;border-radius:5px;background:#e2eaf1;min-height:8px;max-height:12px;text-align:center;}
QProgressBar::chunk {background:#238276;border-radius:5px;}
QLabel#Status {background:#e7f2ef;color:#24766a;border-radius:7px;padding:8px 12px;}
QLabel#Metric {font-size:27px;font-weight:700;color:#193b53;}
"""


class Task(QThread):
    done = Signal(object)
    error = Signal(str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            self.done.emit(self.function())
        except Exception as exc:
            self.error.emit(f"{exc}\n\n{traceback.format_exc()}")


def button(text, callback, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("Primary")
    widget.clicked.connect(callback)
    return widget


def note(text):
    label = QLabel(text)
    label.setObjectName("Subtitle")
    label.setWordWrap(True)
    return label


def double(value, minimum, maximum, decimals=5, step=.01):
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    return box


def integer(value, minimum, maximum):
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    return box


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setAlternatingRowColors(True)
    widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    widget.verticalHeader().setVisible(False)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    widget.horizontalHeader().setStretchLastSection(True)
    widget.resizeColumnsToContents()
    return widget


def populate(widget, rows):
    widget.setSortingEnabled(False)
    widget.setRowCount(len(rows))
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            if isinstance(value, (float, np.floating)):
                value = f"{value:.7g}"
            item = QTableWidgetItem("—" if value is None else str(value))
            item.setToolTip(item.text())
            widget.setItem(row, column, item)
    widget.resizeColumnsToContents()
    for i in range(widget.columnCount()):
        widget.setColumnWidth(i, min(360, max(75, widget.columnWidth(i))))


class StructureDialog(QDialog):
    def __init__(self, path, records, parent=None, metadata=None):
        super().__init__(parent)
        self.path, self.records, self.metadata = path, records, metadata or {}
        self.setWindowTitle("Review and confirm crystal structure")
        self.resize(840, 670)
        layout = QVBoxLayout(self)
        layout.addWidget(note("Confirm the composition, space group, cell, and atomic sites before adding this phase. A matching formula alone does not identify a polymorph or oxidation state."))
        form = QFormLayout()
        self.blocks = QComboBox()
        for record in records:
            self.blocks.addItem(f"{record['block_name']}   |   {record['formula']}   |   {record['space_group']}")
        self.name = QLineEdit()
        form.addRow("CIF data block", self.blocks)
        form.addRow("Phase name", self.name)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        form.addRow("Cell and source", self.summary)
        layout.addLayout(form)
        self.sites = table(["Site", "Element", "x", "y", "z", "Occupancy", "Uiso (Å²)"])
        layout.addWidget(self.sites, 1)
        self.warning = note("")
        layout.addWidget(self.warning)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        controls.button(QDialogButtonBox.StandardButton.Ok).setText("Confirm and add phase")
        controls.accepted.connect(self.accept)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
        self.blocks.currentIndexChanged.connect(self.update_record)
        self.update_record(0)

    def update_record(self, index):
        record = self.records[index]
        self.name.setText(record["formula"] or record["name"])
        values = record["cell"]
        source = f"COD {self.metadata.get('cod_id')}" if self.metadata.get("cod_id") else "Local CIF"
        self.summary.setText(f"a = {values[0]:.6g} Å    b = {values[1]:.6g} Å    c = {values[2]:.6g} Å\n"
            f"α = {values[3]:.5g}°    β = {values[4]:.5g}°    γ = {values[5]:.5g}°    V = {values[6]:.6g} Å³\n{source}    DOI: {record.get('doi') or self.metadata.get('doi') or 'not supplied'}")
        populate(self.sites, [[s[k] for k in ("label", "element", "x", "y", "z", "occupancy", "u_iso")] for s in record["sites"]])
        self.warning.setText("\n".join(record["warnings"]))

    def phase(self):
        spec = phase_from_cif(self.path, self.records[self.blocks.currentIndex()], self.metadata)
        spec.name = self.name.text().strip()
        if not spec.name:
            raise ValueError("Enter a phase name.")
        return spec


class PlotPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = FigureCanvasQTAgg(Figure(figsize=(10, 6), layout="constrained"))
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas, 1)
        self.empty()

    def empty(self):
        self.canvas.figure.clear()
        axis = self.canvas.figure.add_subplot()
        axis.set_axis_off()
        axis.text(.5, .58, "Your diffraction pattern starts here", ha="center", va="center", fontsize=18, color="#47677d")
        axis.text(.5, .46, "Add confirmed phases, load powder data, then review the instrument and recipe.",
                  ha="center", va="center", fontsize=11, color="#8697a7")
        self.canvas.draw_idle()

    def replace(self, figure):
        self.layout.removeWidget(self.toolbar)
        self.layout.removeWidget(self.canvas)
        self.toolbar.deleteLater()
        self.canvas.deleteLater()
        self.canvas = FigureCanvasQTAgg(figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas, 1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Rietveld Studio {__version__}")
        self.resize(1480, 940)
        self.setMinimumSize(1080, 740)
        self.settings = QSettings("RietveldStudio", "RietveldStudio")
        self.phases = []
        self.candidates = []
        self.powder = None
        self.result = None
        self.result_dir = None
        self.tasks = []
        self.process = None
        self.process_mode = ""
        self.process_buffer = ""
        self.engine_ok = False
        self.live_iterations = []
        self.continued_from = ""
        self.last_error = ""
        self._build()
        self._menu()
        self._restore_settings()
        self.navigate(0)

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        horizontal = QHBoxLayout(central)
        horizontal.setContentsMargins(0, 0, 0, 0)
        horizontal.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(20, 28, 17, 24)
        brand = QLabel("Rietveld\nStudio")
        brand.setObjectName("Brand")
        left.addWidget(brand)
        tagline = QLabel("CRYSTAL STRUCTURE\nWORKSPACE")
        tagline.setStyleSheet("font-size:10px;letter-spacing:1px;color:#a6bdcc;")
        left.addWidget(tagline)
        left.addSpacing(26)
        self.nav = QListWidget()
        self.nav.setObjectName("Navigation")
        self.nav.addItems(["01   Crystal structures", "02   Powder data", "03   Instrument", "04   Refinement recipe", "05   Results & export", "06   Engine & run log"])
        self.nav.currentRowChanged.connect(self.navigate)
        left.addWidget(self.nav, 1)
        left.addWidget(note("GSAS-II refinement engine\nCOD crystal structures\nTraceable results"))
        horizontal.addWidget(sidebar)
        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(27, 22, 27, 18)
        layout.setSpacing(12)
        top = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("Title")
        top.addWidget(self.title, 1)
        self.status = QLabel("Setup required")
        self.status.setObjectName("Status")
        top.addWidget(self.status)
        layout.addLayout(top)
        self.subtitle = note("")
        layout.addWidget(self.subtitle)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self._structures_page()
        self._powder_page()
        self._instrument_page()
        self._recipe_page()
        self._results_page()
        self._engine_page()
        footer = QHBoxLayout()
        self.readiness = note("0 phases  ·  no powder data")
        footer.addWidget(self.readiness, 1)
        self.save_button = button("Save project", self.save_project)
        footer.addWidget(self.save_button)
        self.cancel_button = button("Stop run", self.stop_run)
        self.cancel_button.setObjectName("Danger")
        self.cancel_button.setEnabled(False)
        footer.addWidget(self.cancel_button)
        self.run_button = button("Run automatic refinement", self.run, True)
        footer.addWidget(self.run_button)
        layout.addLayout(footer)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        horizontal.addWidget(right, 1)

    def _page(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 3, 0, 0)
        layout.setSpacing(12)
        self.pages.addWidget(widget)
        return layout

    def navigate(self, index):
        if index < 0 or not hasattr(self, "pages"):
            return
        self.pages.setCurrentIndex(index)
        self.nav.setCurrentRow(index)
        titles = [("Crystal structures", "Find the right structural model and explicitly confirm each phase."),
            ("Powder diffraction data", "Preview the raw pattern and declare how its uncertainties should be weighted."),
            ("Instrument & radiation", "Match the actual measurement geometry, wavelength, and instrumental profile."),
            ("Refinement recipe", "Release parameters in stages, with checkpoints and physical-model diagnostics."),
            ("Results & export", "Inspect the structural model, fit diagnostics, and traceable reflection assignments."),
            ("Engine & run log", "Verify the numerical backend and follow the complete refinement log.")]
        self.title.setText(titles[index][0])
        self.subtitle.setText(titles[index][1])
        if hasattr(self, "readiness"):
            self.update_readiness()

    def _structures_page(self):
        layout = self._page()
        search = QGroupBox("Search the Crystallography Open Database")
        form = QGridLayout(search)
        self.query = QLineEdit()
        self.query.setPlaceholderText("LiFePO4, LiMn0.6Fe0.4PO4, NMC622, silicon, or a COD ID")
        self.query.returnPressed.connect(self.search_cod)
        self.search_mode = QComboBox()
        self.search_mode.addItems(["Chemical formula", "Compound / mineral name", "COD ID"])
        self.exact_elements = QCheckBox("Require the same element set")
        self.exact_elements.setChecked(True)
        self.search_button = button("Search COD", self.search_cod, True)
        form.addWidget(self.query, 0, 0, 1, 2)
        form.addWidget(self.search_mode, 0, 2)
        form.addWidget(self.search_button, 0, 3)
        form.addWidget(self.exact_elements, 1, 0, 1, 2)
        form.addWidget(button("Import local CIF…", self.import_cif), 1, 3)
        layout.addWidget(search)
        self.search_notice = note("Search results may include polymorphs, different stoichiometries, temperatures, and literature models. Review the selected CIF before adding it.")
        layout.addWidget(self.search_notice)
        self.candidate_table = table(["COD ID", "Formula", "Space group", "a (Å)", "b (Å)", "c (Å)", "Year", "Composition distance", "DOI / name"])
        self.candidate_table.doubleClicked.connect(self.choose_candidate)
        layout.addWidget(self.candidate_table, 3)
        actions = QHBoxLayout()
        actions.addWidget(button("Open selected COD source", self.open_candidate_source))
        actions.addStretch()
        self.confirm_candidate = button("Review selected CIF…", self.choose_candidate)
        actions.addWidget(self.confirm_candidate)
        layout.addLayout(actions)
        phases = QGroupBox("Confirmed phases in this model")
        pl = QVBoxLayout(phases)
        self.phase_table = table(["Phase name", "Formula", "Space group", "Source", "Refine cell"])
        self.phase_table.setMaximumHeight(170)
        pl.addWidget(self.phase_table)
        controls = QHBoxLayout()
        controls.addWidget(button("Rename phase", self.rename_phase))
        controls.addWidget(button("Inspect CIF", self.inspect_phase))
        controls.addWidget(button("Toggle cell refinement", self.toggle_phase_cell))
        controls.addStretch()
        controls.addWidget(button("Remove phase", self.remove_phase))
        pl.addLayout(controls)
        layout.addWidget(phases, 2)

    def _powder_page(self):
        layout = self._page()
        row = QHBoxLayout()
        self.powder_path = QLineEdit()
        self.powder_path.setPlaceholderText("XY, XYE, CSV, TSV, DAT, TXT, or single-scan XRDML")
        row.addWidget(self.powder_path, 1)
        row.addWidget(button("Browse powder…", self.browse_powder))
        layout.addLayout(row)
        options = QGroupBox("Columns and uncertainty model")
        form = QGridLayout(options)
        self.x_col = integer(1, 1, 64)
        self.y_col = integer(2, 1, 64)
        self.sigma_col = integer(3, 1, 64)
        self.skip_rows = integer(0, 0, 100000)
        self.uncertainty = QComboBox()
        self.uncertainty.addItems(["Poisson counts", "Sigma column", "Constant sigma (descriptive)"])
        self.delimiter = QComboBox()
        self.delimiter.addItems(["auto", "whitespace", "comma", "tab", "semicolon"])
        self.constant_sigma = double(1, .000001, 1e9, decimals=6)
        self.sort_x = QCheckBox("Sort by increasing 2θ")
        widgets = [("2θ column (1-based)", self.x_col), ("Intensity column", self.y_col),
                   ("Sigma column", self.sigma_col), ("Skip initial rows", self.skip_rows),
                   ("Weighting", self.uncertainty), ("Delimiter", self.delimiter), ("Constant sigma", self.constant_sigma)]
        for i, (label, widget) in enumerate(widgets):
            form.addWidget(QLabel(label), i // 4 * 2, i % 4)
            form.addWidget(widget, i // 4 * 2 + 1, i % 4)
        form.addWidget(self.sort_x, 3, 3)
        form.addWidget(button("Load & validate pattern", self.load_pattern, True), 4, 3)
        layout.addWidget(options)
        self.powder_summary = note("For processed, normalized, or counts-per-second data, supply measured standard uncertainties. XRDML counts/CPS uncertainties are propagated from counting metadata.")
        layout.addWidget(self.powder_summary)
        self.input_plot = PlotPanel()
        layout.addWidget(self.input_plot, 1)
        self.preview_button = button("Overlay calculated CIF sticks", self.overlay_preview)
        layout.addWidget(self.preview_button)

    def _instrument_page(self):
        outer = self._page()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        calibration = QGroupBox("Instrument profile")
        cl = QFormLayout(calibration)
        self.instrument_path = QLineEdit()
        ir = QHBoxLayout()
        ir.addWidget(self.instrument_path)
        ir.addWidget(button("Load .instprm…", self.browse_instrument))
        cl.addRow("GSAS-II profile file", ir)
        self.calibrated = QCheckBox("This profile was calibrated using a suitable standard on this instrument")
        cl.addRow(self.calibrated)
        cl.addRow(note("A loaded .instprm overrides the numeric radiation/profile fields below. Confirm geometry and radius separately. Without a calibrated instrument profile, size/strain results are not enabled."))
        layout.addWidget(calibration)
        radiation = QGroupBox("Radiation and measurement geometry")
        form = QFormLayout(radiation)
        self.radiation = QComboBox()
        self.radiation.addItems(["Cu Kα1", "Cu Kα1 + Kα2", "Co Kα1", "Mo Kα1", "Custom wavelength"])
        self.wave = double(1.540593, .05, 5, 6)
        self.wave2 = double(1.544427, .05, 5, 6)
        self.doublet = QCheckBox("Include Kα2")
        self.ratio = double(.5, .0001, 1, 4)
        self.geometry = QComboBox()
        self.geometry.addItems(["Bragg-Brentano", "Debye-Scherrer"])
        self.radius = double(200, 1, 10000, 2)
        self.polarization = double(.5, 0, 1, 4)
        for label, widget in [("Radiation preset", self.radiation), ("λ1 / λ (Å)", self.wave),
             ("Kα2", self.doublet), ("λ2 (Å)", self.wave2), ("I(Kα2) / I(Kα1)", self.ratio),
             ("Geometry", self.geometry), ("Goniometer radius (mm)", self.radius), ("Polarization fraction", self.polarization)]:
            form.addRow(label, widget)
        self.radiation.currentIndexChanged.connect(self.set_radiation)
        layout.addWidget(radiation)
        profile = QGroupBox("Starting profile coefficients — GSAS-II conventions")
        form2 = QFormLayout(profile)
        self.profile_values = {}
        for key, value in [("U", 2), ("V", -1), ("W", 5), ("X", 0), ("Y", 0), ("SH/L", .002)]:
            widget = double(value, -.5e5 if key == "V" else 0, .5e5 if key != "SH/L" else 1, 6)
            self.profile_values[key] = widget
            form2.addRow(key, widget)
        form2.addRow(note("U, V, W describe Gaussian variance in centidegree²: U tan²θ + V tanθ + W. X and Y are Lorentzian terms in centidegrees. Defaults are starting guesses, not an instrument calibration."))
        layout.addWidget(profile)
        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _recipe_page(self):
        outer = self._page()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        run = QGroupBox("Project and output")
        form = QFormLayout(run)
        self.project_name = QLineEdit("Powder XRD refinement")
        self.output_root = QLineEdit(str(Path.home() / "RietveldStudio_results"))
        row = QHBoxLayout()
        row.addWidget(self.output_root)
        row.addWidget(button("Choose folder…", self.choose_output))
        form.addRow("Project name", self.project_name)
        form.addRow("Results root", row)
        form.addRow(note("Each run creates its own dated folder with inputs, checkpoints, the complete model, and export files."))
        layout.addWidget(run)
        optimizer = QGroupBox("Iterative refinement and independent starts")
        opt = QGridLayout(optimizer)
        self.max_passes = integer(6, 1, 30)
        self.min_passes = integer(2, 1, 30)
        self.stable_passes = integer(2, 1, 5)
        self.start_trials = integer(3, 1, 9)
        self.rwp_tolerance = double(.0001, .00000001, .02, 8, .0001)
        self.shift_tolerance = double(.10, .001, 1, 3, .01)
        self.cell_search = double(2, 0, 5, 2, .25)
        self.background_mode = QComboBox()
        self.background_mode.addItems(["Auto (filename hint)", "Raw / unsubtracted", "Background already subtracted"])
        self.auto_initialize = QCheckBox("Estimate starting scale, peak alignment and bounded profile-width starts")
        self.auto_initialize.setChecked(True)
        for i, (label, widget) in enumerate([
            ("Maximum calls per stage", self.max_passes), ("Minimum calls per stage", self.min_passes),
            ("Stable calls required", self.stable_passes), ("Independent starts", self.start_trials),
            ("Relative Rwp tolerance", self.rwp_tolerance), ("Maximum shift / su", self.shift_tolerance),
            ("Initial lattice search ± (%)", self.cell_search), ("Background treatment", self.background_mode)]):
            opt.addWidget(QLabel(label), (i // 3) * 2, i % 3)
            opt.addWidget(widget, (i // 3) * 2 + 1, i % 3)
        opt.addWidget(self.auto_initialize, 6, 0, 1, 3)
        opt.addWidget(note("The same observations, uncertainties and fit mask are used for every start. Refinement stops when both Rwp and parameter shifts settle, or the call limit is reached. Background-subtracted mode allows only a low-order residual background."), 7, 0, 1, 3)
        layout.addWidget(optimizer)
        split = QHBoxLayout()
        self.recipe_split = split
        general = QGroupBox("Fit model")
        gf = QFormLayout(general)
        self.background_terms = integer(6, 1, 24)
        self.cycles = integer(12, 1, 100)
        self.refine_cell = QCheckBox("Refine unit-cell parameters")
        self.refine_cell.setChecked(True)
        self.correction = QComboBox()
        self.correction.addItems(["None (keep calibration)", "Instrument zero", "Sample height (Bragg-Brentano)"])
        self.profile_mode = QComboBox()
        self.profile_mode.addItems(["Refine effective U/V/W, then X/Y", "Keep profile fixed", "Sample size/strain; instrument fixed"])
        self.refine_size = QCheckBox("Isotropic coherent-domain size")
        self.refine_strain = QCheckBox("Isotropic microstrain")
        self.preferred_orientation = QCheckBox("March-Dollase preferred orientation")
        self.orientation_axis = QLineEdit("0 0 1")
        self.refine_positions = QCheckBox("Refine atomic positions (advanced)")
        self.refine_uiso = QCheckBox("Refine isotropic atomic displacement (advanced)")
        self.refine_asymmetry = QCheckBox("Refine axial-divergence asymmetry (SH/L)")
        for label, widget in [("Background coefficients", self.background_terms), ("Max cycles per stage", self.cycles),
            ("Cell", self.refine_cell), ("Position correction", self.correction), ("Broadening strategy", self.profile_mode),
            ("Size", self.refine_size), ("Strain", self.refine_strain), ("Texture", self.preferred_orientation),
            ("Orientation axis [h k l]", self.orientation_axis), ("Atomic positions", self.refine_positions),
            ("Atomic displacement", self.refine_uiso), ("Peak asymmetry", self.refine_asymmetry)]:
            gf.addRow(label, widget)
        split.addWidget(general, 3)
        ranges = QGroupBox("Range, exclusions, and peak associations")
        rf = QFormLayout(ranges)
        self.fit_min = QLineEdit()
        self.fit_min.setPlaceholderText("Full range if blank")
        self.fit_max = QLineEdit()
        self.fit_max.setPlaceholderText("Full range if blank")
        self.exclusions = QLineEdit()
        self.exclusions.setPlaceholderText("e.g. 25.0:27.5; 44.0:45.0")
        self.tolerance = double(.15, .005, 2, 3, .01)
        self.prominence = double(.025, .001, .5, 3, .005)
        self.auto_origin = QCheckBox("Export native Origin project after fitting")
        self.auto_origin.setChecked(platform.system() == "Windows")
        for label, widget in [("Minimum 2θ (°)", self.fit_min), ("Maximum 2θ (°)", self.fit_max),
            ("Exclude 2θ intervals", self.exclusions), ("Peak match tolerance (°)", self.tolerance),
            ("Peak prominence / range", self.prominence), ("Origin", self.auto_origin)]:
            rf.addRow(label, widget)
        rf.addRow(note("Automatic stages: background/scale → optional position correction → cell → profile or calibrated sample broadening → optional texture/atomic parameters → final cycle. Failed or nonphysical stages are rolled back."))
        rf.addRow(note("Occupancies remain fixed to the confirmed CIF. Li vacancies, dopant distribution, and oxidation state need additional evidence and constrained modeling."))
        split.addWidget(ranges, 2)
        layout.addLayout(split, 1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _results_page(self):
        layout = self._page()
        metrics = QHBoxLayout()
        self.metric_values = {}
        self.metric_boxes = {}
        for label, key in [("Rwp", "Rwp_percent"), ("Rp", "Rp_percent"), ("Rexp", "Rexp_percent"),
                           ("Reduced χ²", "chi2_reduced"), ("GOF", "goodness_of_fit")]:
            frame = QGroupBox(label)
            fl = QVBoxLayout(frame)
            value = QLabel("—")
            value.setObjectName("Metric")
            fl.addWidget(value)
            self.metric_values[key] = value
            self.metric_boxes[key] = frame
            metrics.addWidget(frame)
        layout.addLayout(metrics)
        self.results_banner = note("Review the full profile and declared uncertainties alongside the R factors.")
        layout.addWidget(self.results_banner)
        self.result_tabs = QTabWidget()
        self.result_plot = PlotPanel()
        self.result_tabs.addTab(self.result_plot, "Refinement plot")
        self.convergence_plot = PlotPanel()
        self.convergence_plot.replace(convergence_figure({}))
        self.result_tabs.addTab(self.convergence_plot, "Convergence")
        self.iteration_table = table(["Start", "Stage", "Pass", "Rwp (%)", "Max shift/su", "Accepted"])
        self.result_tabs.addTab(self.iteration_table, "Iterations")
        self.lattice_table = table(["Phase", "Parameter", "Value", "Standard uncertainty", "Unit"])
        self.result_tabs.addTab(self.lattice_table, "Lattice")
        self.result_phase_table = table(["Phase", "Space group", "Density (g/cm³)", "Weight (%)", "Weight su (%)", "Size (nm)", "Strain (ppm)"])
        self.result_tabs.addTab(self.result_phase_table, "Phases")
        self.atom_table = table(["Phase", "Site", "Element", "x", "y", "z", "Occupancy", "Uiso (Å²)", "Biso (Å²)", "Flags"])
        self.result_tabs.addTab(self.atom_table, "Atoms")
        self.reflections_table = table(["Phase", "h", "k", "l", "2θ", "d (Å)", "Icalc", "Radiation", "Source", "DOI"])
        self.result_tabs.addTab(self.reflections_table, "hkl reflections")
        self.peaks_table = table(["Observed 2θ", "Status", "Assignments", "Nearest calculated 2θ", "Δ2θ", "Sources"])
        self.result_tabs.addTab(self.peaks_table, "Peak associations")
        self.parameter_table = table(["GSAS-II variable", "Value", "Standard uncertainty", "Last shift/su"])
        self.result_tabs.addTab(self.parameter_table, "Parameters")
        self.correlation_table = table(["Parameter 1", "Parameter 2", "Correlation"])
        self.result_tabs.addTab(self.correlation_table, "Correlations")
        self.diagnostics = QTextBrowser()
        self.result_tabs.addTab(self.diagnostics, "Diagnostics")
        layout.addWidget(self.result_tabs, 1)
        row = QHBoxLayout()
        row.addWidget(button("Open previous results…", self.open_results))
        row.addWidget(button("Open report", self.open_report))
        row.addWidget(button("Open result folder", self.open_result_folder))
        row.addWidget(button("Continue from this result", self.continue_result))
        row.addStretch()
        self.origin_button = button("Export Origin .opju…", self.export_origin, True)
        row.addWidget(self.origin_button)
        layout.addLayout(row)

    def _engine_page(self):
        layout = self._page()
        box = QGroupBox("GSAS-II execution environment")
        form = QFormLayout(box)
        self.engine_python = QLineEdit(sys.executable)
        self.gsas_path = QLineEdit(os.environ.get("GSASII_PATH", ""))
        root = Path(__file__).resolve().parents[2]
        if (root / ".engine" / "GSAS-II").is_dir() and not self.gsas_path.text():
            self.gsas_path.setText(str(root / ".engine" / "GSAS-II"))
        form.addRow("Engine Python executable", self.engine_python)
        form.addRow("GSAS-II source folder (optional)", self.gsas_path)
        form.addRow(button("Check engine installation", self.check_engine, True))
        self.engine_status = note("Run the engine check before your first refinement. The GUI remains responsive while refinement runs in a separate Python process.")
        form.addRow(self.engine_status)
        layout.addWidget(box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Live numerical log"))
        row.addStretch()
        row.addWidget(button("Copy log", lambda: QApplication.clipboard().setText(self.log.toPlainText())))
        layout.addLayout(row)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(14000)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.log.setFont(font)
        layout.addWidget(self.log, 1)

    def _menu(self):
        filemenu = self.menuBar().addMenu("File")
        for title, callback, shortcut in [("Open project…", self.open_project, "Ctrl+O"),
            ("Save project…", self.save_project, "Ctrl+S"), ("Open results…", self.open_results, ""),
            ("Quit", self.close, "Ctrl+Q")]:
            action = QAction(title, self)
            action.triggered.connect(callback)
            if shortcut:
                action.setShortcut(shortcut)
            filemenu.addAction(action)
        helpmenu = self.menuBar().addMenu("Help")
        for title, url in [("GSAS-II documentation", "https://gsas-ii.readthedocs.io/en/latest/GSASIIscriptable.html"),
            ("COD search documentation", "https://wiki.crystallography.net/RESTful_API/"),
            ("Origin automation documentation", "https://docs.originlab.com/python/")]:
            action = QAction(title, self)
            action.triggered.connect(lambda checked=False, url=url: QDesktopServices.openUrl(QUrl(url)))
            helpmenu.addAction(action)
        about = QAction("About Rietveld Studio", self)
        about.triggered.connect(lambda: QMessageBox.information(self, "About",
            f"Rietveld Studio {__version__}\nAuthor and maintainer: {__author__}\nLicense: MIT\n"
            "Guided constant-wavelength powder XRD refinement.\n"
            "Numerical engine: GSAS-II (Toby & Von Dreele).\n\n"
            f"Software citation:\n{__citation__}\n\n"
            "Review scientific diagnostics before interpreting any automatic fit."))
        helpmenu.addAction(about)

    def _restore_settings(self):
        for key, widget in [("engine_python", self.engine_python), ("gsas_path", self.gsas_path), ("output_root", self.output_root)]:
            if self.settings.value(key):
                widget.setText(str(self.settings.value(key)))

    def _task(self, function, done):
        task = Task(function, self)
        self.tasks.append(task)
        task.done.connect(done)
        task.error.connect(self.task_error)
        task.finished.connect(lambda: self._task_finished(task))
        task.start()

    def _task_finished(self, task):
        if task in self.tasks:
            self.tasks.remove(task)
        task.deleteLater()
        self.search_button.setEnabled(True)
        self.confirm_candidate.setEnabled(True)
        self.preview_button.setEnabled(True)

    def task_error(self, message):
        self.log.appendPlainText(message)
        self.show_error(message.split("\n\nTraceback")[0])

    def show_error(self, message):
        QMessageBox.warning(self, "Rietveld Studio", str(message))

    def search_cod(self):
        query = self.query.text().strip()
        mode = ["formula", "keyword", "id"][self.search_mode.currentIndex()]
        exact = self.exact_elements.isChecked()
        self.search_button.setEnabled(False)
        self.search_notice.setText("Searching COD… This may take a moment.")
        def work():
            client = CODClient()
            rows = client.search(query, mode=mode, exact_elements=exact)
            return rows, client.last_notice
        self._task(work, self.cod_results)

    def cod_results(self, payload):
        self.candidates, notice = payload
        populate(self.candidate_table, [[r.cod_id, r.formula, r.space_group, r.a, r.b, r.c, r.year,
            r.distance, r.doi or r.name] for r in self.candidates])
        if self.candidates:
            self.search_notice.setText(f"{len(self.candidates)} candidate structures. Composition distance 0 means the same normalized element ratios; it does not establish the same phase. Select a row to review. {notice}")
        else:
            self.search_notice.setText("No candidates found. Try a compound/mineral name, uncheck the exact element-set filter, search a likely parent phase, or import your CIF. The app never silently substitutes a different chemistry.")

    def choose_candidate(self, *unused):
        index = self.candidate_table.currentRow()
        if not 0 <= index < len(self.candidates):
            return self.show_error("Select a COD candidate first.")
        candidate = self.candidates[index]
        self.confirm_candidate.setEnabled(False)
        self.search_notice.setText(f"Downloading and validating COD {candidate.cod_id}…")
        def work():
            client = CODClient()
            path, metadata = client.download(candidate)
            return path, inspect_cif(path), metadata, client.last_notice
        self._task(work, self.confirm_download)

    def confirm_download(self, payload):
        path, records, metadata, notice = payload
        self.search_notice.setText(notice or "CIF downloaded. Review the source model before confirmation.")
        self.confirm_structure(path, records, metadata)

    def import_cif(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import crystal structure", "", "CIF files (*.cif);;All files (*)")
        if not path:
            return
        self._task(lambda: (path, inspect_cif(path), {}, ""), self.confirm_download)

    def confirm_structure(self, path, records, metadata=None):
        dialog = StructureDialog(path, records, self, metadata)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            phase = dialog.phase()
            if any(p.name == phase.name for p in self.phases):
                raise ValueError("A phase with this name already exists. Choose a unique phase name.")
            self.phases.append(phase)
            self.refresh_phases()
            self.status.setText("Phase confirmed · load powder data next")
        except Exception as exc:
            self.show_error(exc)

    def refresh_phases(self):
        populate(self.phase_table, [[p.name, p.formula, p.space_group, f"COD {p.cod_id}" if p.cod_id else "Local CIF",
            "Yes" if p.refine_cell else "No"] for p in self.phases])
        self.update_readiness()

    def open_candidate_source(self):
        i = self.candidate_table.currentRow()
        if 0 <= i < len(self.candidates):
            QDesktopServices.openUrl(QUrl(self.candidates[i].source_url))

    def remove_phase(self):
        i = self.phase_table.currentRow()
        if 0 <= i < len(self.phases):
            self.phases.pop(i)
            self.refresh_phases()

    def rename_phase(self):
        i = self.phase_table.currentRow()
        if not 0 <= i < len(self.phases):
            return
        name, ok = QInputDialog.getText(self, "Rename phase", "Unique phase name", text=self.phases[i].name)
        if ok and name.strip() and not any(p.name == name.strip() for j, p in enumerate(self.phases) if j != i):
            self.phases[i].name = name.strip()
            self.refresh_phases()

    def toggle_phase_cell(self):
        i = self.phase_table.currentRow()
        if 0 <= i < len(self.phases):
            self.phases[i].refine_cell = not self.phases[i].refine_cell
            self.refresh_phases()

    def inspect_phase(self):
        i = self.phase_table.currentRow()
        if 0 <= i < len(self.phases):
            try:
                p = self.phases[i]
                dialog = StructureDialog(p.cif_path, inspect_cif(p.cif_path), self, asdict(p))
                dialog.setWindowTitle("Inspect existing crystal structure")
                dialog.exec()
            except Exception as exc:
                self.show_error(exc)

    def browse_powder(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose powder data", "", "Powder files (*.xy *.xye *.csv *.tsv *.dat *.txt *.xrdml);;All files (*)")
        if path:
            self.powder_path.setText(path)
            if Path(path).suffix.lower() == ".xye":
                self.uncertainty.setCurrentIndex(1)

    def powder_options(self):
        return {"x_col": self.x_col.value() - 1, "y_col": self.y_col.value() - 1,
                "sigma_col": self.sigma_col.value() - 1, "skip_rows": self.skip_rows.value(),
                "uncertainty": ["poisson", "column", "constant"][self.uncertainty.currentIndex()],
                "delimiter": self.delimiter.currentText(), "sort_x": self.sort_x.isChecked(),
                "constant_sigma": self.constant_sigma.value()}

    def load_pattern(self):
        path = self.powder_path.text()
        options = self.powder_options()
        self._task(lambda: load_powder(path, **options), self.pattern_loaded)

    def pattern_loaded(self, powder):
        self.powder = powder
        self.powder_summary.setText(f"{len(powder.x):,} points · {powder.x[0]:.4f}–{powder.x[-1]:.4f}° 2θ · "
            f"median step {np.median(np.diff(powder.x)):.5g}°\n{powder.weighting}\n" + "\n".join(powder.warnings))
        fig = Figure(figsize=(10, 6), layout="constrained")
        axis = fig.add_subplot()
        axis.plot(powder.x, powder.y, color="#2c6f8b", lw=.85)
        axis.set_xlabel("2θ (degree)", fontsize=12)
        axis.set_ylabel("Intensity (input units)", fontsize=12)
        axis.set_title(Path(powder.source).name, loc="left", fontsize=13)
        axis.tick_params(direction="in", labelsize=10)
        self.input_plot.replace(fig)
        self.update_readiness()

    def overlay_preview(self):
        if self.powder is None or not self.phases:
            return self.show_error("Load a pattern and confirm at least one phase first.")
        phases = list(self.phases)
        wavelength = self.wave.value()
        if self.instrument_path.text().strip():
            # Parse only known scalar fields; do not load or evaluate arbitrary instrument code.
            try:
                for line in Path(self.instrument_path.text()).read_text(encoding="utf-8").splitlines():
                    for pair in line.split(";"):
                        key, _, value = pair.partition(":")
                        if key.strip() in {"Lam", "Lam1"}:
                            wavelength = float(value)
            except Exception as exc:
                return self.show_error(f"Cannot read preview wavelength: {exc}")
        low, high = float(self.powder.x[0]), float(self.powder.x[-1])
        self.preview_button.setEnabled(False)
        self._task(lambda: [(p.name, preview_reflections(p, wavelength, low, high)) for p in phases], self.show_preview)

    def show_preview(self, sets):
        self.pattern_loaded(self.powder)
        axis = self.input_plot.canvas.figure.axes[0]
        low = min(0, float(self.powder.y.min()))
        span = float(np.ptp(self.powder.y)) or 1
        from .reports import COLORS
        for i, (phase_name, reflections) in enumerate(sets):
            center = low - span * .09 * (i + 1)
            axis.vlines([r["two_theta"] for r in reflections], center,
                [center + span * .06 * r["intensity"] / 100 for r in reflections], colors=COLORS[i % len(COLORS)],
                lw=.8, label=phase_name)
        axis.legend(frameon=False)
        self.input_plot.canvas.draw_idle()
        self.powder_summary.setText(self.powder_summary.text() + "\nPreview sticks are calculated from the starting CIF and wavelength; they are not a fit or independent reference-card identification.")

    def browse_instrument(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load GSAS-II instrument parameters", "", "GSAS-II instrument profile (*.instprm);;All files (*)")
        if path:
            self.instrument_path.setText(path)

    def set_radiation(self, index):
        values = {0: (1.540593, False), 1: (1.540593, True), 2: (1.788965, False), 3: (.709317, False)}
        if index in values:
            wavelength, doublet = values[index]
            self.wave.setValue(wavelength)
            self.doublet.setChecked(doublet)
            if index == 1:
                self.wave2.setValue(1.544427)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Choose results root", self.output_root.text())
        if path:
            self.output_root.setText(path)

    def gather(self, new_run=False):
        try:
            axis = [int(x) for x in self.orientation_axis.text().replace(",", " ").split()]
            excluded = [[float(x) for x in item.strip().split(":")] for item in self.exclusions.text().split(";") if item.strip()]
            if any(len(pair) != 2 for pair in excluded):
                raise ValueError()
        except ValueError as exc:
            raise ValueError("Orientation needs three integers; exclusions use low:high; low:high syntax.") from exc
        instrument = InstrumentConfig(instrument_file=self.instrument_path.text().strip(), wavelength=self.wave.value(),
            wavelength2=self.wave2.value() if self.doublet.isChecked() else None, ka2_ratio=self.ratio.value(),
            geometry=self.geometry.currentText(), radius_mm=self.radius.value(), polarization=self.polarization.value(),
            calibrated=self.calibrated.isChecked(), **{k.lower() if k != "SH/L" else "shl": w.value() for k, w in self.profile_values.items()})
        recipe = RecipeConfig(background_terms=self.background_terms.value(), cycles=self.cycles.value(),
            refine_cell=self.refine_cell.isChecked(), position_correction=["none", "zero", "displacement"][self.correction.currentIndex()],
            profile_mode=["instrument", "fixed", "sample"][self.profile_mode.currentIndex()], refine_size=self.refine_size.isChecked(),
            refine_strain=self.refine_strain.isChecked(), preferred_orientation=self.preferred_orientation.isChecked(),
            orientation_axis=axis, refine_positions=self.refine_positions.isChecked(), refine_uiso=self.refine_uiso.isChecked(),
            min_two_theta=float(self.fit_min.text()) if self.fit_min.text().strip() else None,
            max_two_theta=float(self.fit_max.text()) if self.fit_max.text().strip() else None,
            excluded_ranges=excluded, peak_tolerance_deg=self.tolerance.value(), peak_prominence_fraction=self.prominence.value())
        recipe.max_passes = self.max_passes.value()
        recipe.min_passes = self.min_passes.value()
        recipe.stable_passes = self.stable_passes.value()
        recipe.start_trials = self.start_trials.value()
        recipe.rwp_relative_tolerance = self.rwp_tolerance.value()
        recipe.shift_su_tolerance = self.shift_tolerance.value()
        recipe.cell_search_percent = self.cell_search.value()
        recipe.background_mode = ["auto", "raw", "subtracted"][self.background_mode.currentIndex()]
        recipe.auto_initialize = self.auto_initialize.isChecked()
        recipe.refine_asymmetry = self.refine_asymmetry.isChecked()
        output = Path(self.output_root.text()).expanduser().resolve()
        if new_run:
            from .engine import _slug
            output = output / f"{_slug(self.project_name.text())}_{datetime.now():%Y%m%d_%H%M%S_%f}"
        return ProjectConfig(name=self.project_name.text().strip() or "Powder XRD refinement",
            powder_path=self.powder_path.text().strip(), powder_options=self.powder_options(), phases=list(self.phases),
            instrument=instrument, recipe=recipe, output_dir=str(output), engine_python=self.engine_python.text().strip(),
            gsas_path=self.gsas_path.text().strip(), continued_from=self.continued_from)

    def save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save project", self.project_name.text() + ".rsv.json", "Rietveld Studio project (*.rsv.json)")
        if path:
            try:
                self.gather().save(path)
                self.status.setText("Project saved")
            except Exception as exc:
                self.show_error(exc)

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open project", "", "Rietveld Studio project (*.json)")
        if path:
            try:
                self.apply_project(ProjectConfig.load(path))
            except Exception as exc:
                self.show_error(exc)

    def apply_project(self, project):
        self.continued_from = project.continued_from
        self.project_name.setText(project.name)
        self.powder_path.setText(project.powder_path)
        self.output_root.setText(project.output_dir)
        self.phases = project.phases
        self.refresh_phases()
        options = project.powder_options
        for key, widget in [("x_col", self.x_col), ("y_col", self.y_col), ("sigma_col", self.sigma_col)]:
            if options.get(key) is not None:
                widget.setValue(options[key] + 1)
        self.uncertainty.setCurrentIndex(["poisson", "column", "constant"].index(options.get("uncertainty", "poisson")))
        self.skip_rows.setValue(options.get("skip_rows", 0))
        self.delimiter.setCurrentText(options.get("delimiter", "auto"))
        self.sort_x.setChecked(options.get("sort_x", False))
        self.constant_sigma.setValue(options.get("constant_sigma", 1))
        inst = project.instrument
        self.instrument_path.setText(inst.instrument_file)
        self.wave.setValue(inst.wavelength)
        self.doublet.setChecked(inst.wavelength2 is not None)
        if inst.wavelength2:
            self.wave2.setValue(inst.wavelength2)
        self.radiation.setCurrentIndex(4)
        self.ratio.setValue(inst.ka2_ratio)
        self.geometry.setCurrentText(inst.geometry)
        self.radius.setValue(inst.radius_mm)
        self.polarization.setValue(inst.polarization)
        self.calibrated.setChecked(inst.calibrated)
        for key, widget in self.profile_values.items():
            widget.setValue(getattr(inst, key.lower() if key != "SH/L" else "shl"))
        recipe = project.recipe
        for name, widget in [("max_passes", self.max_passes), ("min_passes", self.min_passes),
            ("stable_passes", self.stable_passes), ("start_trials", self.start_trials),
            ("rwp_relative_tolerance", self.rwp_tolerance), ("shift_su_tolerance", self.shift_tolerance),
            ("cell_search_percent", self.cell_search)]:
            widget.setValue(getattr(recipe, name))
        self.auto_initialize.setChecked(recipe.auto_initialize)
        self.refine_asymmetry.setChecked(recipe.refine_asymmetry)
        self.background_mode.setCurrentIndex(["auto", "raw", "subtracted"].index(recipe.background_mode))
        self.background_terms.setValue(recipe.background_terms)
        self.cycles.setValue(recipe.cycles)
        self.refine_cell.setChecked(recipe.refine_cell)
        self.correction.setCurrentIndex(["none", "zero", "displacement"].index(recipe.position_correction))
        self.profile_mode.setCurrentIndex(["instrument", "fixed", "sample"].index(recipe.profile_mode))
        for key, widget in [("refine_size", self.refine_size), ("refine_strain", self.refine_strain),
            ("preferred_orientation", self.preferred_orientation), ("refine_positions", self.refine_positions), ("refine_uiso", self.refine_uiso)]:
            widget.setChecked(getattr(recipe, key))
        self.orientation_axis.setText(" ".join(map(str, recipe.orientation_axis)))
        self.fit_min.setText(str(recipe.min_two_theta) if recipe.min_two_theta is not None else "")
        self.fit_max.setText(str(recipe.max_two_theta) if recipe.max_two_theta is not None else "")
        self.exclusions.setText("; ".join(f"{a}:{b}" for a, b in recipe.excluded_ranges))
        self.tolerance.setValue(recipe.peak_tolerance_deg)
        self.prominence.setValue(recipe.peak_prominence_fraction)
        if project.engine_python and Path(project.engine_python).is_file():
            self.engine_python.setText(project.engine_python)
        if project.gsas_path and Path(project.gsas_path).is_dir():
            self.gsas_path.setText(project.gsas_path)
        self.navigate(1)
        self.load_pattern()

    def update_readiness(self):
        if self.result and self.pages.currentIndex() == 4:
            self.readiness.setText(f"{len(self.result['phases'])} refined phase(s)  ·  {self.result['statistics']['n_observations']:,} fitted observations")
            return
        self.readiness.setText(f"{len(self.phases)} confirmed phase(s)  ·  " + (f"{len(self.powder.x):,} loaded points" if self.powder is not None else "no powder data"))

    def _start_process(self, arguments, mode, python=None):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            raise ValueError("An engine/export process is already running.")
        process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        source = str(Path(__file__).resolve().parents[1])
        existing = environment.value("PYTHONPATH")
        environment.insert("PYTHONPATH", source + (os.pathsep + existing if existing else ""))
        environment.insert("PYTHONUNBUFFERED", "1")
        # Windows subprocesses must not inherit a Qt plugin path from another environment.
        environment.remove("QT_PLUGIN_PATH")
        environment.remove("QT_QPA_PLATFORM_PLUGIN_PATH")
        process.setProcessEnvironment(environment)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self.read_process)
        process.finished.connect(self.process_finished)
        process.errorOccurred.connect(self.process_error)
        self.process, self.process_mode, self.process_buffer, self.last_error = process, mode, "", ""
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(mode in {"refine", "origin"})
        process.start(python or self.engine_python.text().strip() or sys.executable, arguments)

    def check_engine(self):
        try:
            self.engine_status.setText("Checking GSAS-II Python, compiled symmetry and powder modules…")
            self._start_process(["-u", "-m", "rietveld_studio.engine", "--doctor", "--gsas-path", self.gsas_path.text().strip()], "doctor")
        except Exception as exc:
            self.show_error(exc)

    def run(self):
        try:
            config = self.gather(new_run=True)
            config.validate()
            # Re-read input with current options; the old preview is not assumed authoritative.
            preview = load_powder(config.powder_path, **config.powder_options)
            preview.fit_mask(config.recipe.min_two_theta, config.recipe.max_two_theta, config.recipe.excluded_ranges)
            folder = Path(config.output_dir)
            folder.mkdir(parents=True, exist_ok=False)
            request = folder / "requested_project.rsv.json"
            config.save(request)
            self.current_run_dir = folder
            self.live_iterations = []
            for value in self.metric_values.values():
                value.setText("—")
            self.convergence_plot.replace(convergence_figure({}))
            self.iteration_table.setRowCount(0)
            self.log.clear()
            self.progress.setValue(0)
            self.status.setText("Starting refinement…")
            self.navigate(5)
            self._start_process(["-u", "-m", "rietveld_studio.engine", str(request)], "refine")
        except Exception as exc:
            self.show_error(exc)

    def read_process(self):
        if not self.process:
            return
        self.process_buffer += bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        while "\n" in self.process_buffer:
            line, self.process_buffer = self.process_buffer.split("\n", 1)
            self.log.appendPlainText(line)
            if line.startswith("Origin export failed:"):
                self.last_error = line
            if line.startswith("RS_EVENT "):
                try:
                    self.handle_event(json.loads(line[9:]))
                except (ValueError, KeyError):
                    pass

    def handle_event(self, event):
        kind = event.get("kind")
        if kind == "doctor":
            self.engine_ok = bool(event.get("ok"))
            self.engine_status.setText(json.dumps(event, indent=2))
            self.status.setText("Engine ready" if self.engine_ok else "Engine needs setup")
        elif kind == "stage":
            self.status.setText(event["message"])
            trial, total_trials = event.get("trial", 1), event.get("trial_total", 1)
            self.progress.setValue(round(90 * ((trial - 1) + (event["index"] - 1) / event["total"]) / total_trials))
        elif kind == "trial":
            self.status.setText(event["message"])
        elif kind == "iteration":
            self.live_iterations.append(event)
            self.convergence_plot.replace(convergence_figure({"iteration_history": self.live_iterations}))
            self.status.setText(f"Start {event['trial']} · {event['stage']} · pass {event['pass']} · Rwp {event['Rwp_percent']:.3f}%")
            best = event.get("best_Rwp_percent")
            if best is not None:
                self.metric_values["Rwp_percent"].setText(f"{best:.3f}%")
        elif kind == "stage_done":
            self.status.setText(f"{event['stage']} · Rwp {event['Rwp_percent']:.3g}%" + (" · rolled back" if not event["accepted"] else ""))
        elif kind == "export":
            self.progress.setValue(94)
            self.status.setText("Writing results…")
        elif kind == "error":
            self.last_error = event.get("message", "Refinement failed")
        elif kind == "complete":
            self.status.setText("Refinement complete")

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.last_error = "Could not start the selected Python executable. Check the Engine settings."
            self.run_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.engine_status.setText(self.last_error)
            self.show_error(self.last_error)

    def process_finished(self, code, exit_status):
        self.read_process()
        if self.process_buffer:
            self.log.appendPlainText(self.process_buffer)
        mode = self.process_mode
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if mode == "doctor":
            if code != 0:
                self.engine_status.setText(self.last_error or "Engine check failed. See the log; run scripts/bootstrap_engine.py or choose the correct environment.")
            return
        if code != 0:
            self.status.setText("Run stopped / failed")
            self.show_error(self.last_error or "The process stopped. Inspect the log; accepted checkpoints and existing results are retained.")
            return
        if mode == "refine":
            try:
                self.load_results(self.current_run_dir)
                self.progress.setValue(100)
                self.navigate(4)
                if self.auto_origin.isChecked() and platform.system() == "Windows":
                    self.export_origin(automatic=True)
            except Exception as exc:
                self.show_error(f"Refinement finished but results could not be displayed: {exc}")
        elif mode == "origin":
            self.status.setText("Origin project exported")

    def stop_run(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.last_error = "Stopped by the user. Earlier accepted stage checkpoints are retained."
            # Kill the owned worker, leaving the GUI and any other applications untouched.
            self.process.kill()

    def open_results(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose refinement result folder")
        if folder:
            try:
                self.load_results(folder)
                self.navigate(4)
            except Exception as exc:
                self.show_error(exc)

    def load_results(self, folder):
        folder = Path(folder)
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        with np.load(folder / "profile.npz", allow_pickle=False) as arrays:
            profile = {k: arrays[k] for k in arrays.files}
        self.result, self.result_dir = result, folder
        self.status.setText("Results loaded")
        for key, value in self.metric_values.items():
            value.setText(f"{result['statistics'][key]:.3f}" + ("%" if key.endswith("percent") else ""))
        self.result_plot.replace(refinement_figure(result, profile))
        self.convergence_plot.replace(convergence_figure(result))
        populate(self.iteration_table, [[a.get(k) for k in ["trial", "stage", "pass", "Rwp_percent", "max_shift_over_su", "accepted"]] for a in result.get("iteration_history", [])])
        descriptive = result["statistics"].get("statistical_interpretation") == "descriptive_only" or "constant sigma" in result.get("weighting", "")
        self.metric_boxes["chi2_reduced"].setTitle("χ² (descriptive)" if descriptive else "Reduced χ²")
        self.metric_boxes["goodness_of_fit"].setTitle("GOF (descriptive)" if descriptive else "GOF")
        status = "Convergence criteria met" if result.get("convergence", {}).get("converged") else "Convergence not established / not recorded"
        interpretation = "Constant sigma: χ²/GOF depend on the chosen intensity units and sigma; values near one are not a statistical quality certificate." if descriptive else "Statistical interpretation assumes the declared intensity uncertainties are correct."
        rmse = result["statistics"].get("residual_RMSE_input_units")
        self.results_banner.setText(f"{status}. {interpretation}" + (f" Residual RMSE: {rmse:.5g} input units." if rmse is not None else ""))
        cells = []
        for phase in result["phases"]:
            for key, value in phase["cell"].items():
                cells.append([phase["phase"], key, value, phase["cell_su"].get(key), "Å³" if key == "volume" else "degree" if "angle" in key else "Å"])
        populate(self.lattice_table, cells)
        populate(self.result_phase_table, [[p["phase"], p["space_group"], p["density_g_cm3"],
            p["weight_fraction"] * 100 if p["weight_fraction"] is not None else None,
            p["weight_fraction_su"] * 100 if p["weight_fraction_su"] is not None else None,
            p["size_um"] * 1000 if p["size_um"] is not None else None, p["microstrain_ppm"]] for p in result["phases"]])
        populate(self.atom_table, [[a.get(k) for k in ["phase", "label", "element", "x", "y", "z", "occupancy", "Uiso_A2", "Biso_A2", "refinement_flags"]] for a in result["atoms"]])
        populate(self.reflections_table, [[a.get(k) for k in ["phase", "h", "k", "l", "two_theta", "d_A", "Icalc", "component", "source_url", "doi"]] for a in result["reflections"]])
        populate(self.peaks_table, [[a.get(k) for k in ["observed_two_theta", "status", "assignments", "nearest_calculated_two_theta", "delta_two_theta", "source_urls"]] for a in result["peak_matches"]])
        populate(self.parameter_table, [[a.get(k) for k in ["parameter", "value", "standard_uncertainty", "shift_over_su"]] for a in result["parameters"]])
        populate(self.correlation_table, [[a[k] for k in ["parameter_1", "parameter_2", "correlation"]] for a in result["correlations"]])
        import html
        self.diagnostics.setHtml("<h2>Model review</h2><p>Completed stages do not establish that the chemical model is correct.</p><ul>" +
            "".join(f"<li>{html.escape(w)}</li>" for w in result["warnings"]) + "</ul><p>Weighting: " + html.escape(result["weighting"]) +
            "</p><p>Standard uncertainties are conditional on the structural model and declared weights; they do not include calibration/systematic errors.</p>")

    def open_report(self):
        if self.result_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str((self.result_dir / "report.html").resolve())))

    def continue_result(self):
        if not self.result_dir:
            return self.show_error("Open or complete a refinement first.")
        try:
            from .continuation import continuation_project
            project = continuation_project(self.result_dir)
            self.apply_project(project)
            self.navigate(3)
            self.status.setText("Refined model loaded for a new run")
        except Exception as exc:
            self.show_error(exc)

    def open_result_folder(self):
        if self.result_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result_dir.resolve())))

    def export_origin(self, checked=False, automatic=False):
        if not self.result_dir:
            return self.show_error("Complete a refinement or open a result folder first.")
        if platform.system() != "Windows":
            return self.show_error("Native .opju export needs Windows with licensed Origin. The result folder includes a standalone export_to_origin.py script for that computer, plus CSV/XLSX/SVG/PDF files.")
        destination = self.result_dir / "refinement.opju"
        if not automatic:
            path, _ = QFileDialog.getSaveFileName(self, "Export native Origin project", str(destination), "Origin project (*.opju)")
            if not path:
                return
            destination = Path(path)
        if destination.exists():
            return self.show_error("This OPJU file exists. Choose a new filename to preserve it.")
        self.status.setText("Exporting native Origin project…")
        self._start_process(["-u", "-m", "rietveld_studio.origin_export", str(self.result_dir), "--output", str(destination)], "origin", python=sys.executable)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "recipe_split"):
            self.recipe_split.setDirection(QBoxLayout.Direction.TopToBottom if self.width() < 1280
                                           else QBoxLayout.Direction.LeftToRight)

    def closeEvent(self, event):
        if self.tasks:
            self.show_error("A structure/data-loading task is finishing. Close again when it completes.")
            event.ignore()
            return
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.stop_run()
            self.process.waitForFinished(3000)
        for key, widget in [("engine_python", self.engine_python), ("gsas_path", self.gsas_path), ("output_root", self.output_root)]:
            self.settings.setValue(key, widget.text())
        event.accept()


def launch(project=None, results=None):
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setApplicationName("Rietveld Studio")
    window = MainWindow()
    if project:
        window.apply_project(ProjectConfig.load(project))
    if results:
        window.load_results(results)
        window.navigate(4)
    window.show()
    return app.exec()

