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
import json
import asyncio
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QFileDialog, QTextEdit,
    QProgressBar, QSplitter, QFrame, QGroupBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QTabWidget, QScrollArea,
    QStatusBar, QDateEdit, QButtonGroup, QRadioButton, QPlainTextEdit,
    QCheckBox
)
from PyQt6.QtCore import Qt, QSettings, QTimer, pyqtSlot, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QAction, QIcon

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

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

# Import OpenAI for chatbot
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class ChatBotWorker(QThread):
    """Worker thread for OpenAI API calls"""
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, api_key: str, messages: list, optimization_data: dict = None):
        super().__init__()
        self.api_key = api_key
        self.messages = messages
        self.optimization_data = optimization_data
        
    def run(self):
        try:
            client = openai.OpenAI(api_key=self.api_key)
            
            # Add system message with optimization data context
            system_message = {
                "role": "system",
                "content": f"""あなたは Battery Optimizer の専門アシスタントです。
                
最適化結果データがある場合、以下の情報を参照して回答してください：

{json.dumps(self.optimization_data, indent=2, ensure_ascii=False) if self.optimization_data else '最適化結果データはまだありません。'}

ユーザーの質問に対して、最適化結果を具体的に分析して、日本語で分かりやすく回答してください。
数値は適切に丸めて表示し、グラフの傾向や収益性について詳細に説明してください。"""
            }
            
            messages_with_context = [system_message] + self.messages
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages_with_context,
                max_tokens=1500,
                temperature=0.7
            )
            
            self.response_ready.emit(response.choices[0].message.content)
            
        except Exception as e:
            self.error_occurred.emit(f"エラー: {str(e)}")


class BatteryOptimizerMainWindow(QMainWindow):
    """Main window for the Battery Optimizer application"""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings()
        self.optimization_engine = None
        self.optimization_results = None
        self.current_data = None
        self.chat_messages = []
        self.chatbot_worker = None
        
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
        
        # Settings menu
        settings_menu = menubar.addMenu('設定')
        
        api_action = QAction('OpenAI API設定...', self)
        api_action.triggered.connect(self.show_api_settings)
        settings_menu.addAction(api_action)
        
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
        
        # Revenue Details tab (NEW!)
        revenue_tab = self.create_revenue_details_tab()
        self.tab_widget.addTab(revenue_tab, "収益詳細")
        
        # Results table tab
        table_tab = self.create_table_tab()
        self.tab_widget.addTab(table_tab, "詳細データ")
        
        # Summary tab
        summary_tab = self.create_summary_tab()
        self.tab_widget.addTab(summary_tab, "サマリー")
        
        # ChatBot tab (NEW!)
        if OPENAI_AVAILABLE:
            chat_tab = self.create_chatbot_tab()
            self.tab_widget.addTab(chat_tab, "AI分析チャット")
        
        layout.addWidget(self.tab_widget)
        
        # Initialize with empty charts
        self.init_empty_chart()
        
        return panel
        
    def create_revenue_details_tab(self):
        """Create revenue details visualization tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Create matplotlib figure for revenue details
        self.revenue_figure = Figure(figsize=(12, 8))
        self.revenue_canvas = FigureCanvas(self.revenue_figure)
        layout.addWidget(self.revenue_canvas)
        
        # Initialize empty revenue chart
        self.init_empty_revenue_chart()
        
        return tab
        
    def create_chatbot_tab(self):
        """Create AI chatbot tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # API Key status
        api_status_layout = QHBoxLayout()
        self.api_status_label = QLabel("API状態: ")
        api_status_layout.addWidget(self.api_status_label)
        
        api_settings_btn = QPushButton("API設定")
        api_settings_btn.clicked.connect(self.show_api_settings)
        api_status_layout.addWidget(api_settings_btn)
        api_status_layout.addStretch()
        
        layout.addLayout(api_status_layout)
        
        # Chat display area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("システムフォント", 12))
        layout.addWidget(self.chat_display)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("最適化結果について質問してください... (例: 最も収益の高い時間帯は？)")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        input_layout.addWidget(self.chat_input)
        
        self.send_button = QPushButton("送信")
        self.send_button.clicked.connect(self.send_chat_message)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        
        # Clear chat button
        clear_btn = QPushButton("チャット履歴をクリア")
        clear_btn.clicked.connect(self.clear_chat)
        layout.addWidget(clear_btn)
        
        # Update API status
        self.update_api_status()
        
        return tab
        
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
            'debug_mode': 'full',
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
        """Update all result displays"""
        if not self.optimization_results:
            return
            
        try:
            # Update existing displays
            self.populate_results_table(self.optimization_results['results'])
            self.populate_summary_display(self.optimization_results['summary'])
            self.update_visualization()
            self.update_revenue_details()  # NEW!
            
            # Show first tab (graphs) after completion
            self.tab_widget.setCurrentIndex(0)
            
        except Exception as e:
            self.add_log_message(f"結果表示エラー: {str(e)}")
            
    def update_revenue_details(self):
        """Update revenue details visualization"""
        if not self.optimization_results:
            self.init_empty_revenue_chart()
            return
            
        try:
            results_data = self.optimization_results['results']
            if not results_data:
                self.init_empty_revenue_chart()
                return
                
            # Get filtered data
            df = pd.DataFrame(results_data)
            df = self.get_filtered_data(df)
            
            if df.empty:
                self.init_empty_revenue_chart()
                return
                
            # Prepare data for visualization
            df['datetime'] = pd.to_datetime(df['date']) + pd.to_timedelta((df['slot'] - 1) * 0.5, unit='h')
            
            # Clear previous plots
            self.revenue_figure.clear()
            
            # Create subplots
            gs = self.revenue_figure.add_gridspec(3, 2, hspace=0.4, wspace=0.3)
            
            # 1. Hourly Revenue Breakdown
            ax1 = self.revenue_figure.add_subplot(gs[0, :])
            
            # Calculate total hourly PnL
            df['total_pnl'] = df['JEPX_PnL'] + df['EPRX1_PnL'] + df['EPRX3_PnL']
            hourly_pnl = df.groupby(df['datetime'].dt.hour)['total_pnl'].sum()
            
            bars = ax1.bar(hourly_pnl.index, hourly_pnl.values, 
                          color=['green' if x > 0 else 'red' for x in hourly_pnl.values],
                          alpha=0.7, edgecolor='black', linewidth=0.5)
            ax1.set_title('時間別収益分布', fontsize=14, fontweight='bold')
            ax1.set_xlabel('時間')
            ax1.set_ylabel('収益 (円)')
            ax1.grid(True, alpha=0.3)
            ax1.set_xticks(range(0, 24, 2))
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                if abs(height) > max(abs(hourly_pnl.values)) * 0.02:  # Only label significant bars
                    ax1.text(bar.get_x() + bar.get_width()/2., height/2,
                            f'{int(height):,}', ha='center', va='center', fontsize=8)
            
            # 2. Market Contribution Analysis
            ax2 = self.revenue_figure.add_subplot(gs[1, 0])
            
            market_totals = {
                'JEPX': df['JEPX_PnL'].sum(),
                'EPRX1': df['EPRX1_PnL'].sum(), 
                'EPRX3': df['EPRX3_PnL'].sum()
            }
            
            # Filter out zero contributions
            market_totals = {k: v for k, v in market_totals.items() if abs(v) > 1}
            
            if market_totals:
                colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
                wedges, texts, autotexts = ax2.pie(
                    market_totals.values(), 
                    labels=market_totals.keys(),
                    autopct=lambda pct: f'{pct:.1f}%\n({int(pct/100 * sum(market_totals.values())):,}円)',
                    colors=colors,
                    startangle=90
                )
                ax2.set_title('市場別収益貢献', fontsize=12, fontweight='bold')
                
                # Improve text readability
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(9)
            else:
                ax2.text(0.5, 0.5, 'データなし', ha='center', va='center', transform=ax2.transAxes)
                ax2.set_title('市場別収益貢献', fontsize=12, fontweight='bold')
            
            # 3. Action Distribution
            ax3 = self.revenue_figure.add_subplot(gs[1, 1])
            
            action_counts = df['action'].value_counts()
            colors_action = {'charge': '#FF9999', 'discharge': '#99FF99', 'eprx1': '#9999FF', 
                           'eprx3': '#FFFF99', 'idle': '#CCCCCC'}
            
            wedges, texts, autotexts = ax3.pie(
                action_counts.values,
                labels=action_counts.index,
                autopct='%1.1f%%',
                colors=[colors_action.get(action, '#CCCCCC') for action in action_counts.index],
                startangle=90
            )
            ax3.set_title('アクション分布', fontsize=12, fontweight='bold')
            
            # 4. Daily Revenue Trend
            ax4 = self.revenue_figure.add_subplot(gs[2, :])
            
            daily_pnl = df.groupby('date')['total_pnl'].sum()
            daily_pnl.index = pd.to_datetime(daily_pnl.index)
            
            # Line plot with markers
            ax4.plot(daily_pnl.index, daily_pnl.values, marker='o', linewidth=2, 
                    markersize=6, color='#007AFF', markerfacecolor='white', markeredgecolor='#007AFF')
            
            # Fill positive/negative areas
            ax4.fill_between(daily_pnl.index, daily_pnl.values, 0, 
                           where=(daily_pnl.values > 0), color='green', alpha=0.3, label='利益')
            ax4.fill_between(daily_pnl.index, daily_pnl.values, 0,
                           where=(daily_pnl.values <= 0), color='red', alpha=0.3, label='損失')
            
            ax4.set_title('日別収益推移', fontsize=12, fontweight='bold')
            ax4.set_xlabel('日付')
            ax4.set_ylabel('収益 (円)')
            ax4.grid(True, alpha=0.3)
            ax4.legend()
            
            # Format x-axis dates
            if len(daily_pnl) > 7:
                ax4.xaxis.set_major_locator(mdates.WeekdayLocator())
                ax4.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            else:
                ax4.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            
            # Rotate labels for better readability
            plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            # Add overall statistics text
            total_profit = df['total_pnl'].sum()
            avg_daily_profit = daily_pnl.mean()
            best_day = daily_pnl.idxmax()
            best_day_profit = daily_pnl.max()
            
            stats_text = f"""収益サマリー ({self.get_date_range_title()}):
• 総収益: {total_profit:,.0f}円
• 平均日収: {avg_daily_profit:,.0f}円
• 最高収益日: {best_day.strftime('%m/%d')} ({best_day_profit:,.0f}円)"""
            
            self.revenue_figure.text(0.02, 0.98, stats_text, transform=self.revenue_figure.transFigure,
                                   fontsize=10, verticalalignment='top', fontweight='bold',
                                   bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8))
            
            # Overall title
            period_title = f"収益詳細分析 - {self.get_date_range_title()}"
            self.revenue_figure.suptitle(period_title, fontsize=16, fontweight='bold', y=0.95)
            
            self.revenue_canvas.draw()
            
        except Exception as e:
            self.add_log_message(f"収益詳細グラフ更新エラー: {str(e)}")
            self.init_empty_revenue_chart()
        
    def init_empty_revenue_chart(self):
        """Initialize empty revenue details chart"""
        self.revenue_figure.clear()
        ax = self.revenue_figure.add_subplot(111)
        ax.text(0.5, 0.5, '最適化結果がありません\n最適化を実行すると収益詳細グラフが表示されます', 
                horizontalalignment='center', verticalalignment='center', 
                transform=ax.transAxes, fontsize=14, color='gray')
        ax.set_title('収益詳細分析')
        self.revenue_canvas.draw()
        
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
        
    def show_api_settings(self):
        """Show OpenAI API settings dialog"""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("OpenAI API設定")
        dialog.setIcon(QMessageBox.Icon.Information)
        
        current_key = self.settings.value("openai_api_key", "")
        masked_key = "sk-..." + current_key[-4:] if current_key and len(current_key) > 7 else "未設定"
        
        dialog.setText(f"現在のAPIキー: {masked_key}")
        dialog.setInformativeText("新しいOpenAI APIキーを入力してください:")
        
        # Custom dialog with input field
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QDialogButtonBox
        
        api_dialog = QDialog(self)
        api_dialog.setWindowTitle("OpenAI API設定")
        api_dialog.setModal(True)
        api_dialog.resize(400, 150)
        
        layout = QVBoxLayout(api_dialog)
        
        layout.addWidget(QLabel("OpenAI APIキーを入力してください:"))
        
        api_input = QLineEdit()
        api_input.setPlaceholderText("sk-...")
        api_input.setText(current_key)
        api_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(api_input)
        
        show_key_checkbox = QCheckBox("APIキーを表示")
        show_key_checkbox.toggled.connect(
            lambda checked: api_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(show_key_checkbox)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(api_dialog.accept)
        buttons.rejected.connect(api_dialog.reject)
        layout.addWidget(buttons)
        
        if api_dialog.exec() == QDialog.DialogCode.Accepted:
            api_key = api_input.text().strip()
            if api_key:
                self.settings.setValue("openai_api_key", api_key)
                self.update_api_status()
                QMessageBox.information(self, "設定完了", "OpenAI APIキーが保存されました。")
            else:
                self.settings.remove("openai_api_key")
                self.update_api_status()
                QMessageBox.information(self, "設定削除", "OpenAI APIキーが削除されました。")
                
    def update_api_status(self):
        """Update API status display"""
        if not OPENAI_AVAILABLE:
            self.api_status_label.setText("API状態: openaiライブラリが未インストール")
            self.api_status_label.setStyleSheet("color: red;")
            return
            
        api_key = self.settings.value("openai_api_key", "")
        if api_key:
            self.api_status_label.setText("API状態: 設定済み ✓")
            self.api_status_label.setStyleSheet("color: green;")
        else:
            self.api_status_label.setText("API状態: 未設定")
            self.api_status_label.setStyleSheet("color: orange;")
            
    def send_chat_message(self):
        """Send message to chatbot"""
        if not OPENAI_AVAILABLE:
            QMessageBox.warning(self, "エラー", "openaiライブラリがインストールされていません。\npip install openai を実行してください。")
            return
            
        api_key = self.settings.value("openai_api_key", "")
        if not api_key:
            QMessageBox.warning(self, "API未設定", "OpenAI APIキーが設定されていません。\n設定メニューから設定してください。")
            return
            
        message = self.chat_input.text().strip()
        if not message:
            return
            
        # Add user message to chat
        self.chat_messages.append({"role": "user", "content": message})
        self.display_chat_message("ユーザー", message, is_user=True)
        self.chat_input.clear()
        
        # Disable input while processing
        self.chat_input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.send_button.setText("送信中...")
        
        # Prepare optimization data for context
        optimization_context = None
        if self.optimization_results:
            # Create a summary of optimization results for the AI
            optimization_context = {
                "summary": self.optimization_results.get("summary", {}),
                "total_rows": len(self.optimization_results.get("results", [])),
                "date_range": self.get_date_range_title(),
                "recent_results": self.optimization_results.get("results", [])[-10:] if self.optimization_results.get("results") else []
            }
        
        # Start chatbot worker
        self.chatbot_worker = ChatBotWorker(
            api_key=api_key,
            messages=self.chat_messages.copy(),
            optimization_data=optimization_context
        )
        self.chatbot_worker.response_ready.connect(self.on_chat_response)
        self.chatbot_worker.error_occurred.connect(self.on_chat_error)
        self.chatbot_worker.start()
        
    def on_chat_response(self, response):
        """Handle chatbot response"""
        self.chat_messages.append({"role": "assistant", "content": response})
        self.display_chat_message("AI分析", response, is_user=False)
        
        # Re-enable input
        self.chat_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.send_button.setText("送信")
        
    def on_chat_error(self, error):
        """Handle chatbot error"""
        self.display_chat_message("エラー", error, is_user=False, is_error=True)
        
        # Re-enable input
        self.chat_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.send_button.setText("送信")
        
    def display_chat_message(self, sender, message, is_user=False, is_error=False):
        """Display chat message in the chat area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if is_error:
            color = "red"
            prefix = "❌"
        elif is_user:
            color = "#007AFF"
            prefix = "👤"
        else:
            color = "#34C759"
            prefix = "🤖"
            
        formatted_message = f"""
        <div style="margin: 10px 0; padding: 10px; border-left: 3px solid {color}; background-color: {'#f8f9fa' if not is_user else '#e3f2fd'};">
            <strong style="color: {color};">{prefix} {sender}</strong> 
            <span style="color: gray; font-size: 12px;">[{timestamp}]</span><br/>
            <div style="margin-top: 5px; white-space: pre-wrap;">{message}</div>
        </div>
        """
        
        self.chat_display.append(formatted_message)
        
        # Scroll to bottom
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def clear_chat(self):
        """Clear chat history"""
        self.chat_messages.clear()
        self.chat_display.clear()
        self.chat_display.append("<p style='color: gray; text-align: center;'>チャット履歴がクリアされました。</p>")
        
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