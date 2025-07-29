# Updated main_app.py with full workflow run functionality and updated intro page

import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit, QProgressBar, 
                             QComboBox, QSpinBox, QMessageBox, QScrollArea, QStackedWidget, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon
from app_backend import Backend
from ui_pages import UIPages

class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, str)  # Added message parameter
    result_signal = pyqtSignal(bool, list)

    def __init__(self, func, *args):
        super().__init__()
        self.func = func
        self.args = args

    def run(self):
        success, messages = self.func(*self.args)
        for msg in messages:
            self.log_signal.emit(msg)
        self.result_signal.emit(success, messages)

class MainWindow(QMainWindow, UIPages):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hydrological Analysis Tool")
        self.setGeometry(100, 100, 1200, 800)
        self.backend = Backend()
        self.current_theme = "dark"  # Default theme
        self.workflow_type = None  # Initialize workflow_type to avoid AttributeError
        
        # Set window icon (logo)
        logo_path = os.path.join("resources", "logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        
        # Define stylesheets for dark and light modes
        self.dark_stylesheet = """
            QMainWindow, QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                                          stop:0 #1e1e2e, stop:1 #3b3b4f);
            }
            QLabel {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 16px;
            }
            QLineEdit, QComboBox, QSpinBox, QTextEdit {
                background-color: #2e2e3e;
                color: #ffffff;
                border: 1px solid #4a4a5a;
                border-radius: 5px;
                padding: 5px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                min-width: 300px;
            }
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QTextEdit:hover {
                border: 1px solid #6a6a7a;
            }
            QComboBox QAbstractItemView {
                color: #ffffff;
                background-color: #2e2e3e;
                selection-background-color: #3498db;
                border: 1px solid #4a4a5a;
            }
            QPushButton {
                background-color: #3498db;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f6699;
            }
            QPushButton#themeSwitch {
                background-color: #2ecc71;
                padding: 8px 16px;
                border-radius: 15px;
            }
            QPushButton#themeSwitch:hover {
                background-color: #27ae60;
            }
            QProgressBar {
                background-color: #2e2e3e;
                border: 1px solid #4a4a5a;
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QComboBox::drop-down {
                border: none;
                background: #2e2e3e;
                border-radius: 5px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #2e2e3e;
                border: 1px solid #4a4a5a;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #4a4a5a;
                border-radius: 3px;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                background: #2e2e3e;
                border: none;
            }
        """
        self.light_stylesheet = """
            QMainWindow {
                background: #e0e0e5;
            }
            QLabel {
                color: #333333;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 16px;
            }
            QLineEdit, QComboBox, QSpinBox, QTextEdit {
                background-color: #f0f0f5;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 5px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                min-width: 300px;
            }
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QTextEdit:hover {
                border: 1px solid #aaaaaa;
            }
            QPushButton {
                background-color: #3498db;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f6699;
            }
            QPushButton#themeSwitch {
                background-color: #2ecc71;
                padding: 8px 16px;
                border-radius: 15px;
            }
            QPushButton#themeSwitch:hover {
                background-color: #27ae60;
            }
            QProgressBar {
                background-color: #f0f0f5;
                border: 1px solid #cccccc;
                border-radius: 5px;
                text-align: center;
                color: #333333;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QComboBox::drop-down {
                border: none;
                background: #3498db;
                border-radius: 5px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
            }
        """
        
        # Apply initial theme
        self.set_theme("dark")
        
        self.init_ui()

    def set_theme(self, theme):
        """Apply the selected theme (dark or light)"""
        self.current_theme = theme
        if theme == "light":
            self.setStyleSheet(self.dark_stylesheet)
        else:
            self.setStyleSheet(self.light_stylesheet)

    def toggle_theme(self):
        """Toggle between dark and light themes"""
        if self.current_theme == "dark":
            self.set_theme("light")
            self.theme_switch.setText("Light Mode")
        else:
            self.set_theme("dark")
            self.theme_switch.setText("Dark Mode")

    def start_workflow(self, workflow_type):
        """Initialize the selected workflow type and show the first relevant page"""
        self.workflow_type = workflow_type
        
        if workflow_type == "full":
            self.stacked_widget.setCurrentIndex(2)  # Full inputs page
        elif workflow_type == "smbalance":
            self.stacked_widget.setCurrentIndex(5)  # SM balance page
        elif workflow_type == "hydroloop":
            self.stacked_widget.setCurrentIndex(6)  # Hydroloop page
        elif workflow_type == "netcdf":
            self.stacked_widget.setCurrentIndex(3)  # NetCDF page

    def init_ui(self):
        # Create stacked widget for page navigation
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Create pages
        self.create_intro_page()
        self.create_module_selection_page()
        self.create_full_inputs_page()
        self.create_netcdf_page()
        self.create_rain_page()
        self.create_smbalance_page()
        self.create_hydroloop_page()
        self.create_sheets_page()
        
        # Show intro page first
        self.stacked_widget.setCurrentIndex(0)

    def create_intro_page(self):
        """Create the introduction page with app information"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Logo
        logo_label = QLabel()
        logo_path = os.path.join("resources", "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo_label)
        else:
            logo_label.setText("Logo Not Found")
            logo_label.setStyleSheet("color: #ff5555; font-size: 16px;")
            logo_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo_label)
        
        # Title
        title = QLabel("Water Accounting")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #3498db; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Theme switch
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_layout.addWidget(theme_label)
        self.theme_switch = QPushButton("Dark Mode" if self.current_theme == "dark" else "Light Mode")
        self.theme_switch.setObjectName("themeSwitch")
        self.theme_switch.setFixedSize(120, 30)
        self.theme_switch.setCursor(Qt.PointingHandCursor)
        self.theme_switch.clicked.connect(self.toggle_theme)
        theme_layout.addWidget(self.theme_switch)
        theme_layout.addStretch(1)
        layout.addLayout(theme_layout)
        
        # Read introduction text from file
        intro_text = QTextEdit()
        intro_text.setReadOnly(True)
        intro_text.setStyleSheet("padding: 10px; border-radius: 10px;")
        intro_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        try:
            intro_file = os.path.join("resources", "introduction.txt")
            if os.path.exists(intro_file):
                with open(intro_file, 'r') as f:
                    intro_text.setPlainText(f.read())
            else:
                intro_text.setPlainText("Welcome to the WA+ Hydrological Analysis Tool.\n\n"
                                       "This tool helps in analyzing hydrological data including:\n"
                                       "- NetCDF file creation from TIFFs\n"
                                       "- Rain interception calculations\n"
                                       "- Soil moisture balance\n"
                                       "- Full hydrological loop analysis\n"
                                       "- Sheet 1 and Sheet 2 generation")
        except Exception as e:
            intro_text.setPlainText(f"Error loading introduction: {str(e)}")
        
        layout.addWidget(intro_text)
        layout.setStretchFactor(intro_text, 1)
        
        # Button group
        btn_layout = QHBoxLayout()
        
        # Start button
        start_btn = QPushButton("Start")
        start_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        start_btn.setFixedSize(200, 60)
        start_btn.setStyleSheet("background-color: #2ecc71; margin: 10px; font-size: 16px;")
        start_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(start_btn)
        
        layout.addLayout(btn_layout)
        
        layout.setSpacing(20)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)

    def update_unit_conversion(self, unit_text):
        """Update the hidden unit conversion factor based on user selection"""
        if "MCM" in unit_text:
            self.hydro_entries["unit_conversion"].setText("1e3")
        else:  # Km³
            self.hydro_entries["unit_conversion"].setText("1e6")

    def browse_directory(self, key, entries):
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            entries[key].setText(path)

    def browse_file(self, key, entries, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", file_filter)
        if path:
            entries[key].setText(path)

    def save_log(self, log_widget):
        def save():
            filename, _ = QFileDialog.getSaveFileName(self, "Save Log", "", "Text Files (*.txt)")
            if filename:
                with open(filename, "w") as f:
                    f.write(log_widget.toPlainText())
                QMessageBox.information(self, "Success", f"Log saved to {filename}")
        return save

    def run_full_workflow(self):
        """Run all steps of the full workflow sequentially"""
        if self.workflow_type != "full":
            QMessageBox.critical(self, "Error", "Full workflow can only be run from Full Water Accounting mode")
            return

        self.full_run_btn.setEnabled(False)
        self.full_progress.setMaximum(2100)  # Sum of all steps: 100 (NetCDF) + 300 (Rain) + 100 (SM) + 500 (Hydro Init) + 1000 (Hydro Run) + 200 (Sheet1) + 200 (Sheet2)
        self.full_progress.setValue(0)
        self.full_log.clear()

        def update_progress(current, total, message=None):
            current_total = self.full_progress.value() + current
            self.full_progress.setValue(current_total)
            self.full_progress_label.setText(f"{int((current_total/2100)*100)}%")
            if message:
                self.full_step_label.setText(f"Current step: {message}")
                self.full_log.append(message)

        def run_next_step(step_index, success=True, messages=[]):
            if not success:
                self.task_finished(False, messages, self.full_run_btn, self.full_progress)
                return

            steps = [
                (self.create_netcdf_full, "Creating NetCDF Files"),
                (self.calculate_rain_full, "Calculating Rain Interception"),
                (self.run_smbalance_full, "Running Soil Moisture Balance"),
                (self.init_hydroloop_full, "Initializing Hydroloop"),
                (self.run_hydroloop_full, "Running Hydroloop"),
                (self.generate_sheet1_full, "Generating Sheet 1"),
                (self.generate_sheet2_full, "Generating Sheet 2")
            ]

            if step_index >= len(steps):
                self.task_finished(True, ["Full workflow completed"], self.full_run_btn, self.full_progress)
                self.stacked_widget.setCurrentIndex(0)
                return

            func, step_name = steps[step_index]
            update_progress(0, 0, f"Starting: {step_name}")
            self.worker = WorkerThread(func, update_progress)
            self.worker.log_signal.connect(self.full_log.append)
            self.worker.progress_signal.connect(update_progress)
            self.worker.result_signal.connect(
                lambda s, m: run_next_step(step_index + 1, s, m)
            )
            self.worker.start()

        run_next_step(0)

    def create_netcdf_full(self, update_progress):
        """Run NetCDF creation for full workflow"""
        input_dir = self.full_entries["input_tifs"].text()
        shp_path = self.full_entries["shapefile"].text()
        template_path = self.full_entries["template_mask"].text()
        output_dir = self.full_entries["output_dir"].text()
        return self.backend.create_netcdf(input_dir, shp_path, template_path, output_dir, update_progress)

    def calculate_rain_full(self, update_progress):
        """Run rain interception for full workflow"""
        directory = self.full_entries["rain_input"].text()
        return self.backend.calculate_rain(directory, update_progress)

    def run_smbalance_full(self, update_progress):
        """Run soil moisture balance for full workflow"""
        directory = self.full_entries["sm_input"].text()
        start_year = self.full_entries["start_year"].text()
        end_year = self.full_entries["end_year"].text()
        f_percol = self.full_entries["f_percol"].text()
        f_smax = self.full_entries["f_smax"].text()
        cf = self.full_entries["cf"].text()
        f_bf = self.full_entries["f_bf"].text()
        deep_percol_f = self.full_entries["deep_percol_f"].text()
        return self.backend.run_smbalance(directory, start_year, end_year, f_percol, f_smax, cf, f_bf, deep_percol_f, update_progress)

    def init_hydroloop_full(self, update_progress):
        """Initialize hydroloop for full workflow"""
        inputs = {key: entry.text() if isinstance(entry, QLineEdit) else entry.currentText() 
                 for key, entry in self.full_entries.items()}
        return self.backend.init_hydroloop(inputs, update_progress)

    def run_hydroloop_full(self, update_progress):
        """Run hydroloop for full workflow"""
        return self.backend.run_hydroloop(update_progress)

    def generate_sheet1_full(self, update_progress):
        """Generate Sheet 1 for full workflow"""
        if not hasattr(self.backend, 'BASIN') or not self.backend.BASIN:
            return False, ["Hydroloop not initialized or basin data not available"]
        return self.backend.generate_sheet1(self.backend.BASIN, update_progress)

    def generate_sheet2_full(self, update_progress):
        """Generate Sheet 2 for full workflow"""
        if not hasattr(self.backend, 'BASIN') or not self.backend.BASIN:
            return False, ["Hydroloop not initialized or basin data not available"]
        return self.backend.generate_sheet2(self.backend.BASIN, update_progress)

    def create_netcdf(self):
        if self.workflow_type == "full":
            input_dir = self.full_entries["input_tifs"].text()
            shp_path = self.full_entries["shapefile"].text()
            template_path = self.full_entries["template_mask"].text()
            output_dir = self.full_entries["output_dir"].text()
        else:
            input_dir = self.netcdf_entries["input_tifs"].text()
            shp_path = self.netcdf_entries["shapefile"].text()
            template_path = self.netcdf_entries["template_mask"].text()
            output_dir = self.netcdf_entries["output_dir"].text()

        self.netcdf_run_btn.setEnabled(False)
        self.netcdf_progress.setMaximum(100)
        self.netcdf_progress.setValue(0)
        
        def update_progress(current, total, message=None):
            self.netcdf_progress.setValue(current)
            self.netcdf_progress_label.setText(f"{current}%")
            if message:
                self.current_step_label.setText(f"Current step: {message}")
        
        self.worker = WorkerThread(
            self.backend.create_netcdf, 
            input_dir, 
            shp_path, 
            template_path, 
            output_dir,
            update_progress
        )

        self.worker.log_signal.connect(self.netcdf_log.append)
        self.worker.progress_signal.connect(update_progress)
        self.worker.result_signal.connect(
            lambda success, messages: self.task_finished(
                success, messages, 
                self.netcdf_run_btn, 
                self.netcdf_progress, 
                self.netcdf_next_btn
            )
        )
        self.netcdf_next_btn.clicked.disconnect()
        self.netcdf_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(4))
        self.worker.start()

    def calculate_rain(self):
        if self.workflow_type == "full":
            directory = self.full_entries["rain_input"].text()
        else:
            directory = self.rain_input.text()
            
        self.rain_run_btn.setEnabled(False)
        self.rain_progress.setMaximum(300)
        self.rain_progress.setValue(0)
        
        def update_progress(current, total, message=None):
            self.rain_progress.setValue(current)
            self.rain_progress_label.setText(f"{int((current/total)*100)}%")
            if message:
                self.rain_step_label.setText(f"Current step: {message}")
        
        self.worker = WorkerThread(self.backend.calculate_rain, directory, update_progress)
        self.worker.log_signal.connect(self.rain_log.append)
        self.worker.progress_signal.connect(update_progress)
        self.worker.result_signal.connect(
            lambda success, messages: self.task_finished(
                success, messages, 
                self.rain_run_btn, 
                self.rain_progress, 
                self.rain_next_btn
            )
        )
        self.worker.start()

    def run_smbalance(self):
        if self.workflow_type == "full":
            directory = self.full_entries["sm_input"].text()
            start_year = self.full_entries["start_year"].text()
            end_year = self.full_entries["end_year"].text()
            f_percol = self.full_entries["f_percol"].text()
            f_smax = self.full_entries["f_smax"].text()
            cf = self.full_entries["cf"].text()
            f_bf = self.full_entries["f_bf"].text()
            deep_percol_f = self.full_entries["deep_percol_f"].text()
        else:
            directory = self.sm_entries["sm_input"].text()
            start_year = self.sm_entries["start_year"].text()
            end_year = self.sm_entries["end_year"].text()
            f_percol = self.sm_entries["f_percol"].text()
            f_smax = self.sm_entries["f_smax"].text()
            cf = self.sm_entries["cf"].text()
            f_bf = self.sm_entries["f_bf"].text()
            deep_percol_f = self.sm_entries["deep_percol_f"].text()

        self.sm_run_btn.setEnabled(False)
        self.sm_progress.setMaximum(100)
        self.sm_progress.setValue(0)
        
        def update_progress(current, total, message=None):
            self.sm_progress.setValue(current)
            self.sm_progress_label.setText(f"{current}%")
            if message:
                self.sm_step_label.setText(f"Current step: {message}")
        
        self.worker = WorkerThread(
            self.backend.run_smbalance, 
            directory, 
            start_year, 
            end_year, 
            f_percol, 
            f_smax, 
            cf, 
            f_bf, 
            deep_percol_f,
            update_progress
        )
        
        self.worker.log_signal.connect(self.sm_log.append)
        self.worker.progress_signal.connect(update_progress)
        self.worker.result_signal.connect(
            lambda success, messages: self.task_finished(
                success, messages, 
                self.sm_run_btn, 
                self.sm_progress, 
                self.sm_next_btn
            )
        )
        self.worker.start()

    def init_hydroloop(self):
        if self.workflow_type == "full":
            inputs = {key: entry.text() if isinstance(entry, QLineEdit) else entry.currentText() 
                     for key, entry in self.full_entries.items()}
        else:
            inputs = {key: entry.text() if isinstance(entry, QLineEdit) else entry.currentText() 
                     for key, entry in self.hydro_entries.items()}
            
        self.hydro_init_btn.setEnabled(False)
        self.hydro_progress.setMaximum(500)
        self.hydro_progress.setValue(0)
        
        def update_progress(current, total, message=None):
            self.hydro_progress.setValue(current)
            self.hydro_progress_label.setText(f"{int((current/total)*100)}%")
            if message:
                self.hydro_step_label.setText(f"Current step: {message}")
        
        self.worker = WorkerThread(self.backend.init_hydroloop, inputs, update_progress)
        self.worker.log_signal.connect(self.hydro_log.append)
        self.worker.progress_signal.connect(update_progress)
        self.worker.result_signal.connect(
            lambda success, messages: self.task_finished(
                success, messages, 
                self.hydro_init_btn, 
                self.hydro_progress, 
                self.hydro_run_btn
            )
        )
        self.worker.start()

    def run_hydroloop(self):
        self.hydro_run_btn.setEnabled(False)
        self.hydro_progress.setMaximum(1000)
        
        def update_progress(current, total, message=None):
            self.hydro_progress.setValue(current)
            self.hydro_progress_label.setText(f"{int((current/total)*100)}%")
            if message:
                self.hydro_step_label.setText(f"Current step: {message}")
        
        self.worker = WorkerThread(self.backend.run_hydroloop, update_progress)
        self.worker.log_signal.connect(self.hydro_log.append)
        self.worker.progress_signal.connect(update_progress)
        self.worker.result_signal.connect(
            lambda success, messages: self.task_finished(
                success, messages, 
                self.hydro_run_btn, 
                self.hydro_progress, 
                self.hydro_next_btn
            )
        )
        self.hydro_next_btn.clicked.disconnect()
        self.hydro_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(7))
        self.worker.start()

    def generate_sheet1(self):
        if not hasattr(self.backend, 'BASIN') or not self.backend.BASIN:
            QMessageBox.critical(self, "Error", "Hydroloop not initialized or basin data not available")
            return
            
        self.sheet1_run_btn.setEnabled(False)
        self.sheet1_progress.setMaximum(200)
        self.sheet1_progress.setValue(0)
        
        def update_progress(current, total, message=None):
            self.sheet1_progress.setValue(current)
            self.sheet1_progress_label.setText(f"{int((current/total)*100)}%")
            if message:
                self.sheet1_step_label.setText(f"Current step: {message}")
        
        self.worker = WorkerThread(
            self.backend.generate_sheet1, 
            self.backend.BASIN, 
            update_progress
        )
        self.worker.log_signal.connect(self.sheet1_log.append)
        self.worker.progress_signal.connect(update_progress)
        self.worker.result_signal.connect(
            lambda success, messages: self.task_finished(
                success, messages, 
                self.sheet1_run_btn, 
                self.sheet1_progress
            )
        )
        self.worker.start()

    def generate_sheet2(self):
        if not hasattr(self.backend, 'BASIN') or not self.backend.BASIN:
            QMessageBox.critical(self, "Error", "Hydroloop not initialized or basin data not available")
            return
            
        self.sheet2_run_btn.setEnabled(False)
        self.sheet2_progress.setMaximum(200)
        self.sheet2_progress.setValue(0)
        
        def update_progress(current, total, message=None):
            self.sheet2_progress.setValue(current)
            self.sheet2_progress_label.setText(f"{int((current/total)*100)}%")
            if message:
                self.sheet2_step_label.setText(f"Current step: {message}")
        
        self.worker = WorkerThread(
            self.backend.generate_sheet2, 
            self.backend.BASIN, 
            update_progress
        )
        self.worker.log_signal.connect(self.sheet2_log.append)
        self.worker.progress_signal.connect(update_progress)
        self.worker.result_signal.connect(
            lambda success, messages: self.task_finished(
                success, messages, 
                self.sheet2_run_btn, 
                self.sheet2_progress
            )
        )
        self.worker.start()

    def task_finished(self, success, messages, run_btn, progress=None, next_btn=None):
        run_btn.setEnabled(True)
        if progress:
            progress.setValue(progress.maximum())
        if next_btn and success:
            next_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "Success", "Task completed successfully")
        else:
            QMessageBox.critical(self, "Error", messages[-1] if messages else "Task failed")

    def closeEvent(self, event):
        if hasattr(self.backend, 'running') and self.backend.running:
            reply = QMessageBox.question(self, "Quit", "A task is running! Are you sure you want to quit?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()