"""
Main Window for Battery Optimizer GUI Application

This module contains the main window class that provides the primary
user interface for the battery optimization application.
"""

import sys
import os
from pathlib import Path
import pandas as pd
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QFileDialog, QTextEdit,
    QProgressBar, QSplitter, QFrame, QGroupBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QTabWidget, QScrollArea,
    QStatusBar, QDateEdit, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, QSettings, QTimer, pyqtSlot, QDate
from PyQt6.QtGui import QFont, QPixmap, QAction, QIcon

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from datetime import datetime, timedelta

# Configure matplotlib for Japanese fonts
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False
# For Japanese text, try to use system fonts
try:
    import matplotlib.font_manager as fm
    # Try to find a Japanese font
    japanese_fonts = ['Hiragino Sans', 'Apple Gothic', 'Noto Sans CJK JP', 'DejaVu Sans']
    for font in japanese_fonts:
        try:
            plt.rcParams['font.family'] = font
            break
        except:
            continue
except:
    pass

# Import our custom modules
from core.optimization_engine import OptimizationEngine
from config.area_config import (
    get_area_list, get_voltage_list, parse_area_selection,
    DEFAULT_OPTIMIZATION_PARAMS, validate_optimization_params
)


class BatteryOptimizerMainWindow(QMainWindow):
    """Main window for the Battery Optimizer application"""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings()
        self.optimization_engine = None
        self.optimization_results = None
        self.current_data = None
        
        # Date range selection variables
        self.date_range_start = None
        self.date_range_end = None
        self.date_range_mode = "all"  # "all", "range", "last_7", "last_30"
        
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Battery Optimizer 2.0")
        self.setGeometry(100, 100, 1600, 1000)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel: Parameters and controls
        left_panel = self.create_control_panel()
        left_panel.setMaximumWidth(500)
        left_panel.setMinimumWidth(400)
        
        # Right panel: Results and visualization
        right_panel = self.create_results_panel()
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 1200])
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.create_status_bar()
        
        # Initialize optimization engine
        self.optimization_engine = OptimizationEngine(self)
        self.connect_optimization_signals()
        
    def create_menu_bar(self):
        """Create the application menu bar (macOS native)"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('ファイル')
        
        open_action = QAction('CSV読み込み...', self)
        open_action.triggered.connect(self.load_csv_file)
        open_action.setShortcut('Ctrl+O')
        file_menu.addAction(open_action)
        
        save_action = QAction('結果保存...', self)
        save_action.triggered.connect(self.save_results)
        save_action.setShortcut('Ctrl+S')
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction('終了', self)
        quit_action.triggered.connect(self.close)
        quit_action.setShortcut('Ctrl+Q')
        file_menu.addAction(quit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu('編集')
        
        reset_action = QAction('パラメータリセット', self)
        reset_action.triggered.connect(self.reset_parameters)
        edit_menu.addAction(reset_action)
        
        # View menu
        view_menu = menubar.addMenu('表示')
        
        refresh_action = QAction('グラフ更新', self)
        refresh_action.triggered.connect(self.update_visualization)
        refresh_action.setShortcut('F5')
        view_menu.addAction(refresh_action)
        
        # Help menu
        help_menu = menubar.addMenu('ヘルプ')
        
        about_action = QAction('About...', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了")
        
    def create_control_panel(self):
        """Create the left control panel with parameters"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout(panel)
        
        # Application title and logo area
        header_layout = QVBoxLayout()
        
        title_label = QLabel("Battery Optimizer 2.0")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        subtitle_label = QLabel("バッテリー蓄電最適化システム")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: gray;")
        header_layout.addWidget(subtitle_label)
        
        layout.addLayout(header_layout)
        layout.addWidget(self.create_separator())
        
        # Create scrollable area for parameters
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Basic parameters group
        basic_group = self.create_basic_parameters_group()
        scroll_layout.addWidget(basic_group)
        
        # Advanced parameters group
        advanced_group = self.create_advanced_parameters_group()
        scroll_layout.addWidget(advanced_group)
        
        # File loading group
        file_group = self.create_file_group()
        scroll_layout.addWidget(file_group)
        
        # Control buttons
        control_group = self.create_control_buttons()
        scroll_layout.addWidget(control_group)
        
        # Progress and log
        progress_group = self.create_progress_group()
        scroll_layout.addWidget(progress_group)
        
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        return panel
        
    def create_basic_parameters_group(self):
        """Create basic parameters group"""
        group = QGroupBox("基本パラメータ")
        layout = QGridLayout(group)
        
        # Area selection
        layout.addWidget(QLabel("対象エリア:"), 0, 0)
        self.area_combo = QComboBox()
        self.area_combo.addItems(get_area_list())
        self.area_combo.setCurrentIndex(2)  # Tokyo default
        layout.addWidget(self.area_combo, 0, 1)
        
        # Voltage type
        layout.addWidget(QLabel("電圧区分:"), 1, 0)
        self.voltage_combo = QComboBox()
        self.voltage_combo.addItems(get_voltage_list())
        self.voltage_combo.setCurrentIndex(1)  # HV default
        layout.addWidget(self.voltage_combo, 1, 1)
        
        # Battery power
        layout.addWidget(QLabel("バッテリー出力 (kW):"), 2, 0)
        self.power_input = QSpinBox()
        self.power_input.setRange(10, 100000)
        self.power_input.setValue(1000)
        self.power_input.setSuffix(" kW")
        layout.addWidget(self.power_input, 2, 1)
        
        # Battery capacity
        layout.addWidget(QLabel("バッテリー容量 (kWh):"), 3, 0)
        self.capacity_input = QSpinBox()
        self.capacity_input.setRange(10, 1000000)
        self.capacity_input.setValue(4000)
        self.capacity_input.setSuffix(" kWh")
        layout.addWidget(self.capacity_input, 3, 1)
        
        # Battery loss rate
        layout.addWidget(QLabel("バッテリー損失率 (%):"), 4, 0)
        self.loss_rate_input = QDoubleSpinBox()
        self.loss_rate_input.setRange(0.0, 50.0)
        self.loss_rate_input.setValue(5.0)
        self.loss_rate_input.setSuffix(" %")
        self.loss_rate_input.setDecimals(2)
        layout.addWidget(self.loss_rate_input, 4, 1)
        
        return group
        
    def create_advanced_parameters_group(self):
        """Create advanced parameters group"""
        group = QGroupBox("詳細設定")
        layout = QGridLayout(group)
        
        # Daily cycle limit
        layout.addWidget(QLabel("日次上限:"), 0, 0)
        self.daily_cycle_input = QSpinBox()
        self.daily_cycle_input.setRange(0, 10)
        self.daily_cycle_input.setValue(1)
        self.daily_cycle_input.setSpecialValueText("制限なし")
        layout.addWidget(self.daily_cycle_input, 0, 1)
        
        # Forecast period
        layout.addWidget(QLabel("予測対象スロット数:"), 1, 0)
        self.forecast_period_input = QSpinBox()
        self.forecast_period_input.setRange(24, 168)
        self.forecast_period_input.setValue(48)
        self.forecast_period_input.setSuffix(" スロット")
        layout.addWidget(self.forecast_period_input, 1, 1)
        
        # EPRX1 block size
        layout.addWidget(QLabel("EPRX1連続スロット数:"), 2, 0)
        self.eprx1_block_input = QSpinBox()
        self.eprx1_block_input.setRange(1, 12)
        self.eprx1_block_input.setValue(3)
        layout.addWidget(self.eprx1_block_input, 2, 1)
        
        # EPRX1 cooldown
        layout.addWidget(QLabel("EPRX1クールダウン:"), 3, 0)
        self.eprx1_cooldown_input = QSpinBox()
        self.eprx1_cooldown_input.setRange(0, 12)
        self.eprx1_cooldown_input.setValue(2)
        layout.addWidget(self.eprx1_cooldown_input, 3, 1)
        
        # Max daily EPRX1 slots
        layout.addWidget(QLabel("EPRX1日次上限:"), 4, 0)
        self.max_eprx1_input = QSpinBox()
        self.max_eprx1_input.setRange(0, 48)
        self.max_eprx1_input.setValue(6)
        self.max_eprx1_input.setSpecialValueText("制限なし")
        layout.addWidget(self.max_eprx1_input, 4, 1)
        
        # Yearly cycle limit
        layout.addWidget(QLabel("年間サイクル上限:"), 5, 0)
        self.yearly_cycle_input = QSpinBox()
        self.yearly_cycle_input.setRange(0, 5000)
        self.yearly_cycle_input.setValue(365)
        self.yearly_cycle_input.setSpecialValueText("制限なし")
        self.yearly_cycle_input.setSuffix(" サイクル")
        layout.addWidget(self.yearly_cycle_input, 5, 1)
        
        # Annual degradation rate
        layout.addWidget(QLabel("年間劣化率:"), 6, 0)
        self.degradation_input = QDoubleSpinBox()
        self.degradation_input.setRange(0.0, 10.0)
        self.degradation_input.setValue(3.0)
        self.degradation_input.setSuffix(" %")
        self.degradation_input.setDecimals(1)
        layout.addWidget(self.degradation_input, 6, 1)
        
        # Performance mode selection
        layout.addWidget(QLabel("パフォーマンスモード:"), 7, 0)
        self.performance_mode_combo = QComboBox()
        self.performance_mode_combo.addItems([
            "高速モード (simple)",
            "標準モード (basic)", 
            "完全モード (full)"
        ])
        self.performance_mode_combo.setCurrentIndex(0)  # Default to simple mode for best performance
        self.performance_mode_combo.currentTextChanged.connect(self.on_performance_mode_changed)
        self.performance_mode_combo.setToolTip(
            "高速モード: EPRX1制約なし、最高速度（推奨）\n"
            "標準モード: 簡易EPRX1制約、バランス型\n"
            "完全モード: 全EPRX1制約、Streamlit完全一致（大容量データで低速）"
        )
        layout.addWidget(self.performance_mode_combo, 7, 1)
        
        return group
        
    def create_file_group(self):
        """Create file loading group"""
        group = QGroupBox("データファイル")
        layout = QVBoxLayout(group)
        
        # File selection button
        self.file_button = QPushButton("CSVファイルを選択...")
        self.file_button.clicked.connect(self.load_csv_file)
        layout.addWidget(self.file_button)
        
        # File info label
        self.file_info_label = QLabel("ファイルが選択されていません")
        self.file_info_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.file_info_label)
        
        # Download template button
        template_button = QPushButton("CSVテンプレートをダウンロード")
        template_button.clicked.connect(self.download_template)
        template_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                padding: 5px;
            }
        """)
        layout.addWidget(template_button)
        
        return group
        
    def create_control_buttons(self):
        """Create control buttons group"""
        group = QGroupBox("実行制御")
        layout = QVBoxLayout(group)
        
        # Main optimization button
        self.optimize_button = QPushButton("最適化を実行")
        self.optimize_button.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056CC;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.optimize_button.setEnabled(False)
        self.optimize_button.clicked.connect(self.run_optimization)
        layout.addWidget(self.optimize_button)
        
        # Cancel button
        self.cancel_button = QPushButton("キャンセル")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #FF3B30;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #D70015;
            }
        """)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_optimization)
        layout.addWidget(self.cancel_button)
        
        return group
        
    def create_progress_group(self):
        """Create progress monitoring group"""
        group = QGroupBox("実行状況")
        layout = QVBoxLayout(group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("待機中...")
        layout.addWidget(self.status_label)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monaco", 10))  # Monospace font for macOS
        layout.addWidget(self.log_text)
        
        return group
        
    def create_results_panel(self):
        """Create the right results panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Create tab widget for different views
        self.tab_widget = QTabWidget()
        
        # Visualization tab
        viz_tab = self.create_visualization_tab()
        self.tab_widget.addTab(viz_tab, "グラフ")
        
        # Results table tab
        table_tab = self.create_table_tab()
        self.tab_widget.addTab(table_tab, "詳細データ")
        
        # Summary tab
        summary_tab = self.create_summary_tab()
        self.tab_widget.addTab(summary_tab, "サマリー")
        
        layout.addWidget(self.tab_widget)
        
        return panel
        
    def create_visualization_tab(self):
        """Create visualization tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Chart controls
        controls_frame = QFrame()
        controls_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        controls_layout = QVBoxLayout(controls_frame)
        
        # Date range selection group
        date_group = QGroupBox("表示期間選択")
        date_layout = QGridLayout(date_group)
        
        # Period preset radio buttons
        self.date_range_group = QButtonGroup()
        
        self.all_period_radio = QRadioButton("全期間")
        self.all_period_radio.setChecked(True)
        self.all_period_radio.toggled.connect(lambda: self.set_date_range_mode("all"))
        self.date_range_group.addButton(self.all_period_radio)
        date_layout.addWidget(self.all_period_radio, 0, 0)
        
        self.last_7_radio = QRadioButton("最近7日間")
        self.last_7_radio.toggled.connect(lambda: self.set_date_range_mode("last_7"))
        self.date_range_group.addButton(self.last_7_radio)
        date_layout.addWidget(self.last_7_radio, 0, 1)
        
        self.last_30_radio = QRadioButton("最近30日間")
        self.last_30_radio.toggled.connect(lambda: self.set_date_range_mode("last_30"))
        self.date_range_group.addButton(self.last_30_radio)
        date_layout.addWidget(self.last_30_radio, 0, 2)
        
        self.custom_range_radio = QRadioButton("期間指定")
        self.custom_range_radio.toggled.connect(lambda: self.set_date_range_mode("range"))
        self.date_range_group.addButton(self.custom_range_radio)
        date_layout.addWidget(self.custom_range_radio, 1, 0)
        
        # Custom date range selectors
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setEnabled(False)
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.start_date_edit.dateChanged.connect(self.on_date_range_changed)
        date_layout.addWidget(QLabel("開始日:"), 1, 1)
        date_layout.addWidget(self.start_date_edit, 1, 2)
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setEnabled(False)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.dateChanged.connect(self.on_date_range_changed)
        date_layout.addWidget(QLabel("終了日:"), 1, 3)
        date_layout.addWidget(self.end_date_edit, 1, 4)
        
        # Apply button
        apply_button = QPushButton("適用")
        apply_button.clicked.connect(self.update_visualization)
        date_layout.addWidget(apply_button, 1, 5)
        
        controls_layout.addWidget(date_group)
        
        # Additional controls
        chart_controls_layout = QHBoxLayout()
        
        refresh_chart_button = QPushButton("グラフ更新")
        refresh_chart_button.clicked.connect(self.update_visualization)
        chart_controls_layout.addWidget(refresh_chart_button)
        
        chart_controls_layout.addStretch()
        controls_layout.addLayout(chart_controls_layout)
        
        layout.addWidget(controls_frame)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(12, 8))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Initialize empty chart
        self.init_empty_chart()
        
        return widget
        
    def create_table_tab(self):
        """Create results table tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Results table
        self.results_table = QTableWidget()
        layout.addWidget(self.results_table)
        
        # Table controls
        controls_layout = QHBoxLayout()
        
        export_button = QPushButton("CSVエクスポート")
        export_button.clicked.connect(self.export_results)
        controls_layout.addWidget(export_button)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        return widget
        
    def create_summary_tab(self):
        """Create summary tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Summary display
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Monaco", 12))
        layout.addWidget(self.summary_text)
        
        return widget
        
    def create_separator(self):
        """Create a horizontal separator line"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line
        
    def set_date_range_mode(self, mode):
        """Set date range selection mode"""
        old_mode = getattr(self, 'date_range_mode', None)
        self.date_range_mode = mode
        
        # Enable/disable custom date controls
        if mode == "range":
            self.start_date_edit.setEnabled(True)
            self.end_date_edit.setEnabled(True)
        else:
            self.start_date_edit.setEnabled(False)
            self.end_date_edit.setEnabled(False)
            
        # Log mode change
        self.add_log_message(f"期間選択モード変更: {old_mode} → {mode}")
            
        # Auto-update visualization for preset modes
        if mode != "range" and self.optimization_results:
            self.update_visualization()
    
    def on_date_range_changed(self):
        """Handle custom date range changes"""
        if self.date_range_mode == "range":
            start_qdate = self.start_date_edit.date()
            end_qdate = self.end_date_edit.date()
            
            # Convert QDate to Python date for comparison
            start_date = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day()).date()
            end_date = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day()).date()
            
            # Ensure start date is before end date
            if start_date > end_date:
                self.end_date_edit.setDate(self.start_date_edit.date())
    
    def on_performance_mode_changed(self):
        """Handle performance mode change"""
        current_mode = self.performance_mode_combo.currentText()
        
        if "simple" in current_mode:
            self.add_log_message("💨 高速モード選択: EPRX1制約なしで最高速度")
        elif "basic" in current_mode:
            self.add_log_message("⚡ 標準モード選択: 簡易EPRX1制約、バランス型（推奨）")
        elif "full" in current_mode:
            self.add_log_message("🔧 完全モード選択: 全EPRX1制約、Streamlit完全一致（大容量データで低速）")
            self.add_log_message("⚠️  完全モードは大容量データで時間がかかる場合があります")
    
    def get_filtered_data(self, df):
        """Filter data based on selected date range"""
        if df is None or df.empty:
            return df
            
        # Ensure datetime column exists
        if 'datetime' not in df.columns:
            df = df.copy()
            df['datetime'] = pd.to_datetime(df['date']) + pd.to_timedelta((df['slot'] - 1) * 30, unit='minutes')
        
        original_count = len(df)
        
        # Apply date range filter based on mode
        if self.date_range_mode == "all":
            filtered_df = df
        elif self.date_range_mode == "last_7":
            cutoff_date = df['datetime'].max() - timedelta(days=7)
            filtered_df = df[df['datetime'] >= cutoff_date]
            self.add_log_message(f"最近7日間フィルター: {original_count} → {len(filtered_df)} 行")
        elif self.date_range_mode == "last_30":
            cutoff_date = df['datetime'].max() - timedelta(days=30)
            filtered_df = df[df['datetime'] >= cutoff_date]
            self.add_log_message(f"最近30日間フィルター: {original_count} → {len(filtered_df)} 行")
        elif self.date_range_mode == "range":
            start_qdate = self.start_date_edit.date()
            end_qdate = self.end_date_edit.date()
            
            # Convert QDate to Python date
            start_date = datetime(start_qdate.year(), start_qdate.month(), start_qdate.day()).date()
            end_date = datetime(end_qdate.year(), end_qdate.month(), end_qdate.day()).date()
            
            # Convert to datetime for comparison
            start_datetime = pd.Timestamp(start_date)
            end_datetime = pd.Timestamp(end_date) + pd.Timedelta(days=1)  # Include full end day
            
            filtered_df = df[(df['datetime'] >= start_datetime) & (df['datetime'] < end_datetime)]
            self.add_log_message(f"期間指定フィルター ({start_date} - {end_date}): {original_count} → {len(filtered_df)} 行")
        else:
            filtered_df = df
        
        # Debug: Check if filtered data is empty
        if filtered_df.empty:
            self.add_log_message(f"警告: フィルター後のデータが空です (モード: {self.date_range_mode})")
            if not df.empty:
                data_range = f"{df['datetime'].min()} から {df['datetime'].max()}"
                self.add_log_message(f"元データの日付範囲: {data_range}")
        
        return filtered_df
        
    def update_date_range_controls(self, df):
        """Update date range controls based on loaded data"""
        if df is None or df.empty:
            return
            
        # Get date range from data
        df_dates = pd.to_datetime(df['date'])
        min_date = df_dates.min().date()
        max_date = df_dates.max().date()
        
        # Update date edit controls
        self.start_date_edit.setMinimumDate(QDate(min_date))
        self.start_date_edit.setMaximumDate(QDate(max_date))
        self.start_date_edit.setDate(QDate(min_date))
        
        self.end_date_edit.setMinimumDate(QDate(min_date))
        self.end_date_edit.setMaximumDate(QDate(max_date))
        self.end_date_edit.setDate(QDate(max_date))
        
    def connect_optimization_signals(self):
        """Connect optimization engine signals to UI slots"""
        self.optimization_engine.progress_updated.connect(self.update_progress)
        self.optimization_engine.status_updated.connect(self.update_status)
        self.optimization_engine.log_updated.connect(self.add_log_message)
        self.optimization_engine.optimization_completed.connect(self.on_optimization_completed)
        self.optimization_engine.optimization_failed.connect(self.on_optimization_failed)
        
    @pyqtSlot()
    def load_csv_file(self):
        """Load CSV file with price data"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "CSVファイルを選択",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                # Load and validate CSV
                df = pd.read_csv(file_path)
                
                # Basic validation
                required_cols = {
                    "date", "slot", "JEPX_prediction", "JEPX_actual",
                    "EPRX1_prediction", "EPRX3_prediction", 
                    "EPRX1_actual", "EPRX3_actual", "imbalance"
                }
                
                missing_cols = required_cols - set(df.columns)
                if missing_cols:
                    raise ValueError(f"必須列が不足しています: {', '.join(missing_cols)}")
                
                # Convert date column
                df['date'] = pd.to_datetime(df['date'])
                
                self.current_data = df
                self.file_info_label.setText(f"✓ {Path(file_path).name} ({len(df)} 行)")
                self.file_info_label.setStyleSheet("color: green;")
                self.optimize_button.setEnabled(True)
                
                # Update date range controls based on loaded data
                self.update_date_range_controls(df)
                
                self.add_log_message(f"CSVファイルを読み込みました: {len(df)} 行")
                self.status_bar.showMessage(f"データ読み込み完了: {len(df)} スロット")
                
            except Exception as e:
                QMessageBox.warning(self, "ファイル読み込みエラー", str(e))
                self.add_log_message(f"ファイル読み込みエラー: {e}")
                
    @pyqtSlot()
    def download_template(self):
        """Download CSV template"""
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "CSVテンプレートを保存",
            "csv_template.csv",
            "CSV Files (*.csv)"
        )
        
        if save_path:
            try:
                # Create template data
                template_data = {
                    'date': ['2024-01-01', '2024-01-01'],
                    'slot': [1, 2],
                    'JEPX_prediction': [25.0, 30.0],
                    'JEPX_actual': [26.0, 29.5],
                    'EPRX1_prediction': [100.0, 120.0],
                    'EPRX1_actual': [105.0, 115.0],
                    'EPRX3_prediction': [200.0, 220.0],
                    'EPRX3_actual': [210.0, 215.0],
                    'imbalance': [50.0, 55.0]
                }
                
                template_df = pd.DataFrame(template_data)
                template_df.to_csv(save_path, index=False)
                
                QMessageBox.information(
                    self, 
                    "テンプレート保存完了", 
                    f"CSVテンプレートを保存しました:\n{save_path}"
                )
                
            except Exception as e:
                QMessageBox.warning(self, "保存エラー", str(e))
                
    @pyqtSlot()
    def run_optimization(self):
        """Start optimization process"""
        if self.current_data is None:
            QMessageBox.warning(self, "エラー", "CSVファイルを先に読み込んでください")
            return
            
        try:
            # Collect parameters
            params = self.collect_parameters()
            
            # Validate parameters
            params = validate_optimization_params(params)
            
            # Setup UI for optimization
            self.optimize_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Clear previous results
            self.optimization_results = None
            
            # Start optimization
            self.optimization_engine.set_parameters(params, self.current_data)
            self.optimization_engine.start()
            
            self.add_log_message("最適化を開始しました...")
            
        except Exception as e:
            QMessageBox.warning(self, "パラメータエラー", str(e))
            self.reset_ui_after_optimization()
            
    @pyqtSlot()
    def cancel_optimization(self):
        """Cancel ongoing optimization"""
        if self.optimization_engine and self.optimization_engine.isRunning():
            self.optimization_engine.cancel_optimization()
            self.add_log_message("最適化をキャンセルしています...")
            
    def collect_parameters(self) -> Dict[str, Any]:
        """Collect parameters from UI"""
        # Parse area selection to get the correct area name
        area_number, area_name = parse_area_selection(self.area_combo.currentText())
        
        # Map performance mode to debug mode
        mode_text = self.performance_mode_combo.currentText()
        if "simple" in mode_text:
            debug_mode = 'simple'
        elif "basic" in mode_text:
            debug_mode = 'basic'
        elif "full" in mode_text:
            debug_mode = 'full'
        else:
            debug_mode = 'basic'  # Default fallback
            
        # Create parameters dictionary
        params = {
            'target_area_name': area_name,  # Use parsed area name (e.g., "Tokyo" not "3: Tokyo")
            'voltage_type': self.voltage_combo.currentText(),  # Should be "HV", "LV", or "SHV"
            'battery_power_kW': float(self.power_input.value()),
            'battery_capacity_kWh': float(self.capacity_input.value()),
            'battery_loss_rate': float(self.loss_rate_input.value()) / 100,
            'daily_cycle_limit': float(self.daily_cycle_input.value()),
            'yearly_cycle_limit': float(self.yearly_cycle_input.value()),
            'annual_degradation_rate': float(self.degradation_input.value()) / 100,
            'forecast_period': self.forecast_period_input.value(),
            'eprx1_block_size': self.eprx1_block_input.value(),
            'eprx1_block_cooldown': self.eprx1_cooldown_input.value(),
            'max_daily_eprx1_slots': self.max_eprx1_input.value(),
            'debug_mode': debug_mode  # Use selected performance mode
        }
        
        return params
        
    @pyqtSlot(int)
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
        
    @pyqtSlot(str)
    def update_status(self, message):
        """Update status message"""
        self.status_label.setText(message)
        self.status_bar.showMessage(message)
        
    @pyqtSlot(str)
    def add_log_message(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
    @pyqtSlot(dict)
    def on_optimization_completed(self, results):
        """Handle optimization completion"""
        self.optimization_results = results
        self.reset_ui_after_optimization()
        
        # Update UI with results
        self.update_results_display()
        self.update_visualization()
        
        # Show completion message
        summary = results['summary']
        final_profit = summary.get('Final_Profit', 0)
        total_slots = summary.get('Total_Slots', 0)
        
        self.add_log_message(f"最適化完了! 総利益: ¥{final_profit:,.0f} ({total_slots} スロット)")
        
        QMessageBox.information(
            self,
            "最適化完了",
            f"最適化が正常に完了しました。\n\n"
            f"最終利益: ¥{final_profit:,.0f}\n"
            f"処理スロット数: {total_slots}"
        )
        
    @pyqtSlot(str) 
    def on_optimization_failed(self, error_message):
        """Handle optimization failure"""
        self.reset_ui_after_optimization()
        self.add_log_message(f"最適化エラー: {error_message}")
        QMessageBox.critical(self, "最適化エラー", error_message)
        
    def reset_ui_after_optimization(self):
        """Reset UI state after optimization completes/fails"""
        self.optimize_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("待機中...")
        
    def update_results_display(self):
        """Update results display in table and summary tabs"""
        if not self.optimization_results:
            return
            
        results_data = self.optimization_results['results']
        summary_data = self.optimization_results['summary']
        
        # Update table
        self.populate_results_table(results_data)
        
        # Update summary
        self.populate_summary_display(summary_data)
        
    def populate_results_table(self, results_data):
        """Populate the results table"""
        if not results_data:
            return
            
        df = pd.DataFrame(results_data)
        
        self.results_table.setRowCount(len(df))
        self.results_table.setColumnCount(len(df.columns))
        self.results_table.setHorizontalHeaderLabels(df.columns)
        
        for i, row in df.iterrows():
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                self.results_table.setItem(i, j, item)
                
    def populate_summary_display(self, summary_data):
        """Populate the summary display"""
        if not summary_data:
            return
            
        summary_text = "=== 最適化結果サマリー ===\n\n"
        
        for key, value in summary_data.items():
            if isinstance(value, (int, float)):
                if 'Profit' in key or 'Fee' in key or 'Charge' in key:
                    summary_text += f"{key}: ¥{value:,.0f}\n"
                elif 'kWh' in key:
                    summary_text += f"{key}: {value:,.1f} kWh\n"
                else:
                    summary_text += f"{key}: {value:,.2f}\n"
            else:
                summary_text += f"{key}: {value}\n"
                
        self.summary_text.setText(summary_text)
        
    def init_empty_chart(self):
        """Initialize empty chart"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(0.5, 0.5, "最適化結果が表示されます", 
                ha='center', va='center', transform=ax.transAxes,
                fontsize=16, color='gray')
        ax.set_xticks([])
        ax.set_yticks([])
        self.canvas.draw()
        
    def update_visualization(self):
        """Update the visualization chart"""
        if not self.optimization_results:
            self.init_empty_chart()
            return
            
        results_data = self.optimization_results['results']
        if not results_data:
            return
            
        df = pd.DataFrame(results_data)
        df['datetime'] = pd.to_datetime(df['date']) + pd.to_timedelta((df['slot'] - 1) * 30, unit='minutes')
        
        # Apply date range filtering
        filtered_df = self.get_filtered_data(df)
        
        if filtered_df.empty:
            self.add_log_message(f"グラフ更新スキップ: フィルター後のデータが空 (モード: {self.date_range_mode})")
            self.init_empty_chart()
            return
        
        self.add_log_message(f"グラフ更新開始: {len(filtered_df)} 行のデータを使用 (モード: {self.date_range_mode})")
        
        # Clear figure
        self.figure.clear()
        
        # Create subplots
        ax1 = self.figure.add_subplot(211)
        ax2 = self.figure.add_subplot(212)
        
        # Debug: Check if battery_level_kWh column exists and has data
        if 'battery_level_kWh' not in filtered_df.columns:
            self.add_log_message("警告: battery_level_kWh列が見つかりません")
            print("Debug: Missing battery_level_kWh column")
            print(f"Available columns: {list(filtered_df.columns)}")
        elif filtered_df['battery_level_kWh'].isna().all():
            self.add_log_message("警告: battery_level_kWh列にデータがありません")
            print("Debug: battery_level_kWh column is all NaN")
        elif (filtered_df['battery_level_kWh'] == 0).all():
            self.add_log_message("警告: battery_level_kWh列が全て0です")
            print("Debug: battery_level_kWh column is all zeros")
        else:
            min_val = filtered_df['battery_level_kWh'].min()
            max_val = filtered_df['battery_level_kWh'].max()
            self.add_log_message(f"バッテリー残量範囲: {min_val:.1f} - {max_val:.1f} kWh")
            print(f"Debug: battery_level_kWh range: {min_val:.1f} - {max_val:.1f}")

        # Plot battery level
        try:
            battery_data = filtered_df['battery_level_kWh'] if 'battery_level_kWh' in filtered_df.columns else [0] * len(filtered_df)
            ax1.bar(filtered_df['datetime'], battery_data, 
                    color='lightblue', alpha=0.7, width=0.02)
            ax1.set_title(f'バッテリー残量 (kWh) - {self.get_date_range_title()}')
            ax1.set_ylabel('kWh')
            ax1.grid(True, alpha=0.3)
        except Exception as e:
            self.add_log_message(f"バッテリーグラフ描画エラー: {str(e)}")
            print(f"Debug: Battery plot error: {str(e)}")
        
        # Plot JEPX price
        ax2.plot(filtered_df['datetime'], filtered_df['JEPX_actual'], 
                color='red', linewidth=2, label='JEPX実績価格')
        ax2.set_title(f'JEPX価格 (円/kWh) - {self.get_date_range_title()}')
        ax2.set_ylabel('円/kWh')
        ax2.set_xlabel('時刻')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # Format x-axis based on data range
        date_range = (filtered_df['datetime'].max() - filtered_df['datetime'].min()).days
        if date_range <= 1:
            # For 1 day or less, show hourly ticks
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        elif date_range <= 7:
            # For up to 7 days, show daily ticks
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        else:
            # For longer periods, show weekly ticks
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        
        # Rotate labels for better readability
        for ax in [ax1, ax2]:
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
        self.figure.tight_layout()
        self.canvas.draw()
        
    def get_date_range_title(self):
        """Get title describing current date range"""
        if self.date_range_mode == "all":
            return "全期間"
        elif self.date_range_mode == "last_7":
            return "最近7日間"
        elif self.date_range_mode == "last_30":
            return "最近30日間"
        elif self.date_range_mode == "range":
            start_date = self.start_date_edit.date().toString("yyyy/MM/dd")
            end_date = self.end_date_edit.date().toString("yyyy/MM/dd")
            return f"{start_date} - {end_date}"
        return ""
        
    @pyqtSlot()
    def save_results(self):
        """Save results to file"""
        if not self.optimization_results:
            QMessageBox.warning(self, "エラー", "保存する結果がありません")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "結果を保存",
            "optimization_results.csv",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                results_df = pd.DataFrame(self.optimization_results['results'])
                results_df.to_csv(file_path, index=False)
                QMessageBox.information(self, "保存完了", f"結果を保存しました:\n{file_path}")
                self.add_log_message(f"結果を保存: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "保存エラー", str(e))
                
    @pyqtSlot()
    def export_results(self):
        """Export results table"""
        self.save_results()  # Same as save results for now
        
    @pyqtSlot()
    def reset_parameters(self):
        """Reset parameters to defaults"""
        reply = QMessageBox.question(
            self, "パラメータリセット", 
            "パラメータをデフォルト値にリセットしますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Reset to defaults
            self.area_combo.setCurrentIndex(2)  # Tokyo
            self.voltage_combo.setCurrentIndex(1)  # HV
            self.power_input.setValue(1000)
            self.capacity_input.setValue(4000)
            self.loss_rate_input.setValue(5.0)
            self.daily_cycle_input.setValue(1)
            self.forecast_period_input.setValue(48)
            self.eprx1_block_input.setValue(3)
            self.eprx1_cooldown_input.setValue(2)
            self.max_eprx1_input.setValue(6)
            self.yearly_cycle_input.setValue(365)
            self.degradation_input.setValue(3.0)
            
            self.add_log_message("パラメータをリセットしました")
            
    @pyqtSlot()
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Battery Optimizer",
            "Battery Optimizer 2.0\n\n"
            "PyQt6-based desktop application for battery storage optimization\n"
            "in Japanese electricity markets.\n\n"
            "© 2024 Factlabel\n"
            "Built with PyQt6, PuLP, and matplotlib"
        )
        
    def load_settings(self):
        """Load application settings"""
        # Restore window geometry
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        # Restore parameter values
        self.power_input.setValue(
            self.settings.value("battery_power_kW", 1000, type=int)
        )
        self.capacity_input.setValue(
            self.settings.value("battery_capacity_kWh", 4000, type=int)
        )
        
    def save_settings(self):
        """Save application settings"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("battery_power_kW", self.power_input.value())
        self.settings.setValue("battery_capacity_kWh", self.capacity_input.value())
        
    def closeEvent(self, event):
        """Handle application close event"""
        # Cancel any running optimization
        if self.optimization_engine and self.optimization_engine.isRunning():
            reply = QMessageBox.question(
                self, "終了確認",
                "最適化が実行中です。終了しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.optimization_engine.cancel_optimization()
                self.optimization_engine.wait()  # Wait for thread to finish
            else:
                event.ignore()
                return
                
        # Save settings
        self.save_settings()
        event.accept() 