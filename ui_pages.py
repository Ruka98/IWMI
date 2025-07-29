from PyQt5.QtWidgets import (QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar, 
                             QComboBox, QHBoxLayout, QVBoxLayout, QWidget, 
                             QSizePolicy, QScrollArea)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
import os

class UIPages:
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
        
        # Create NetCDF button
        netcdf_btn = QPushButton("Create NetCDF")
        netcdf_btn.clicked.connect(lambda: self.start_workflow("netcdf"))
        netcdf_btn.setFixedSize(200, 60)
        netcdf_btn.setStyleSheet("background-color: #3498db; margin: 10px; font-size: 16px;")
        netcdf_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(netcdf_btn)
        
        layout.addLayout(btn_layout)
        
        layout.setSpacing(20)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)

    def create_module_selection_page(self):
        """Create the module selection page"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Select Analysis Module")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #3498db; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Description
        desc = QLabel("Please select the type of analysis you want to perform:")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)
        
        # Module buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(20)
        
        full_btn = QPushButton("Full Water Accounting")
        full_btn.setToolTip("Complete workflow from NetCDF creation to final water accounting sheets")
        full_btn.setMinimumSize(300, 60)
        full_btn.clicked.connect(lambda: self.start_workflow("full"))
        full_btn.setCursor(Qt.PointingHandCursor)
        
        netcdf_btn = QPushButton("Create NetCDF")
        netcdf_btn.setToolTip("Create NetCDF files from TIFFs only")
        netcdf_btn.setMinimumSize(300, 60)
        netcdf_btn.clicked.connect(lambda: self.start_workflow("netcdf"))
        netcdf_btn.setCursor(Qt.PointingHandCursor)
        
        sm_btn = QPushButton("Soil Moisture Balance")
        sm_btn.setToolTip("Calculate soil moisture balance only")
        sm_btn.setMinimumSize(300, 60)
        sm_btn.clicked.connect(lambda: self.start_workflow("smbalance"))
        sm_btn.setCursor(Qt.PointingHandCursor)
        
        hydro_btn = QPushButton("Hydroloop Simulation")
        hydro_btn.setToolTip("Perform hydroloop calculations only")
        hydro_btn.setMinimumSize(300, 60)
        hydro_btn.clicked.connect(lambda: self.start_workflow("hydroloop"))
        hydro_btn.setCursor(Qt.PointingHandCursor)
        
        btn_layout.addWidget(full_btn, alignment=Qt.AlignCenter)
        btn_layout.addWidget(netcdf_btn, alignment=Qt.AlignCenter)
        btn_layout.addWidget(sm_btn, alignment=Qt.AlignCenter)
        btn_layout.addWidget(hydro_btn, alignment=Qt.AlignCenter)
        
        layout.addLayout(btn_layout)
        layout.addStretch(1)
        
        # Back button
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        back_btn.setFixedSize(100, 40)
        back_btn.setStyleSheet("background-color: #e74c3c;")
        back_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)
        
        layout.setSpacing(20)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)

    def create_full_inputs_page(self):
        """Create the input page for full water accounting workflow"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Full Water Accounting Inputs")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #3498db; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Back button
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        back_btn.setFixedSize(100, 40)
        back_btn.setStyleSheet("background-color: #e74c3c;")
        back_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)
        
        # Content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        
        # NetCDF inputs
        netcdf_title = QLabel("NetCDF Creation Inputs")
        netcdf_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71; margin: 10px;")
        netcdf_title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(netcdf_title)
        
        netcdf_fields = [
            ("Input TIFF Directory:", "input_tifs", True, "Directory containing TIFF files"),
            ("Shapefile:", "shapefile", False, "Shapefile (*.shp)", "Shapefile for spatial reference"),
            ("Template/Mask File:", "template_mask", False, "GeoTIFF Files (*.tif *.tiff)", "Template and basin mask GeoTIFF file"),
            ("Output Directory:", "output_dir", True, "Directory to save NetCDF files and hydroloop results")
        ]
        
        self.full_entries = {}
        for label, key, is_dir, *args in netcdf_fields:
            row = QHBoxLayout()
            label_widget = QLabel(label)
            row.addWidget(label_widget)
            self.full_entries[key] = QLineEdit()
            self.full_entries[key].setToolTip(args[-1] if args else "")
            self.full_entries[key].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(self.full_entries[key])
            btn = QPushButton("Browse")
            btn.setCursor(Qt.PointingHandCursor)
            if is_dir:
                btn.clicked.connect(lambda _, k=key: self.browse_directory(k, self.full_entries))
            else:
                btn.clicked.connect(lambda _, k=key, f=args[0]: self.browse_file(k, self.full_entries, f))
            row.addWidget(btn)
            content_layout.addLayout(row)
        
        # Rain Interception inputs
        separator = QLabel()
        separator.setStyleSheet("border-top: 1px solid #ccc; margin: 20px 0;")
        content_layout.addWidget(separator)
        
        rain_title = QLabel("Rain Interception Inputs")
        rain_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71; margin: 10px;")
        rain_title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(rain_title)
        
        row = QHBoxLayout()
        row.addWidget(QLabel("NC Directory:"))
        self.full_entries["rain_input"] = QLineEdit()
        self.full_entries["rain_input"].setToolTip("Directory containing input files for rain interception")
        self.full_entries["rain_input"].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.addWidget(self.full_entries["rain_input"])
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(lambda: self.browse_directory("rain_input", self.full_entries))
        browse_btn.setCursor(Qt.PointingHandCursor)
        row.addWidget(browse_btn)
        content_layout.addLayout(row)
        
        # Soil Moisture Balance inputs
        separator = QLabel()
        separator.setStyleSheet("border-top: 1px solid #ccc; margin: 20px 0;")
        content_layout.addWidget(separator)
        
        sm_title = QLabel("Soil Moisture Balance Inputs")
        sm_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71; margin: 10px;")
        sm_title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(sm_title)
        
        sm_fields = [
            ("Input Directory:", "sm_input", True, "Directory containing input files"),
            ("Start Year:", "start_year", False, "Starting year for analysis (e.g., 2019)"),
            ("End Year:", "end_year", False, "Ending year for analysis (e.g., 2022)"),
            ("Percolation Factor:", "f_percol", False, "Percolation factor (e.g., 0.9)"),
            ("Smax Factor:", "f_smax", False, "Smax factor (e.g., 0.818)"),
            ("Correction Factor:", "cf", False, "Correction factor (e.g., 50)"),
            ("Baseflow Factor:", "f_bf", False, "Baseflow factor (e.g., 0.095)"),
            ("Deep Percolation Factor:", "deep_percol_f", False, "Deep percolation factor (e.g., 0.905)")
        ]
        
        for label, key, is_dir, tooltip in sm_fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            self.full_entries[key] = QLineEdit()
            self.full_entries[key].setToolTip(tooltip)
            self.full_entries[key].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(self.full_entries[key])
            if is_dir:
                btn = QPushButton("Browse")
                btn.clicked.connect(lambda _, k=key: self.browse_directory(k, self.full_entries))
                btn.setCursor(Qt.PointingHandCursor)
                row.addWidget(btn)
            content_layout.addLayout(row)
        
        # Set default values
        self.full_entries["start_year"].setText("2019")
        self.full_entries["end_year"].setText("2022")
        self.full_entries["f_percol"].setText("0.9")
        self.full_entries["f_smax"].setText("0.818")
        self.full_entries["cf"].setText("50")
        self.full_entries["f_bf"].setText("0.095")
        self.full_entries["deep_percol_f"].setText("0.905")
        
        # Hydroloop inputs
        separator = QLabel()
        separator.setStyleSheet("border-top: 1px solid #ccc; margin: 20px 0;")
        content_layout.addWidget(separator)
        
        hydro_title = QLabel("Hydroloop Inputs")
        hydro_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71; margin: 10px;")
        hydro_title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(hydro_title)
        
        hydro_fields = [
            ("NC Directory:", "nc_dir", True, "Directory containing NetCDF files"),
            ("Results Directory:", "result_dir", True, "Directory to save results"),
            ("DEM File:", "dem_path", False, "GeoTIFF Files (*.tif *.tiff);;All Files (*)", "Digital Elevation Model file"),
            ("AEISW File:", "aeisw_path", False, "GeoTIFF Files (*.tif *.tiff);;All Files (*)", "AEISW GeoTIFF file"),
            ("Population File:", "population_path", False, "GeoTIFF Files (*.tif *.tiff);;All Files (*)", "Population GeoTIFF file"),
            ("WPL File:", "wpl_path", False, "GeoTIFF Files (*.tif *.tiff);;All Files (*)", "WPL GeoTIFF file"),
            ("EWR File:", "ewr_path", False, "All Files (*)", "EWR file"),
            ("Inflow File:", "inflow", False, "NetCDF Files (*.nc);;All Files (*)", "Inflow NetCDF file"),
            ("Outflow File:", "outflow", False, "NetCDF Files (*.nc);;All Files (*)", "Outflow NetCDF file"),
            ("Desalination File:", "desalination", False, "NetCDF Files (*.nc);;All Files (*)", "Desalination NetCDF file"),
            ("Basin Name:", "basin_name", False, "", "Name of the basin (e.g., Awash)"),
            ("Hydro Year End Month:", "hydro_year", False, "", "End month of hydrological year"),
            ("Output Unit:", "output_unit", False, "", "Unit for output (MCM or Km³)")
        ]
        
        file_fields = ["dem_path", "aeisw_path", "population_path", "wpl_path", "ewr_path", 
                      "inflow", "outflow", "desalination"]
        
        for label, key, is_dir, *args in hydro_fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            
            if key == "hydro_year":
                self.full_entries[key] = QComboBox()
                self.full_entries[key].addItems(['A-JAN', 'A-FEB', 'A-MAR', 'A-APR', 'A-MAY', 'A-JUN',
                                                'A-JUL', 'A-AUG', 'A-SEP', 'A-OCT', 'A-NOV', 'A-DEC'])
                self.full_entries[key].setCurrentText('A-OCT')
                self.full_entries[key].setToolTip(args[-1] if args else "")
            elif key == "output_unit":
                self.full_entries[key] = QComboBox()
                self.full_entries[key].addItems(['MCM (million cubic meters)', 'Km³ (cubic kilometers)'])
                self.full_entries[key].currentTextChanged.connect(self.update_unit_conversion)
                self.full_entries[key].setToolTip(args[-1] if args else "")
                self.full_entries["unit_conversion"] = QLineEdit()
                self.full_entries["unit_conversion"].setText("1e3")
                self.full_entries["unit_conversion"].setVisible(False)
            else:
                self.full_entries[key] = QLineEdit()
                self.full_entries[key].setToolTip(args[-1] if args else "")
                if key in file_fields:
                    self.full_entries[key].setReadOnly(True)
            
            if key != "unit_conversion":
                self.full_entries[key].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                row.addWidget(self.full_entries[key])
            
            if is_dir:
                btn = QPushButton("Browse")
                btn.clicked.connect(lambda _, k=key: self.browse_directory(k, self.full_entries))
                btn.setCursor(Qt.PointingHandCursor)
                row.addWidget(btn)
            elif key in file_fields:
                btn = QPushButton("Browse")
                btn.clicked.connect(lambda _, k=key, f=args[0] if args else "All Files (*)": self.browse_file(k, self.full_entries, f))
                btn.setCursor(Qt.PointingHandCursor)
                row.addWidget(btn)
            
            content_layout.addLayout(row)
        
        self.full_entries["basin_name"].setText("Awash")
        
        # Progress bar and log for full workflow
        separator = QLabel()
        separator.setStyleSheet("border-top: 1px solid #ccc; margin: 20px 0;")
        content_layout.addWidget(separator)
        
        full_run_title = QLabel("Run Full Workflow")
        full_run_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71; margin: 10px;")
        full_run_title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(full_run_title)
        
        self.full_step_label = QLabel("Current step: Ready")
        self.full_step_label.setStyleSheet("font-weight: bold; color: #3498db;")
        content_layout.addWidget(self.full_step_label)
        
        self.full_log = QTextEdit()
        self.full_log.setReadOnly(True)
        self.full_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.full_log)
        content_layout.setStretchFactor(self.full_log, 1)
        
        progress_layout = QHBoxLayout()
        self.full_progress = QProgressBar()
        self.full_progress.setMaximum(2100)
        self.full_progress_label = QLabel("0%")
        progress_layout.addWidget(self.full_progress)
        progress_layout.addWidget(self.full_progress_label)
        content_layout.addLayout(progress_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.full_run_btn = QPushButton("Run Full Workflow")
        self.full_run_btn.clicked.connect(self.run_full_workflow)
        self.full_run_btn.setFixedSize(200, 40)
        self.full_run_btn.setStyleSheet("background-color: #2ecc71;")
        self.full_run_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.full_run_btn)
        
        save_log_btn = QPushButton("Save Log")
        save_log_btn.clicked.connect(self.save_log(self.full_log))
        save_log_btn.setFixedSize(200, 40)
        save_log_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(save_log_btn)
        
        content_layout.addLayout(btn_layout)
        
        # Next button for manual workflow
        separator = QLabel()
        separator.setStyleSheet("border-top: 1px solid #ccc; margin: 20px 0;")
        content_layout.addWidget(separator)
        
        next_btn = QPushButton("Next: NetCDF Creation (Manual)")
        next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))
        next_btn.setFixedSize(250, 40)
        next_btn.setStyleSheet("background-color: #3498db;")
        next_btn.setCursor(Qt.PointingHandCursor)
        content_layout.addWidget(next_btn, alignment=Qt.AlignCenter)
        
        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        layout.setSpacing(20)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)

    def create_netcdf_page(self):
        """Create the NetCDF creation page with progress tracking"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("NetCDF File Creation")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #3498db; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Back button
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2 if self.workflow_type == "full" else 0))
        back_btn.setFixedSize(100, 40)
        back_btn.setStyleSheet("background-color: #e74c3c;")
        back_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)
        
        # Content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        
        # Display inputs (read-only) for full workflow
        if self.workflow_type == "full":
            fields = [
                ("Input TIFF Directory:", "input_tifs"),
                ("Shapefile:", "shapefile"),
                ("Template/Mask File:", "template_mask"),
                ("Output Directory:", "output_dir")
            ]
            
            for label, key in fields:
                row = QHBoxLayout()
                label_widget = QLabel(label)
                row.addWidget(label_widget)
                entry = QLineEdit(self.full_entries[key].text())
                entry.setReadOnly(True)
                entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                row.addWidget(entry)
                content_layout.addLayout(row)
        else:
            fields = [
                ("Input TIFF Directory:", "input_tifs", True, "Directory containing TIFF files"),
                ("Shapefile:", "shapefile", False, "Shapefile (*.shp)", "Shapefile for spatial reference"),
                ("Template/Mask File:", "template_mask", False, "GeoTIFF Files (*.tif *.tiff)", "Template and basin mask GeoTIFF file"),
                ("Output Directory:", "output_dir", True, "Directory to save NetCDF files and hydroloop results")
            ]
            
            self.netcdf_entries = {}
            for label, key, is_dir, *args in fields:
                row = QHBoxLayout()
                label_widget = QLabel(label)
                row.addWidget(label_widget)
                self.netcdf_entries[key] = QLineEdit()
                self.netcdf_entries[key].setToolTip(args[-1] if args else "")
                self.netcdf_entries[key].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                row.addWidget(self.netcdf_entries[key])
                btn = QPushButton("Browse")
                btn.setCursor(Qt.PointingHandCursor)
                if is_dir:
                    btn.clicked.connect(lambda _, k=key: self.browse_directory(k, self.netcdf_entries))
                else:
                    btn.clicked.connect(lambda _, k=key, f=args[0]: self.browse_file(k, self.netcdf_entries, f))
                row.addWidget(btn)
                content_layout.addLayout(row)

        # Add progress step label
        self.current_step_label = QLabel("Current step: Ready")
        self.current_step_label.setStyleSheet("font-weight: bold; color: #3498db;")
        content_layout.addWidget(self.current_step_label)
        
        self.netcdf_log = QTextEdit()
        self.netcdf_log.setReadOnly(True)
        self.netcdf_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.netcdf_log)
        content_layout.setStretchFactor(self.netcdf_log, 1)
        
        # Progress bar setup
        progress_layout = QHBoxLayout()
        self.netcdf_progress = QProgressBar()
        self.netcdf_progress.setMaximum(100)
        self.netcdf_progress_label = QLabel("0%")
        progress_layout.addWidget(self.netcdf_progress)
        progress_layout.addWidget(self.netcdf_progress_label)
        content_layout.addLayout(progress_layout)

        btn_layout = QHBoxLayout()
        self.netcdf_run_btn = QPushButton("Create NetCDF Files")
        self.netcdf_run_btn.clicked.connect(self.create_netcdf)
        self.netcdf_run_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.netcdf_run_btn)
        
        self.netcdf_next_btn = QPushButton("Next: Rain Interception")
        self.netcdf_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(4))
        self.netcdf_next_btn.setEnabled(False)
        self.netcdf_next_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.netcdf_next_btn)
        
        save_log_btn = QPushButton("Save Log")
        save_log_btn.clicked.connect(self.save_log(self.netcdf_log))
        save_log_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(save_log_btn)
        
        content_layout.addLayout(btn_layout)
        
        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        layout.setSpacing(20)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)

    def create_rain_page(self):
        """Create the rain interception page with progress tracking"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Rain Interception")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #3498db; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Back button
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))
        back_btn.setFixedSize(100, 40)
        back_btn.setStyleSheet("background-color: #e74c3c;")
        back_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)
        
        # Content
        content_layout = QVBoxLayout()
        
        # Display input (read-only) for full workflow
        if self.workflow_type == "full":
            row = QHBoxLayout()
            row.addWidget(QLabel("Input Directory:"))
            entry = QLineEdit(self.full_entries["rain_input"].text())
            entry.setReadOnly(True)
            entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(entry)
            content_layout.addLayout(row)
        else:
            row = QHBoxLayout()
            row.addWidget(QLabel("Input Directory:"))
            self.rain_input = QLineEdit()
            self.rain_input.setToolTip("Directory containing input files for rain interception")
            self.rain_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(self.rain_input)
            browse_btn = QPushButton("Browse")
            browse_btn.clicked.connect(lambda: self.browse_directory("rain_input", {"rain_input": self.rain_input}))
            browse_btn.setCursor(Qt.PointingHandCursor)
            row.addWidget(browse_btn)
            content_layout.addLayout(row)

        # Add progress step label
        self.rain_step_label = QLabel("Current step: Ready")
        self.rain_step_label.setStyleSheet("font-weight: bold; color: #3498db;")
        content_layout.addWidget(self.rain_step_label)
        
        self.rain_log = QTextEdit()
        self.rain_log.setReadOnly(True)
        self.rain_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.rain_log)
        content_layout.setStretchFactor(self.rain_log, 1)
        
        # Progress bar setup
        progress_layout = QHBoxLayout()
        self.rain_progress = QProgressBar()
        self.rain_progress.setMaximum(300)
        self.rain_progress_label = QLabel("0%")
        progress_layout.addWidget(self.rain_progress)
        progress_layout.addWidget(self.rain_progress_label)
        content_layout.addLayout(progress_layout)

        btn_layout = QHBoxLayout()
        self.rain_run_btn = QPushButton("Calculate Rain Interception")
        self.rain_run_btn.clicked.connect(self.calculate_rain)
        self.rain_run_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.rain_run_btn)
        
        self.rain_next_btn = QPushButton("Next: Soil Moisture Balance")
        self.rain_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(5))
        self.rain_next_btn.setEnabled(False)
        self.rain_next_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.rain_next_btn)
        
        save_log_btn = QPushButton("Save Log")
        save_log_btn.clicked.connect(self.save_log(self.rain_log))
        save_log_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(save_log_btn)
        
        content_layout.addLayout(btn_layout)
        
        layout.addLayout(content_layout)
        layout.setSpacing(20)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)

    def create_smbalance_page(self):
        """Create the soil moisture balance page with progress tracking"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Soil Moisture Balance")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #3498db; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Back button
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(4 if self.workflow_type == "full" else 1))
        back_btn.setFixedSize(100, 40)
        back_btn.setStyleSheet("background-color: #e74c3c;")
        back_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        # Content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        
        # Display inputs (read-only) for full workflow
        if self.workflow_type == "full":
            fields = [
                ("Input Directory:", "sm_input"),
                ("Start Year:", "start_year"),
                ("End Year:", "end_year"),
                ("Percolation Factor:", "f_percol"),
                ("Smax Factor:", "f_smax"),
                ("Correction Factor:", "cf"),
                ("Baseflow Factor:", "f_bf"),
                ("Deep Percolation Factor:", "deep_percol_f")
            ]
            
            for label, key in fields:
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                entry = QLineEdit(self.full_entries[key].text())
                entry.setReadOnly(True)
                entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                row.addWidget(entry)
                content_layout.addLayout(row)
        else:
            fields = [
                ("Input Directory:", "sm_input", True, "Directory containing input files"),
                ("Start Year:", "start_year", False, "Starting year for analysis (e.g., 2019)"),
                ("End Year:", "end_year", False, "Ending year for analysis (e.g., 2022)"),
                ("Percolation Factor:", "f_percol", False, "Percolation factor (e.g., 0.9)"),
                ("Smax Factor:", "f_smax", False, "Smax factor (e.g., 52)"),
                ("Correction Factor:", "cf", False, "Correction factor (e.g., 50)"),
                ("Baseflow Factor:", "f_bf", False, "Baseflow factor (e.g., 0.095)"),
                ("Deep Percolation Factor:", "deep_percol_f", False, "Deep percolation factor (e.g., 0.905)")
            ]
            
            self.sm_entries = {}
            for label, key, is_dir, tooltip in fields:
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                self.sm_entries[key] = QLineEdit()
                self.sm_entries[key].setToolTip(tooltip)
                self.sm_entries[key].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                row.addWidget(self.sm_entries[key])
                if is_dir:
                    btn = QPushButton("Browse")
                    btn.clicked.connect(lambda _, k=key: self.browse_directory(k, self.sm_entries))
                    btn.setCursor(Qt.PointingHandCursor)
                    row.addWidget(btn)
                content_layout.addLayout(row)
            
            # Set default values
            self.sm_entries["start_year"].setText("2019")
            self.sm_entries["end_year"].setText("2022")
            self.sm_entries["f_percol"].setText("0.9")
            self.sm_entries["f_smax"].setText("52")
            self.sm_entries["cf"].setText("50")
            self.sm_entries["f_bf"].setText("0.095")
            self.sm_entries["deep_percol_f"].setText("0.905")

        # Add progress step label
        self.sm_step_label = QLabel("Current step: Ready")
        self.sm_step_label.setStyleSheet("font-weight: bold; color: #3498db;")
        content_layout.addWidget(self.sm_step_label)
        
        self.sm_log = QTextEdit()
        self.sm_log.setReadOnly(True)
        self.sm_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.sm_log)
        content_layout.setStretchFactor(self.sm_log, 1)
        
        # Progress bar setup
        progress_layout = QHBoxLayout()
        self.sm_progress = QProgressBar()
        self.sm_progress.setMaximum(100)
        self.sm_progress_label = QLabel("0%")
        progress_layout.addWidget(self.sm_progress)
        progress_layout.addWidget(self.sm_progress_label)
        content_layout.addLayout(progress_layout)

        btn_layout = QHBoxLayout()
        self.sm_run_btn = QPushButton("Run Soil Moisture Balance")
        self.sm_run_btn.clicked.connect(self.run_smbalance)
        self.sm_run_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.sm_run_btn)
        
        self.sm_next_btn = QPushButton("Next: Hydroloop")
        self.sm_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(6))
        self.sm_next_btn.setEnabled(False)
        self.sm_next_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.sm_next_btn)
        
        save_log_btn = QPushButton("Save Log")
        save_log_btn.clicked.connect(self.save_log(self.sm_log))
        save_log_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(save_log_btn)
        
        content_layout.addLayout(btn_layout)
        
        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        layout.setSpacing(20)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)

    def create_hydroloop_page(self):
        """Create the hydroloop page with progress tracking"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Hydroloop Analysis")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #3498db; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Back button
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(5 if self.workflow_type == "full" else 1))
        back_btn.setFixedSize(100, 40)
        back_btn.setStyleSheet("background-color: #e74c3c;")
        back_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        # Content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        
        # Display inputs (read-only) for full workflow
        if self.workflow_type == "full":
            fields = [
                ("Input Files Directory:", "nc_dir"),
                ("Results Directory:", "result_dir"),
                ("Template/Mask File:", "template_mask"),
                ("DEM File:", "dem_path"),
                ("AEISW File:", "aeisw_path"),
                ("Population File:", "population_path"),
                ("WPL File:", "wpl_path"),
                ("EWR File:", "ewr_path"),
                ("Inflow File:", "inflow"),
                ("Outflow File:", "outflow"),
                ("Desalination File:", "desalination"),
                ("Basin Name:", "basin_name"),
                ("Hydro Year End Month:", "hydro_year"),
                ("Output Unit:", "output_unit")
            ]
            
            for label, key in fields:
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                entry = QLineEdit(self.full_entries[key].text() if isinstance(self.full_entries[key], QLineEdit) else self.full_entries[key].currentText())
                entry.setReadOnly(True)
                entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                row.addWidget(entry)
                content_layout.addLayout(row)
        else:
            fields = [
                ("Input Files Directory:", "nc_dir", True, "Directory containing NetCDF files"),
                ("Results Directory:", "result_dir", True, "Directory to save results"),
                ("Basin Mask File:", "template_mask", False, "GeoTIFF Files (*.tif *.tiff);;All Files (*)", "Basin mask GeoTIFF file"),
                ("DEM File:", "dem_path", False, "GeoTIFF Files (*.tif *.tiff);;All Files (*)", "Digital Elevation Model file"),
                ("AEISW File:", "aeisw_path", False, "GeoTIFF Files (*.tif *.tiff);;All Files (*)", "AEISW GeoTIFF file"),
                ("Population File:", "population_path", False, "GeoTIFF Files (*.tif *.tiff);;All Files (*)", "Population GeoTIFF file"),
                ("WPL File:", "wpl_path", False, "GeoTIFF Files (*.tif *.tiff);;All Files (*)", "WPL GeoTIFF file"),
                ("EWR File:", "ewr_path", False, "All Files (*)", "EWR file"),
                ("Inflow File:", "inflow", False, "NetCDF Files (*.nc);;All Files (*)", "Inflow NetCDF file"),
                ("Outflow File:", "outflow", False, "NetCDF Files (*.nc);;All Files (*)", "Outflow NetCDF file"),
                ("Desalination File:", "desalination", False, "NetCDF Files (*.nc);;All Files (*)", "Desalination NetCDF file"),
                ("Basin Name:", "basin_name", False, "", "Name of the basin (e.g., Awash)"),
                ("Hydro Year End Month:", "hydro_year", False, "", "End month of hydrological year"),
                ("Output Unit:", "output_unit", False, "", "Unit for output (MCM or Km³)")
            ]
            
            self.hydro_entries = {}
            file_fields = ["template_mask", "dem_path", "aeisw_path", "population_path", 
                          "wpl_path", "ewr_path", "inflow", "outflow", "desalination"]
            
            for label, key, is_dir, *args in fields:
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                
                if key == "hydro_year":
                    self.hydro_entries[key] = QComboBox()
                    self.hydro_entries[key].addItems(['A-JAN', 'A-FEB', 'A-MAR', 'A-APR', 'A-MAY', 'A-JUN',
                                                     'A-JUL', 'A-AUG', 'A-SEP', 'A-OCT', 'A-NOV', 'A-DEC'])
                    self.hydro_entries[key].setCurrentText('A-OCT')
                    self.hydro_entries[key].setToolTip(args[-1] if args else "")
                elif key == "output_unit":
                    self.hydro_entries[key] = QComboBox()
                    self.hydro_entries[key].addItems(['MCM (million cubic meters)', 'Km³ (cubic kilometers)'])
                    self.hydro_entries[key].currentTextChanged.connect(self.update_unit_conversion)
                    self.hydro_entries[key].setToolTip(args[-1] if args else "")
                    self.hydro_entries["unit_conversion"] = QLineEdit()
                    self.hydro_entries["unit_conversion"].setText("1e3")
                    self.hydro_entries["unit_conversion"].setVisible(False)
                else:
                    self.hydro_entries[key] = QLineEdit()
                    self.hydro_entries[key].setToolTip(args[-1] if args else "")
                    if key in file_fields:
                        self.hydro_entries[key].setReadOnly(True)
                
                if key != "unit_conversion":
                    self.hydro_entries[key].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    row.addWidget(self.hydro_entries[key])
                
                if is_dir:
                    btn = QPushButton("Browse")
                    btn.clicked.connect(lambda _, k=key: self.browse_directory(k, self.hydro_entries))
                    btn.setCursor(Qt.PointingHandCursor)
                    row.addWidget(btn)
                elif key in file_fields:
                    btn = QPushButton("Browse")
                    btn.clicked.connect(lambda _, k=key, f=args[0] if args else "All Files (*)": self.browse_file(k, self.hydro_entries, f))
                    btn.setCursor(Qt.PointingHandCursor)
                    row.addWidget(btn)
                
                content_layout.addLayout(row)

            self.hydro_entries["basin_name"].setText("Awash")

        # Add progress step label
        self.hydro_step_label = QLabel("Current step: Ready")
        self.hydro_step_label.setStyleSheet("font-weight: bold; color: #3498db;")
        content_layout.addWidget(self.hydro_step_label)
        
        self.hydro_log = QTextEdit()
        self.hydro_log.setReadOnly(True)
        self.hydro_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.hydro_log)
        content_layout.setStretchFactor(self.hydro_log, 1)
        
        # Progress bar setup
        progress_layout = QHBoxLayout()
        self.hydro_progress = QProgressBar()
        self.hydro_progress.setMaximum(500)
        self.hydro_progress_label = QLabel("0%")
        progress_layout.addWidget(self.hydro_progress)
        progress_layout.addWidget(self.hydro_progress_label)
        content_layout.addLayout(progress_layout)

        btn_layout = QHBoxLayout()
        self.hydro_init_btn = QPushButton("Initialize Hydroloop")
        self.hydro_init_btn.clicked.connect(self.init_hydroloop)
        self.hydro_init_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.hydro_init_btn)

        self.hydro_run_btn = QPushButton("Run All Steps")
        self.hydro_run_btn.setEnabled(False)
        self.hydro_run_btn.clicked.connect(self.run_hydroloop)
        self.hydro_run_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.hydro_run_btn)

        self.hydro_next_btn = QPushButton("Next: Generate Sheets")
        self.hydro_next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(7))
        self.hydro_next_btn.setEnabled(False)
        self.hydro_next_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.hydro_next_btn)
        
        save_log_btn = QPushButton("Save Log")
        save_log_btn.clicked.connect(self.save_log(self.hydro_log))
        save_log_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(save_log_btn)
        
        content_layout.addLayout(btn_layout)
        
        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        layout.setSpacing(20)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)

    def create_sheets_page(self):
        """Create the sheets generation page with progress tracking"""
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Generate Sheets")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #3498db; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Back button
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(6))
        back_btn.setFixedSize(100, 40)
        back_btn.setStyleSheet("background-color: #e74c3c;")
        back_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(back_btn, alignment=Qt.AlignLeft)

        # Content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout()

        # Sheet 1 Section
        sheet1_frame = QVBoxLayout()
        sheet1_title = QLabel("Sheet 1 Generation")
        sheet1_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71; margin: 10px;")
        sheet1_title.setAlignment(Qt.AlignCenter)
        sheet1_frame.addWidget(sheet1_title)

        # Add progress step label
        self.sheet1_step_label = QLabel("Current step: Ready")
        self.sheet1_step_label.setStyleSheet("font-weight: bold; color: #2ecc71;")
        sheet1_frame.addWidget(self.sheet1_step_label)

        self.sheet1_log = QTextEdit()
        self.sheet1_log.setReadOnly(True)
        self.sheet1_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sheet1_frame.addWidget(self.sheet1_log)
        sheet1_frame.setStretchFactor(self.sheet1_log, 1)

        # Progress bar setup
        progress_layout = QHBoxLayout()
        self.sheet1_progress = QProgressBar()
        self.sheet1_progress.setMaximum(200)
        self.sheet1_progress_label = QLabel("0%")
        progress_layout.addWidget(self.sheet1_progress)
        progress_layout.addWidget(self.sheet1_progress_label)
        sheet1_frame.addLayout(progress_layout)

        sheet1_btn_layout = QHBoxLayout()
        self.sheet1_run_btn = QPushButton("Generate Sheet 1")
        self.sheet1_run_btn.clicked.connect(self.generate_sheet1)
        self.sheet1_run_btn.setCursor(Qt.PointingHandCursor)
        sheet1_btn_layout.addWidget(self.sheet1_run_btn)

        save_sheet1_log_btn = QPushButton("Save Sheet 1 Log")
        save_sheet1_log_btn.clicked.connect(self.save_log(self.sheet1_log))
        save_sheet1_log_btn.setCursor(Qt.PointingHandCursor)
        sheet1_btn_layout.addWidget(save_sheet1_log_btn)

        sheet1_frame.addLayout(sheet1_btn_layout)
        content_layout.addLayout(sheet1_frame)

        # Separator
        separator = QLabel()
        separator.setStyleSheet("border-top: 1px solid #ccc; margin: 20px 0;")
        content_layout.addWidget(separator)

        # Sheet 2 Section
        sheet2_frame = QVBoxLayout()
        sheet2_title = QLabel("Sheet 2 Generation")
        sheet2_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71; margin: 10px;")
        sheet2_title.setAlignment(Qt.AlignCenter)
        sheet2_frame.addWidget(sheet2_title)

        # Add progress step label
        self.sheet2_step_label = QLabel("Current step: Ready")
        self.sheet2_step_label.setStyleSheet("font-weight: bold; color: #2ecc71;")
        sheet2_frame.addWidget(self.sheet2_step_label)

        self.sheet2_log = QTextEdit()
        self.sheet2_log.setReadOnly(True)
        self.sheet2_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sheet2_frame.addWidget(self.sheet2_log)
        sheet2_frame.setStretchFactor(self.sheet2_log, 1)

        # Progress bar setup
        progress_layout = QHBoxLayout()
        self.sheet2_progress = QProgressBar()
        self.sheet2_progress.setMaximum(200)
        self.sheet2_progress_label = QLabel("0%")
        progress_layout.addWidget(self.sheet2_progress)
        progress_layout.addWidget(self.sheet2_progress_label)
        sheet2_frame.addLayout(progress_layout)

        sheet2_btn_layout = QHBoxLayout()
        self.sheet2_run_btn = QPushButton("Generate Sheet 2")
        self.sheet2_run_btn.clicked.connect(self.generate_sheet2)
        self.sheet2_run_btn.setCursor(Qt.PointingHandCursor)
        sheet2_btn_layout.addWidget(self.sheet2_run_btn)

        save_sheet2_log_btn = QPushButton("Save Sheet 2 Log")
        save_sheet2_log_btn.clicked.connect(self.save_log(self.sheet2_log))
        save_sheet2_log_btn.setCursor(Qt.PointingHandCursor)
        sheet2_btn_layout.addWidget(save_sheet2_log_btn)

        sheet2_frame.addLayout(sheet2_btn_layout)
        content_layout.addLayout(sheet2_frame)

        # Finish button
        finish_btn_layout = QHBoxLayout()
        self.sheets_finish_btn = QPushButton("Finish")
        self.sheets_finish_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.sheets_finish_btn.setCursor(Qt.PointingHandCursor)
        finish_btn_layout.addWidget(self.sheets_finish_btn)
        content_layout.addLayout(finish_btn_layout)

        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        layout.setSpacing(20)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)