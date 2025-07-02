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
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QFileDialog, QTextEdit,
    QProgressBar, QSplitter, QFrame, QGroupBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QTabWidget, QScrollArea,
    QStatusBar, QDateEdit, QButtonGroup, QRadioButton, QPlainTextEdit,
    QCheckBox, QDialog, QFormLayout, QDialogButtonBox, QCalendarWidget
)
from PyQt6.QtCore import Qt, QSettings, QTimer, pyqtSlot, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QAction, QIcon

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.qt_compat import QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
import socket
import openai

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
from core.optimization_engine_v2 import OptimizationEngineV2
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


def convert_numpy_types(obj):
    """Convert numpy types to JSON serializable Python types"""
    try:
        # Handle None first
        if obj is None:
            return None
            
        # Handle numpy types
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            if np.isnan(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
            
        # Handle pandas types
        try:
            if pd.isna(obj):  # This might cause the ambiguous error
                return None
        except (ValueError, TypeError):
            # If pd.isna() fails on this object type, continue
            pass
            
        # Handle pandas Timestamp and NaT
        if isinstance(obj, pd.Timestamp):
            return str(obj) if not pd.isna(obj) else None
        elif hasattr(obj, '__class__') and 'NaTType' in str(obj.__class__):
            return None
            
        # Handle collections
        elif isinstance(obj, dict):
            return {key: convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_numpy_types(item) for item in obj]
        elif isinstance(obj, set):
            return [convert_numpy_types(item) for item in obj]
            
        # Handle basic Python types and unknown types
        else:
            # Try to convert to basic types if possible
            if hasattr(obj, 'item'):  # numpy scalar
                return convert_numpy_types(obj.item())
            return obj
            
    except Exception as e:
        # If conversion fails, return string representation
        return str(obj)


class CalendarDialog(QDialog):
    """Calendar widget dialog for date selection"""
    
    def __init__(self, parent=None, title="日付選択", current_date=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(350, 300)
        
        # Store selected date
        self.selected_date = current_date or QDate.currentDate()
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize calendar dialog UI"""
        layout = QVBoxLayout(self)
        
        # Calendar widget
        self.calendar = QCalendarWidget()
        self.calendar.setSelectedDate(self.selected_date)
        self.calendar.clicked.connect(self.on_date_selected)
        layout.addWidget(self.calendar)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Today button
        today_button = QPushButton("今日")
        today_button.clicked.connect(self.select_today)
        button_layout.addWidget(today_button)
        
        button_layout.addStretch()
        
        # OK and Cancel buttons
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("キャンセル")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Set focus to calendar
        self.calendar.setFocus()
        
    def on_date_selected(self, date):
        """Handle date selection from calendar"""
        self.selected_date = date
        
    def select_today(self):
        """Select today's date"""
        today = QDate.currentDate()
        self.calendar.setSelectedDate(today)
        self.selected_date = today
        
    def get_selected_date(self):
        """Get the selected date"""
        return self.selected_date


class EmailManager:
    """Handle email notifications for error reporting"""
    
    def __init__(self, settings):
        self.settings = settings
        
    def send_error_report(self, error_message, user_context="", log_data=""):
        """Send error report email to administrator"""
        try:
            # Get email settings
            smtp_server = self.settings.value("email/smtp_server", "smtp.gmail.com")
            smtp_port = int(self.settings.value("email/smtp_port", 587))
            sender_email = self.settings.value("email/sender_email", "")
            sender_password = self.settings.value("email/sender_password", "")
            admin_email = self.settings.value("email/admin_email", "")
            
            if not all([sender_email, sender_password, admin_email]):
                return False, "メール設定が不完全です"
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = admin_email
            msg['Subject'] = "Battery Optimizer - エラー報告"
            
            body = f"""
Battery Optimizer でエラーが発生しました。

【エラー内容】
{error_message}

【ユーザーの状況】
{user_context}

【ログデータ】
{log_data}

【発生時刻】
{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

このメールは自動送信されました。
"""
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(sender_email, sender_password)
                server.send_message(msg)
                
            return True, "エラー報告を送信しました"
            
        except Exception as e:
            return False, f"メール送信エラー: {str(e)}"
    
    def test_email_settings(self):
        """Test email configuration"""
        try:
            smtp_server = self.settings.value("email/smtp_server", "smtp.gmail.com")
            smtp_port = int(self.settings.value("email/smtp_port", 587))
            sender_email = self.settings.value("email/sender_email", "")
            sender_password = self.settings.value("email/sender_password", "")
            
            if not all([sender_email, sender_password]):
                return False, "メール設定が不完全です"
            
            # Test connection
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(sender_email, sender_password)
                
            return True, "メール設定テスト成功"
            
        except Exception as e:
            return False, f"メール設定テストエラー: {str(e)}"


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
            
            # Load knowledge base
            knowledge_base = self.load_knowledge_base()
            
            # Convert optimization data to JSON serializable format
            serializable_data = convert_numpy_types(self.optimization_data) if self.optimization_data else None
            
            # Create comprehensive and readable data summary for AI
            optimization_info = ""
            if serializable_data:
                total_rows = serializable_data.get('total_rows', 0)
                date_range_full = serializable_data.get('date_range_full', '不明')
                current_filter = serializable_data.get('current_display_filter', '不明')
                stats = serializable_data.get('data_statistics', {})
                summary = serializable_data.get('summary', {})
                
                # Format summary data in a more readable way
                summary_text = "\n【基本収益情報】\n"
                for key, value in summary.items():
                    if isinstance(value, (int, float)):
                        if 'Profit' in key or 'Fee' in key:
                            summary_text += f"• {key}: ¥{value:,.0f}\n"
                        elif 'kWh' in key:
                            summary_text += f"• {key}: {value:,.1f} kWh\n"
                        else:
                            summary_text += f"• {key}: {value:,.2f}\n"
                    else:
                        summary_text += f"• {key}: {value}\n"
                
                # Format revenue analysis
                revenue_analysis = stats.get('revenue_analysis', {})
                revenue_text = "\n【詳細収益分析】\n"
                if revenue_analysis:
                    revenue_text += f"• 総収益: ¥{revenue_analysis.get('total_revenue', 0):,.0f}\n"
                    revenue_text += f"• 平均スロット収益: ¥{revenue_analysis.get('average_slot_revenue', 0):,.0f}\n"
                    revenue_text += f"• 最大スロット収益: ¥{revenue_analysis.get('max_slot_revenue', 0):,.0f}\n"
                    revenue_text += f"• 最小スロット収益: ¥{revenue_analysis.get('min_slot_revenue', 0):,.0f}\n"
                    revenue_text += f"• 利益スロット数: {revenue_analysis.get('profitable_slots', 0):,}\n"
                    revenue_text += f"• 損失スロット数: {revenue_analysis.get('loss_slots', 0):,}\n"
                    revenue_text += f"• JEPX収益: ¥{revenue_analysis.get('jepx_total', 0):,.0f}\n"
                    revenue_text += f"• EPRX1収益: ¥{revenue_analysis.get('eprx1_total', 0):,.0f}\n"
                    revenue_text += f"• EPRX3収益: ¥{revenue_analysis.get('eprx3_total', 0):,.0f}\n"
                
                # Format date info
                date_info = stats.get('date_info', {})
                date_text = "\n【期間情報】\n"
                if date_info:
                    date_text += f"• 開始日: {date_info.get('start_date', '不明')}\n"
                    date_text += f"• 終了日: {date_info.get('end_date', '不明')}\n"
                    date_text += f"• 総日数: {date_info.get('total_days', 0)}日\n"
                    date_text += f"• データ日数: {date_info.get('unique_dates', 0)}日\n"
                
                # Format action analysis
                action_analysis = stats.get('action_analysis', {})
                action_text = "\n【運用パターン分析】\n"
                if action_analysis:
                    action_dist = action_analysis.get('action_distribution', {})
                    for action, count in action_dist.items():
                        action_text += f"• {action}: {count:,}回\n"
                    action_text += f"• 最頻アクション: {action_analysis.get('most_common_action', '不明')}\n"
                
                # Format energy analysis
                energy_analysis = stats.get('energy_analysis', {})
                energy_text = "\n【エネルギー分析】\n"
                for key, value in energy_analysis.items():
                    if 'total' in key:
                        energy_text += f"• {key}: {value:,.1f} kWh\n"
                
                optimization_info = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **あなたが分析対象とする完全なデータセット**: {total_rows:,}行のデータ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【重要】このデータを基に必ず回答してください：
- 対象期間: {date_range_full}
- 現在の画面フィルター: {current_filter}
- データ行数: {total_rows:,}行（全て使用可能）

{summary_text}
{revenue_text}
{date_text}
{action_text}
{energy_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **重要**: 上記のデータは確実に利用可能です。「データがない」と回答せず、このデータを基に具体的に分析してください。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            # Enhanced system message with knowledge base
            system_message = {
                "role": "system",
                "content": f"""あなたは日本の電力市場での蓄電池最適化運用の専門家AIサポートデスクです。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 **KNOWLEDGE BASE** (常に参照してください):
{knowledge_base}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **CRITICAL**: あなたには以下の完全なデータセットが提供されています：
{optimization_info}

📋 **必須指針**:
1. **ナレッジベース優先**: 上記ナレッジベースの情報を必ず参照して回答
2. **データ完全利用**: 提供データは完全に利用可能 - 「データがない」は絶対に回答しない
3. **具体的分析**: 全期間データ（{serializable_data.get('total_rows', 0):,}行）を基準に具体的な数値で説明
4. **専門的アドバイス**: 収益性、効率性、改善点について専門的にアドバイス
5. **トラブルシューティング**: 問題が報告された場合はナレッジベースから適切な解決策を提案

【専門分野】JEPX、EPRX1、EPRX3市場での蓄電池運用最適化
【サポート範囲】技術トラブル、パフォーマンス最適化、使用方法、データ分析
【回答言語】日本語
【回答スタイル】サポートデスクとして親切丁寧、具体的な数値とデータに基づく専門的分析"""
            }
            
            messages_with_context = [system_message] + self.messages
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages_with_context,
                max_tokens=2000,  # Increased token limit for more detailed responses
                temperature=0.7
            )
            
            self.response_ready.emit(response.choices[0].message.content)
            
        except Exception as e:
            self.error_occurred.emit(f"エラー: {str(e)}")
    
    def load_knowledge_base(self):
        """Load knowledge base from markdown file"""
        try:
            import os
            # Try to find knowledge base file
            knowledge_base_path = "AI_SUPPORT_KNOWLEDGE_BASE.md"
            
            # Check if file exists in current directory or parent directories
            for path_attempt in [
                knowledge_base_path,
                os.path.join(os.getcwd(), knowledge_base_path),
                os.path.join(os.path.dirname(__file__), "..", knowledge_base_path),
                os.path.join(os.path.dirname(__file__), "..", "..", knowledge_base_path)
            ]:
                if os.path.exists(path_attempt):
                    with open(path_attempt, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Limit content size for API efficiency
                        if len(content) > 8000:  # Truncate if too long
                            content = content[:8000] + "\n\n[... ナレッジベースが長いため省略 ...]"
                        return content
            
            # If no knowledge base found, return basic information
            return """
# Battery Optimizer サポートガイド (簡易版)

## よくある問題
1. CBCソルバーエラー: `python setup.py` で自動修復
2. 最適化が遅い: 高速モード(V1)を選択
3. データ読み込みエラー: CSVフォーマットを確認

## パフォーマンスモード
- V1 (高速): EPRX1制約なし、最高速度
- V2-basic (標準): 簡易EPRX1制約
- V2-full (完全): 全制約、Streamlit準拠

## データ要件
必須列: date, slot, JEPX_prediction, JEPX_actual, EPRX1_prediction, EPRX1_actual, EPRX3_prediction, EPRX3_actual, imbalance
"""
        except Exception as e:
            return f"ナレッジベース読み込みエラー: {str(e)}"


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
        self.email_manager = EmailManager(self.settings)
        
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
        main_layout = QVBoxLayout(central_widget)
        
        # Top bar with settings button
        top_bar = QHBoxLayout()
        
        # Title area
        title_layout = QHBoxLayout()
        app_title = QLabel("Battery Optimizer 2.0")
        app_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        title_layout.addWidget(app_title)
        title_layout.addStretch()
        top_bar.addLayout(title_layout)
        
        # Settings button in top right
        self.top_settings_button = QPushButton("⚙️")
        self.top_settings_button.clicked.connect(self.show_settings_dialog)
        self.top_settings_button.setFixedSize(40, 40)
        self.top_settings_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 20px;
                font-size: 16px;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        self.top_settings_button.setToolTip("設定 (API、メール、一般設定)")
        top_bar.addWidget(self.top_settings_button)
        
        main_layout.addLayout(top_bar)
        
        # Content area with splitter
        content_layout = QHBoxLayout()
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        content_layout.addWidget(splitter)
        
        # Left panel: Parameters and controls
        left_panel = self.create_control_panel()
        left_panel.setMaximumWidth(500)
        left_panel.setMinimumWidth(400)
        
        # Right panel: Results and visualization
        right_panel = self.create_results_panel()
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 1200])
        
        main_layout.addLayout(content_layout)
        
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
        
        # Add settings icon (gear icon)
        settings_action = QAction('⚙️ 全般設定...', self)
        settings_action.triggered.connect(self.show_settings_dialog)
        settings_action.setShortcut('Ctrl+,')
        settings_menu.addAction(settings_action)
        
        settings_menu.addSeparator()
        
        # Quick API setting (legacy support)
        api_action = QAction('OpenAI API設定 (クイック)...', self)
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
        
        # Initial battery level (NEW!)
        layout.addWidget(QLabel("初期蓄電量 (kWh):"), 4, 0)
        self.initial_battery_input = QSpinBox()
        self.initial_battery_input.setRange(0, 1000000)
        self.initial_battery_input.setValue(2000)  # Default to 50% of default capacity
        self.initial_battery_input.setSuffix(" kWh")
        self.initial_battery_input.setToolTip("V2エンジン使用時：最初の日の開始時のバッテリー蓄電量（kWh）\nV1エンジンでは無視され、容量の50%から開始します")
        layout.addWidget(self.initial_battery_input, 4, 1)
        
        # Connect capacity change to update initial battery max value
        self.capacity_input.valueChanged.connect(self.update_initial_battery_max)
        
        # Set initial maximum for initial battery input
        self.update_initial_battery_max()
        
        # Battery loss rate
        layout.addWidget(QLabel("バッテリー損失率 (%):"), 5, 0)
        self.loss_rate_input = QDoubleSpinBox()
        self.loss_rate_input.setRange(0.0, 50.0)
        self.loss_rate_input.setValue(5.0)
        self.loss_rate_input.setSuffix(" %")
        self.loss_rate_input.setDecimals(2)
        layout.addWidget(self.loss_rate_input, 5, 1)
        
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
        
        # EPRX3 activation rate
        layout.addWidget(QLabel("EPRX3発動率:"), 7, 0)
        self.eprx3_activation_input = QDoubleSpinBox()
        self.eprx3_activation_input.setRange(0.0, 100.0)
        self.eprx3_activation_input.setValue(100.0)
        self.eprx3_activation_input.setSuffix(" %")
        self.eprx3_activation_input.setDecimals(1)
        self.eprx3_activation_input.setToolTip("EPRX3指令が選択された時の実際の発動確率")
        layout.addWidget(self.eprx3_activation_input, 7, 1)
        
        # V1 price ratio
        layout.addWidget(QLabel("V1価格比率:"), 8, 0)
        self.v1_price_ratio_input = QDoubleSpinBox()
        self.v1_price_ratio_input.setRange(0.0, 200.0)
        self.v1_price_ratio_input.setValue(100.0)
        self.v1_price_ratio_input.setSuffix(" %")
        self.v1_price_ratio_input.setDecimals(1)
        self.v1_price_ratio_input.setToolTip("EPRX3発動時のV1価格をインバランス価格に対する比率で設定")
        layout.addWidget(self.v1_price_ratio_input, 8, 1)
        
        # Engine version selection
        layout.addWidget(QLabel("エンジン版本:"), 9, 0)
        self.engine_version_combo = QComboBox()
        self.engine_version_combo.addItems(["V1 (従来版)", "V2 (EPRX3確率版)"])
        self.engine_version_combo.setCurrentIndex(0)  # Default to V1
        self.engine_version_combo.setToolTip("V1: 従来の100%発動版, V2: EPRX3確率&V1価格版")
        layout.addWidget(self.engine_version_combo, 9, 1)
        
        return group
        
    def create_file_group(self):
        """Create file loading group"""
        group = QGroupBox("データファイル")
        layout = QVBoxLayout(group)
        
        # File info display
        self.file_info_label = QLabel("ファイルが選択されていません")
        self.file_info_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.file_info_label)
        
        # File loading buttons
        button_layout = QHBoxLayout()
        
        load_button = QPushButton("📁 CSVファイルを読み込み")
        load_button.clicked.connect(self.load_csv_file)
        load_button.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056CC;
            }
        """)
        button_layout.addWidget(load_button)
        
        # Template download button
        template_button = QPushButton("📄 テンプレート")
        template_button.clicked.connect(self.download_template)
        template_button.setToolTip("CSVテンプレートファイルをダウンロード")
        template_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        button_layout.addWidget(template_button)
        
        layout.addLayout(button_layout)
        
        return group
        
    def create_control_buttons(self):
        """Create optimization control buttons"""
        group = QGroupBox("実行コントロール")
        layout = QVBoxLayout(group)
        
        # Optimization button
        self.optimize_button = QPushButton("最適化実行")
        self.optimize_button.setMinimumHeight(50)
        self.optimize_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.optimize_button.clicked.connect(self.run_optimization)
        self.optimize_button.setEnabled(False)
        layout.addWidget(self.optimize_button)
        
        # Cancel button
        self.cancel_button = QPushButton("キャンセル")
        self.cancel_button.setMinimumHeight(35)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.cancel_button.clicked.connect(self.cancel_optimization)
        self.cancel_button.setEnabled(False)
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
        
        # Wheeling Data Management tab (NEW!)
        wheeling_tab = self.create_wheeling_data_tab()
        self.tab_widget.addTab(wheeling_tab, "託送料金・損失率")
        
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
        
        # Top control bar with error reporting and data debug
        top_control_layout = QHBoxLayout()
        
        # Data debug button (NEW!)
        debug_data_btn = QPushButton("📊 送信データ確認")
        debug_data_btn.clicked.connect(self.show_ai_data_debug)
        debug_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #17A2B8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        debug_data_btn.setToolTip("AIに送信されるデータ内容を確認")
        top_control_layout.addWidget(debug_data_btn)
        
        # Error reporting button
        error_report_btn = QPushButton("🐛 問題報告")
        error_report_btn.clicked.connect(self.show_error_report_dialog)
        error_report_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF6B6B;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF5252;
            }
        """)
        error_report_btn.setToolTip("アプリケーションの不具合や問題を管理者に報告")
        top_control_layout.addWidget(error_report_btn)
        
        top_control_layout.addStretch()
        
        # API status indicator
        self.api_status_label = QLabel("API状態: ")
        top_control_layout.addWidget(self.api_status_label)
        
        layout.addLayout(top_control_layout)
        
        # Separator
        layout.addWidget(self.create_separator())
        
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
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        
        # Quick help and clear buttons
        bottom_buttons_layout = QHBoxLayout()
        
        # Quick help button
        quick_help_btn = QPushButton("💡 よくある質問")
        quick_help_btn.clicked.connect(self.show_quick_help)
        quick_help_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFC107;
                color: #333;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFB300;
            }
        """)
        quick_help_btn.setToolTip("よくある質問とサンプル質問を表示")
        bottom_buttons_layout.addWidget(quick_help_btn)
        
        bottom_buttons_layout.addStretch()
        
        # Clear chat button
        clear_btn = QPushButton("チャット履歴をクリア")
        clear_btn.clicked.connect(self.clear_chat)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        bottom_buttons_layout.addWidget(clear_btn)
        
        layout.addLayout(bottom_buttons_layout)
        
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
        start_date_layout = QHBoxLayout()
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setEnabled(False)
        self.start_date_edit.setDate(QDate.currentDate().addDays(-30))
        self.start_date_edit.dateChanged.connect(self.on_date_range_changed)
        self.start_date_edit.setCalendarPopup(True)  # Enable calendar popup
        start_date_layout.addWidget(self.start_date_edit)
        
        self.start_calendar_button = QPushButton("📅")
        self.start_calendar_button.setEnabled(False)
        self.start_calendar_button.setMaximumWidth(30)
        self.start_calendar_button.setToolTip("カレンダーから開始日を選択")
        self.start_calendar_button.clicked.connect(self.select_start_date)
        start_date_layout.addWidget(self.start_calendar_button)
        
        date_layout.addWidget(QLabel("開始日:"), 1, 1)
        start_date_widget = QWidget()
        start_date_widget.setLayout(start_date_layout)
        date_layout.addWidget(start_date_widget, 1, 2)
        
        end_date_layout = QHBoxLayout()
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setEnabled(False)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.dateChanged.connect(self.on_date_range_changed)
        self.end_date_edit.setCalendarPopup(True)  # Enable calendar popup
        end_date_layout.addWidget(self.end_date_edit)
        
        self.end_calendar_button = QPushButton("📅")
        self.end_calendar_button.setEnabled(False)
        self.end_calendar_button.setMaximumWidth(30)
        self.end_calendar_button.setToolTip("カレンダーから終了日を選択")
        self.end_calendar_button.clicked.connect(self.select_end_date)
        end_date_layout.addWidget(self.end_calendar_button)
        
        date_layout.addWidget(QLabel("終了日:"), 1, 3)
        end_date_widget = QWidget()
        end_date_widget.setLayout(end_date_layout)
        date_layout.addWidget(end_date_widget, 1, 4)
        
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
            self.start_calendar_button.setEnabled(True)
            self.end_calendar_button.setEnabled(True)
        else:
            self.start_date_edit.setEnabled(False)
            self.end_date_edit.setEnabled(False)
            self.start_calendar_button.setEnabled(False)
            self.end_calendar_button.setEnabled(False)
            
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
        """Load CSV file with comprehensive validation and error handling"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "CSVファイルを選択", 
            "", 
            "CSV files (*.csv);;All files (*.*)"
        )
        
        if not file_path:
            return
        
        self.current_file_path = file_path  # Track current file
        self.add_log_message(f"📁 ファイル選択: {file_path}")
        
        # Show loading status
        self.status_bar.showMessage("ファイル読み込み中...")
        self.file_info_label.setText(f"読み込み中: {os.path.basename(file_path)}")
        
        try:
            # Try multiple encodings for Japanese files
            encodings = ['utf-8', 'shift_jis', 'cp932', 'euc-jp']
            df = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    used_encoding = encoding
                    self.add_log_message(f"✅ エンコーディング '{encoding}' で読み込み成功")
                    break
                except UnicodeDecodeError:
                    self.add_log_message(f"⚠️ エンコーディング '{encoding}' での読み込み失敗")
                    continue
                except Exception as e:
                    self.add_log_message(f"❌ エンコーディング '{encoding}' でエラー: {e}")
                    continue
            
            if df is None:
                self.add_log_message("❌ すべてのエンコーディングで読み込み失敗")
                self.file_info_label.setText("エラー: ファイル読み込み失敗")
                self.status_bar.showMessage("ファイル読み込み失敗")
                QMessageBox.critical(self, "エラー", "ファイルの読み込みに失敗しました。\nファイル形式を確認してください。")
                return
            
            self.add_log_message(f"📊 初期読み込み完了: {len(df)}行 x {len(df.columns)}列 (エンコーディング: {used_encoding})")
            
            # Pre-loading data quality assessment
            total_rows = len(df)
            total_cells = df.size
            nan_cells = df.isnull().sum().sum()
            nan_percentage = (nan_cells / total_cells) * 100 if total_cells > 0 else 0
            
            self.add_log_message(f"📈 データ品質評価: NaN値 {nan_cells}/{total_cells} ({nan_percentage:.1f}%)")
            
            # Warn about poor data quality
            if nan_percentage > 95:
                reply = QMessageBox.warning(self, "データ品質警告", 
                                          f"このファイルは{nan_percentage:.1f}%のNaN値を含んでいます。\n"
                                          f"大部分のデータが無効で、最適化に適さない可能性があります。\n\n"
                                          f"【推奨】\n"
                                          f"• sample_data.csv (完全なテストデータ)\n"
                                          f"• test_clean_data.csv (実際の市場データ)\n"
                                          f"を使用することをお勧めします。\n\n"
                                          f"それでも続行しますか？",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    self.file_info_label.setText("読み込みキャンセル (データ品質不良)")
                    self.status_bar.showMessage("読み込みキャンセル")
                    return
            elif nan_percentage > 80:
                reply = QMessageBox.warning(self, "データ品質警告", 
                                          f"このファイルは{nan_percentage:.1f}%のNaN値を含んでいます。\n"
                                          f"データ品質が悪い可能性があります。\n\n"
                                          f"それでも続行しますか？",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    self.file_info_label.setText("読み込みキャンセル")
                    self.status_bar.showMessage("読み込みキャンセル")
                    return
            
            # Comprehensive data validation (7-step process)
            self.add_log_message("🔍 データ検証開始 (7ステップ)")
            
            # Step 1: Remove rows with all NaN values
            initial_rows = len(df)
            df = df.dropna(how='all')
            removed_all_nan = initial_rows - len(df)
            if removed_all_nan > 0:
                self.add_log_message(f"📝 Step 1: 全NaN行を{removed_all_nan}行削除")
            
            # Step 2: Data type normalization and basic cleaning
            self.add_log_message("📝 Step 2: データ型正規化開始")
            
            # Clean column names (remove extra spaces)
            df.columns = df.columns.str.strip()
            
            # Try to convert numeric columns
            numeric_columns = ['JEPX_prediction', 'EPRX1_prediction', 'EPRX3_prediction', 'imbalance']
            for col in numeric_columns:
                if col in df.columns:
                    original_dtype = df[col].dtype
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    converted_count = df[col].notna().sum()
                    self.add_log_message(f"   • {col}: {original_dtype} → numeric ({converted_count}個の有効値)")
            
            # Step 3: Validate slot numbers (should be 1-48)
            self.add_log_message("📝 Step 3: スロット番号検証")
            if 'slot' in df.columns:
                try:
                    # Debug: Check original slot values
                    original_slot_sample = df['slot'].head(10).tolist()
                    original_slot_type = df['slot'].dtype
                    self.add_log_message(f"   🔍 元のslot値サンプル: {original_slot_sample} (型: {original_slot_type})")
                    
                    # Convert to numeric with more tolerant approach
                    df['slot'] = pd.to_numeric(df['slot'], errors='coerce')
                    
                    # Check how many values became NaN during conversion
                    nan_count = df['slot'].isnull().sum()
                    if nan_count > 0:
                        self.add_log_message(f"   ⚠️ 数値変換できないslot値: {nan_count}個")
                        # Show some examples of problematic values
                        problematic_mask = df['slot'].isnull()
                        if problematic_mask.any():
                            # Get original data to show problematic values
                            self.add_log_message(f"   🔍 問題のあるslot値の例: (NaN変換されたもの)")
                    
                    # Convert to Int64 (nullable integer)
                    df['slot'] = df['slot'].astype('Int64')
                    
                    # Check slot range, but be more flexible
                    valid_slots = df['slot'].dropna()
                    if len(valid_slots) > 0:
                        min_slot = valid_slots.min()
                        max_slot = valid_slots.max()
                        unique_count = valid_slots.nunique()
                        self.add_log_message(f"   📊 スロット範囲: {min_slot}-{max_slot} (ユニーク値: {unique_count}個)")
                        
                        # Only filter out completely invalid slots (like negative or > 100)
                        # Be more tolerant for slot ranges
                        before_slot_filter = len(df)
                        if min_slot < 1 or max_slot > 100:  # Extended range for flexibility
                            self.add_log_message(f"   ⚠️ 異常なスロット値を検出: 範囲 {min_slot}-{max_slot}")
                            # Only remove extremely invalid slots
                            df = df[(df['slot'] >= 1) & (df['slot'] <= 100) | df['slot'].isnull()]
                            after_slot_filter = len(df)
                            removed_slots = before_slot_filter - after_slot_filter
                            if removed_slots > 0:
                                self.add_log_message(f"   🗑️ 極端に無効なスロット番号の行を{removed_slots}行削除")
                        else:
                            self.add_log_message(f"   ✅ スロット番号は有効範囲内: {min_slot}-{max_slot}")
                    else:
                        self.add_log_message(f"   ❌ 有効なスロット番号が1つもありません")
                        
                except Exception as e:
                    self.add_log_message(f"   ❌ スロット番号変換エラー: {e}")
                    # Don't fail completely, just log the error
            
            # Step 4: Date validation with multiple format support
            self.add_log_message("📝 Step 4: 日付検証")
            if 'date' in df.columns:
                original_dates = len(df)
                original_date_sample = df['date'].head(5).tolist()
                self.add_log_message(f"   🔍 元の日付サンプル: {original_date_sample}")
                
                successful_conversion = False
                used_format = None
                
                # First try: pandas auto-detection (works best for various formats like 2023/4/1)
                try:
                    self.add_log_message("   🔄 pandas自動検出を試行中...")
                    auto_converted = pd.to_datetime(df['date'], errors='coerce')
                    valid_dates = auto_converted.notna().sum()
                    success_rate = valid_dates / original_dates
                    self.add_log_message(f"   📊 自動検出成功率: {success_rate:.1%} ({valid_dates}/{original_dates})")
                    
                    if success_rate > 0.8:  # If >80% successful
                        df['date'] = auto_converted
                        self.add_log_message(f"   ✅ 自動検出で{valid_dates}個の日付変換成功")
                        successful_conversion = True
                        used_format = "pandas auto-detection"
                    else:
                        self.add_log_message(f"   ⚠️ 自動検出の成功率が低い、手動フォーマットを試行します")
                        
                except Exception as e:
                    self.add_log_message(f"   ❌ 自動検出エラー: {e}")
                
                # If auto-detection failed or had low success rate, try specific formats
                if not successful_conversion:
                    # Try multiple date formats with more comprehensive patterns
                    date_formats = [
                        '%Y/%m/%d',      # 2023/4/1
                        '%Y-%m-%d',      # 2023-04-01
                        '%m/%d/%Y',      # 4/1/2023
                        '%d/%m/%Y',      # 1/4/2023
                        '%Y/%m/%d %H:%M:%S',  # With time
                        '%Y-%m-%d %H:%M:%S'   # With time
                    ]
                    
                    for date_format in date_formats:
                        try:
                            self.add_log_message(f"   🔄 日付形式 '{date_format}' を試行中...")
                            converted_dates = pd.to_datetime(df['date'], format=date_format, errors='coerce')
                            valid_dates = converted_dates.notna().sum()
                            success_rate = valid_dates / original_dates
                            self.add_log_message(f"   📊 成功率: {success_rate:.1%} ({valid_dates}/{original_dates})")
                            
                            if success_rate > 0.8:  # If >80% successful
                                df['date'] = converted_dates
                                self.add_log_message(f"   ✅ 日付形式 '{date_format}' で{valid_dates}個変換成功")
                                successful_conversion = True
                                used_format = date_format
                                break
                        except Exception as e:
                            self.add_log_message(f"   ❌ 形式 '{date_format}' エラー: {e}")
                            continue
                
                if successful_conversion:
                    # Remove rows with invalid dates
                    before_date_filter = len(df)
                    df = df.dropna(subset=['date'])
                    removed_invalid_dates = before_date_filter - len(df)
                    if removed_invalid_dates > 0:
                        self.add_log_message(f"   🗑️ 無効な日付の行を{removed_invalid_dates}行削除")
                    
                    # Show date range if any valid dates remain
                    if len(df) > 0:
                        date_range = f"{df['date'].min().strftime('%Y-%m-%d')} ～ {df['date'].max().strftime('%Y-%m-%d')}"
                        unique_dates = df['date'].nunique()
                        self.add_log_message(f"   📅 日付範囲: {date_range} ({unique_dates}ユニーク日)")
                        self.add_log_message(f"   🎯 使用フォーマット: {used_format}")
                else:
                    self.add_log_message(f"   ❌ 全ての日付形式で変換失敗")
                    # Don't remove all data, just log the issue
                    self.add_log_message(f"   ⚠️ 日付変換に失敗しましたが、データは保持します")
            
            # Step 5: Price data validation and outlier detection
            self.add_log_message("📝 Step 5: 価格データ検証")
            price_columns = ['JEPX_prediction', 'EPRX1_prediction', 'EPRX3_prediction']
            for col in price_columns:
                if col in df.columns:
                    # Basic statistics
                    col_data = df[col].dropna()
                    if len(col_data) > 0:
                        mean_val = col_data.mean()
                        std_val = col_data.std()
                        outliers = len(col_data[(col_data < mean_val - 3*std_val) | (col_data > mean_val + 3*std_val)])
                        self.add_log_message(f"   • {col}: 平均={mean_val:.2f}, 標準偏差={std_val:.2f}, 外れ値={outliers}個")
            
            # Step 6: Data completeness check
            self.add_log_message("📝 Step 6: データ完全性チェック")
            required_columns = ['date', 'slot', 'JEPX_prediction']
            missing_required = [col for col in required_columns if col not in df.columns]
            
            if missing_required:
                self.add_log_message(f"   ❌ 基本必須カラム不足: {missing_required}")
                QMessageBox.critical(self, "データエラー", f"基本必須カラムが不足しています: {missing_required}\n\n必要なカラム: date, slot, JEPX_prediction")
                self.file_info_label.setText("エラー: 基本必須カラム不足")
                self.status_bar.showMessage("データ検証失敗")
                return
            
            # Check for critical data (more flexible than optimization engine)
            critical_columns = ['date', 'slot']
            for col in critical_columns:
                if col in df.columns:
                    # Debug: show data samples before cleaning
                    sample_values = df[col].head(10).tolist()
                    null_count_before = df[col].isnull().sum()
                    total_count = len(df)
                    self.add_log_message(f"🔍 {col}カラム調査 (クリーニング前):")
                    self.add_log_message(f"   • 総数: {total_count}")
                    self.add_log_message(f"   • Null数: {null_count_before}")
                    self.add_log_message(f"   • サンプル値: {sample_values}")
                    
                    # Remove rows where critical columns are null
                    before_critical_clean = len(df)
                    df = df.dropna(subset=[col])
                    removed_critical = before_critical_clean - len(df)
                    if removed_critical > 0:
                        self.add_log_message(f"   🗑️ {col}がNullの行を{removed_critical}行削除")
                    else:
                        self.add_log_message(f"   ✅ {col}: Null行なし、全{len(df)}行が有効")
                        
                    # Debug: show remaining data info
                    if len(df) > 0:
                        remaining_sample = df[col].head(5).tolist()
                        self.add_log_message(f"   📊 残存データサンプル: {remaining_sample}")
                    else:
                        self.add_log_message(f"   ❌ {col}クリーニング後にデータが全て消失")
            
            # Step 7: Final statistics and quality metrics
            self.add_log_message("📝 Step 7: 最終統計")
            
            # Calculate final statistics 
            final_rows = len(df)
            data_retention_rate = (final_rows / total_rows) * 100 if total_rows > 0 else 0
            
            if len(df) == 0:
                self.add_log_message("❌ 基本検証後にデータが残りませんでした")
                
                # Provide more detailed explanation
                error_details = f"""
基本データ検証後に有効なデータが残りませんでした。

【考えられる原因】
1. date, slot カラムの値が全てNaN
2. 数値変換に失敗したデータ
3. ファイル形式の不適合

【対処方法】
• 有効なサンプルファイルを使用:
  - sample_data.csv (36行のテストデータ)
  - test_clean_data.csv (96行の実際データ)

• または、CSVファイルの内容を確認:
  - dateカラムに有効な日付 (例: 2024-01-01)
  - slotカラムに有効な数値 (例: 1, 2, 3...)

現在読み込んだファイル:
• 元の行数: {total_rows:,}行
• NaN率: {nan_percentage:.1f}%
• 最終残存行数: 0行
"""
                
                QMessageBox.critical(self, "データエラー", error_details)
                self.file_info_label.setText("エラー: 有効データなし")
                self.status_bar.showMessage("データ検証失敗")
                return
            
            # Warn about low retention rate but allow continuation

            
            # Warn about low retention rate but allow continuation
            if data_retention_rate < 10:
                reply = QMessageBox.warning(self, "データ保持率警告", 
                                          f"データ保持率が非常に低いです: {data_retention_rate:.1f}%\n\n"
                                          f"元の行数: {total_rows:,}行\n"
                                          f"有効行数: {final_rows:,}行\n"
                                          f"NaN率: {nan_percentage:.1f}%\n\n"
                                          f"最適化結果の精度に影響する可能性があります。\n"
                                          f"それでも続行しますか？",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    self.file_info_label.setText("読み込みキャンセル (低保持率)")
                    self.status_bar.showMessage("読み込みキャンセル")
                    return
            
            # Warn if very little data remains, but don't fail
            if len(df) < 24:
                reply = QMessageBox.warning(self, "データ警告", 
                                          f"データが少なすぎます ({len(df)}行)。\n"
                                          f"最適化には最低24スロット（1日分）のデータが推奨されます。\n\n"
                                          f"それでも続行しますか？",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    self.file_info_label.setText("読み込みキャンセル")
                    self.status_bar.showMessage("読み込みキャンセル")
                    return
            
            self.add_log_message(f"✅ データ検証完了:")
            self.add_log_message(f"   • 最初の行数: {total_rows}")
            self.add_log_message(f"   • 最終行数: {final_rows}")
            self.add_log_message(f"   • データ保持率: {data_retention_rate:.1f}%")
            self.add_log_message(f"   • 使用エンコーディング: {used_encoding}")
            
            # Show success and data summary
            self.current_data = df
            
            # Update date range controls
            self.update_date_range_controls(df)
            
            # Enable optimization button
            self.optimize_button.setEnabled(True)
            
            # Update file info display
            file_info = f"✅ {os.path.basename(file_path)} ({final_rows:,}行)"
            self.file_info_label.setText(file_info)
            
            self.status_bar.showMessage(f"ファイル読み込み完了: {final_rows:,}行のデータ")
            
            self.add_log_message("🎉 CSVファイル読み込み・検証完了")
            
            # Show data summary dialog
            summary_text = f"""
データ読み込み完了

📊 データサマリー:
• ファイル名: {os.path.basename(file_path)}
• 総行数: {final_rows:,}行
• データ保持率: {data_retention_rate:.1f}%
• エンコーディング: {used_encoding}

📅 日付範囲:
• 開始日: {df['date'].min().strftime('%Y-%m-%d')}
• 終了日: {df['date'].max().strftime('%Y-%m-%d')}
• 期間: {(df['date'].max() - df['date'].min()).days + 1}日間

📈 データ品質: {'良好' if data_retention_rate > 90 else '普通' if data_retention_rate > 70 else '要注意'}

最適化を実行する準備ができました。
"""
            
            QMessageBox.information(self, "読み込み完了", summary_text)
            
        except Exception as e:
            self.add_log_message(f"❌ ファイル読み込みエラー: {str(e)}")
            import traceback
            self.add_log_message(f"❌ エラー詳細:\n{traceback.format_exc()}")
            
            self.file_info_label.setText("エラー: ファイル読み込み失敗")
            self.status_bar.showMessage("ファイル読み込み失敗")
            
            QMessageBox.critical(self, "読み込みエラー", 
                               f"ファイルの読み込み中にエラーが発生しました:\n{str(e)}\n\n"
                               f"詳細はログを確認してください。")
            
            # Send error report if email is configured
            if self.settings.value("email/admin_email", ""):
                reply = QMessageBox.question(self, "エラー報告", 
                                           "このエラーを管理者に報告しますか？",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.auto_send_error_report(f"CSV読み込みエラー: {str(e)}", traceback.format_exc())
    
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
            
            # Select engine version based on user choice
            engine_version = self.engine_version_combo.currentText()
            if "V2" in engine_version:
                self.optimization_engine = OptimizationEngineV2(parent=self)
                self.add_log_message(f"🚀 V2エンジン使用 - EPRX3発動率: {params['eprx3_activation_rate']:.1f}%, V1価格比率: {params['v1_price_ratio']:.1f}%")
            else:
                self.optimization_engine = OptimizationEngine(parent=self)
                self.add_log_message("🚀 V1エンジン使用 - 従来の100%発動モード")
            
            self.connect_optimization_signals()
            
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
            
    def update_initial_battery_max(self):
        """Update the maximum value of initial battery input when capacity changes"""
        capacity = self.capacity_input.value()
        self.initial_battery_input.setMaximum(capacity)
        # Auto-adjust if current value exceeds new capacity
        if self.initial_battery_input.value() > capacity:
            self.initial_battery_input.setValue(capacity // 2)  # Set to 50% of new capacity

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
            'initial_soc_kwh': float(self.initial_battery_input.value()),  # New parameter for V2 engine
            'battery_loss_rate': float(self.loss_rate_input.value()) / 100,
            'daily_cycle_limit': float(self.daily_cycle_input.value()),
            'yearly_cycle_limit': float(self.yearly_cycle_input.value()),
            'annual_degradation_rate': float(self.degradation_input.value()) / 100,
            'forecast_period': self.forecast_period_input.value(),
            'eprx1_block_size': self.eprx1_block_input.value(),
            'eprx1_block_cooldown': self.eprx1_cooldown_input.value(),
            'max_daily_eprx1_slots': self.max_eprx1_input.value(),
            'eprx3_activation_rate': float(self.eprx3_activation_input.value()),  # New parameter
            'v1_price_ratio': float(self.v1_price_ratio_input.value()),  # New parameter
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
        self.add_log_message(f"❌ 最適化エラー: {error_message}")
        
        # Clear any partial results
        self.optimization_results = None
        
        # Reset all displays to empty state
        self.init_empty_chart()
        self.init_empty_revenue_chart()
        
        # Show error dialog
        QMessageBox.critical(self, "最適化エラー", 
                           f"最適化中にエラーが発生しました:\n\n{error_message}\n\n"
                           "データを確認してから再度お試しください。")
        
    def reset_ui_after_optimization(self):
        """Reset UI state after optimization completes/fails"""
        self.optimize_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("待機中...")
        
    def update_results_display(self):
        """Update all result displays"""
        self.add_log_message("update_results_display: 開始")
        
        if not self.optimization_results:
            self.add_log_message("update_results_display: optimization_results が None")
            return
            
        try:
            self.add_log_message("update_results_display: 各表示を更新中...")
            
            # Update existing displays
            self.populate_results_table(self.optimization_results['results'])
            self.add_log_message("update_results_display: テーブル更新完了")
            
            self.populate_summary_display(self.optimization_results['summary'])
            self.add_log_message("update_results_display: サマリー更新完了")
            
            self.update_visualization()
            self.add_log_message("update_results_display: メイングラフ更新完了")
            
            self.update_revenue_details()  # NEW!
            self.add_log_message("update_results_display: 収益詳細更新完了")
            
            # Show first tab (graphs) after completion
            self.tab_widget.setCurrentIndex(0)
            self.add_log_message("update_results_display: 全て完了")
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.add_log_message(f"結果表示エラー: {str(e)}")
            self.add_log_message(f"エラー詳細: {error_details}")
        
    def update_revenue_details(self):
        """Update revenue details visualization with improved large data handling"""
        self.add_log_message("🔍 update_revenue_details: 開始")
        
        if not self.optimization_results:
            self.add_log_message("❌ update_revenue_details: optimization_results が None")
            self.init_empty_revenue_chart()
            return
            
        try:
            results_data = self.optimization_results['results']
            if not results_data:
                self.add_log_message("❌ update_revenue_details: results_data が空")
                self.init_empty_revenue_chart()
                return
                
            self.add_log_message(f"📊 update_revenue_details: results_data の行数: {len(results_data)}")
            
            # DEBUG: Check first few rows structure
            if len(results_data) > 0:
                first_row = results_data[0]
                self.add_log_message(f"🔍 データ構造確認 - 最初の行のキー: {list(first_row.keys())}")
                self.add_log_message(f"🔍 サンプルデータ: {first_row}")
            
            # Get filtered data (ALWAYS use filtered data for display)
            df_all = pd.DataFrame(results_data)
            self.add_log_message(f"📋 全データフレーム作成完了: {len(df_all)}行 x {len(df_all.columns)}列")
            self.add_log_message(f"📋 カラム一覧: {list(df_all.columns)}")
            
            df = self.get_filtered_data(df_all)
            
            if df.empty:
                self.add_log_message("❌ update_revenue_details: フィルター後のデータが空")
                self.init_empty_revenue_chart()
                return
                
            self.add_log_message(f"✅ update_revenue_details: フィルター後の行数: {len(df)} (全体: {len(df_all)})")
            
            # Check required columns with detailed logging
            required_cols = ['JEPX_PnL', 'EPRX1_PnL', 'EPRX3_PnL', 'action', 'date', 'slot']
            available_cols = list(df.columns)
            missing_cols = [col for col in required_cols if col not in available_cols]
            
            self.add_log_message(f"🔍 必要カラム: {required_cols}")
            self.add_log_message(f"🔍 利用可能カラム: {available_cols}")
            
            if missing_cols:
                self.add_log_message(f"❌ update_revenue_details: 必要なカラムが不足: {missing_cols}")
                # Show alternative columns that might be available
                potential_alternatives = [col for col in available_cols if any(req in col for req in missing_cols)]
                if potential_alternatives:
                    self.add_log_message(f"🔍 代替可能性のあるカラム: {potential_alternatives}")
                self.init_empty_revenue_chart()
                return
                
            self.add_log_message("✅ update_revenue_details: 必要カラム確認完了 - グラフ描画開始")
                
            # Data type validation
            for col in ['JEPX_PnL', 'EPRX1_PnL', 'EPRX3_PnL']:
                if col in df.columns:
                    try:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        non_numeric_count = df[col].isna().sum()
                        if non_numeric_count > 0:
                            self.add_log_message(f"⚠️ {col}: {non_numeric_count}個の非数値データを0に変換")
                            df[col] = df[col].fillna(0)
                    except Exception as e:
                        self.add_log_message(f"❌ {col}の数値変換エラー: {e}")
                        df[col] = 0
                
            # Prepare data for visualization with memory optimization
            df = df.copy()  # Avoid modifying original data
            
            # Date and time processing with error handling
            try:
                df['datetime'] = pd.to_datetime(df['date']) + pd.to_timedelta((df['slot'] - 1) * 0.5, unit='h')
                self.add_log_message("✅ datetime列作成完了")
            except Exception as e:
                self.add_log_message(f"❌ datetime作成エラー: {e}")
                # Fallback: use row index as time
                df['datetime'] = pd.date_range(start='2024-01-01', periods=len(df), freq='30min')
                
            df['total_pnl'] = df['JEPX_PnL'] + df['EPRX1_PnL'] + df['EPRX3_PnL']
            
            total_pnl_stats = {
                'sum': df['total_pnl'].sum(),
                'mean': df['total_pnl'].mean(),
                'min': df['total_pnl'].min(),
                'max': df['total_pnl'].max(),
                'std': df['total_pnl'].std()
            }
            self.add_log_message(f"📊 total_pnl統計: {total_pnl_stats}")
            
            # Clear previous plots
            self.revenue_figure.clear()
            
            # Create subplots with adjusted spacing for large datasets
            gs = self.revenue_figure.add_gridspec(3, 2, hspace=0.5, wspace=0.4)
            
            # 1. Hourly Revenue Breakdown (optimized for large datasets)
            self.add_log_message("📈 グラフ1: 時間別収益分布を作成中...")
            ax1 = self.revenue_figure.add_subplot(gs[0, :])
            
            try:
                # Group by hour more efficiently
                hourly_pnl = df.groupby(df['datetime'].dt.hour)['total_pnl'].sum()
                
                self.add_log_message(f"📊 hourly_pnl 統計: min={hourly_pnl.min():.0f}, max={hourly_pnl.max():.0f}, データ点数={len(hourly_pnl)}")
                
                # Create bar chart with better formatting
                bars = ax1.bar(hourly_pnl.index, hourly_pnl.values, 
                              color=['green' if x > 0 else 'red' for x in hourly_pnl.values],
                              alpha=0.7, edgecolor='black', linewidth=0.5)
                
                ax1.set_title('時間別収益分布', fontsize=14, fontweight='bold', pad=20)
                ax1.set_xlabel('時間')
                ax1.set_ylabel('収益 (円)')
                ax1.grid(True, alpha=0.3)
                ax1.set_xticks(range(0, 24, 2))
                
                # Add value labels only for significant bars (avoid clutter)
                max_val = max(abs(hourly_pnl.values)) if len(hourly_pnl.values) > 0 else 1
                for bar in bars:
                    height = bar.get_height()
                    if abs(height) > max_val * 0.05:  # Only label bars > 5% of max
                        ax1.text(bar.get_x() + bar.get_width()/2., height/2,
                                f'{int(height/1000):.0f}K' if abs(height) > 1000 else f'{int(height)}',
                                ha='center', va='center', fontsize=6, fontweight='bold')  # Reduced from 9 to 6
                
                self.add_log_message("✅ グラフ1完了")
            
            except Exception as e:
                self.add_log_message(f"❌ グラフ1エラー: {e}")
                ax1.text(0.5, 0.5, f'時間別グラフエラー:\n{str(e)}', 
                        ha='center', va='center', transform=ax1.transAxes)
            
            # 2. Market Contribution Analysis (optimized)
            self.add_log_message("📈 グラフ2: 市場別収益貢献を作成中...")
            ax2 = self.revenue_figure.add_subplot(gs[1, 0])
            
            try:
                market_totals = {
                    'JEPX': df['JEPX_PnL'].sum(),
                    'EPRX1': df['EPRX1_PnL'].sum(), 
                    'EPRX3': df['EPRX3_PnL'].sum()
                }
                
                self.add_log_message(f"📊 market_totals: {market_totals}")
                
                # Filter out zero/negligible contributions
                market_totals_filtered = {k: v for k, v in market_totals.items() if abs(v) > 100}  # Minimum 100 yen
                
                if market_totals_filtered:
                    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
                    wedges, texts, autotexts = ax2.pie(
                        market_totals_filtered.values(), 
                        labels=market_totals_filtered.keys(),
                        autopct=lambda pct: f'{pct:.1f}%\n({int(pct/100 * sum(market_totals_filtered.values())/1000):.0f}K円)' if abs(pct/100 * sum(market_totals_filtered.values())) > 1000 else f'{pct:.1f}%',
                        colors=colors[:len(market_totals_filtered)],
                        startangle=90,
                        textprops={'fontsize': 6}  # Set default text size
                    )
                    ax2.set_title('市場別収益貢献', fontsize=12, fontweight='bold')
                    
                    # Improve text readability with smaller font size
                    for autotext in autotexts:
                        autotext.set_color('white')
                        autotext.set_fontweight('bold')
                        autotext.set_fontsize(6)  # Reduced from 8 to 6
                    
                    # Also reduce label font size
                    for text in texts:
                        text.set_fontsize(7)  # Smaller label font
                else:
                    ax2.text(0.5, 0.5, 'データなし\n(すべての市場で収益100円未満)', 
                            ha='center', va='center', transform=ax2.transAxes, fontsize=10)
                    ax2.set_title('市場別収益貢献', fontsize=12, fontweight='bold')
                
                self.add_log_message("✅ グラフ2完了")
                
            except Exception as e:
                self.add_log_message(f"❌ グラフ2エラー: {e}")
                ax2.text(0.5, 0.5, f'市場別グラフエラー:\n{str(e)}', 
                        ha='center', va='center', transform=ax2.transAxes)
            
            # 3. Action Distribution (optimized)
            self.add_log_message("📈 グラフ3: アクション分布を作成中...")
            ax3 = self.revenue_figure.add_subplot(gs[1, 1])
            
            try:
                action_counts = df['action'].value_counts()
                self.add_log_message(f"📊 action_counts: {action_counts.to_dict()}")
                
                colors_action = {'charge': '#FF9999', 'discharge': '#99FF99', 'eprx1': '#9999FF', 
                               'eprx3': '#FFFF99', 'idle': '#CCCCCC'}
                
                if len(action_counts) > 0:
                    wedges, texts, autotexts = ax3.pie(
                        action_counts.values,
                        labels=action_counts.index,
                        autopct='%1.1f%%',
                        colors=[colors_action.get(action, '#CCCCCC') for action in action_counts.index],
                        startangle=90,
                        textprops={'fontsize': 6}  # Set default text size
                    )
                    ax3.set_title('アクション分布', fontsize=12, fontweight='bold')
                    
                    # Reduce font sizes for better fit
                    for autotext in autotexts:
                        autotext.set_fontsize(6)  # Reduced from 8 to 6
                    
                    # Also reduce label font size
                    for text in texts:
                        text.set_fontsize(7)  # Smaller label font
                else:
                    ax3.text(0.5, 0.5, 'アクションデータなし', 
                            ha='center', va='center', transform=ax3.transAxes)
                    ax3.set_title('アクション分布', fontsize=12, fontweight='bold')
                
                self.add_log_message("✅ グラフ3完了")
                
            except Exception as e:
                self.add_log_message(f"❌ グラフ3エラー: {e}")
                ax3.text(0.5, 0.5, f'アクショングラフエラー:\n{str(e)}', 
                        ha='center', va='center', transform=ax3.transAxes)
            
            # 4. Daily Revenue Trend (optimized for large datasets)
            self.add_log_message("📈 グラフ4: 日別収益推移を作成中...")
            ax4 = self.revenue_figure.add_subplot(gs[2, :])
            
            try:
                daily_pnl = df.groupby('date')['total_pnl'].sum()
                daily_pnl.index = pd.to_datetime(daily_pnl.index)
                
                self.add_log_message(f"📊 daily_pnl データポイント数: {len(daily_pnl)}")
                
                # Optimize plotting for large datasets
                if len(daily_pnl) > 365:  # More than 1 year of data
                    # Sample data for plotting performance (show every nth day)
                    sample_interval = max(1, len(daily_pnl) // 200)  # Max 200 points
                    daily_pnl_sampled = daily_pnl.iloc[::sample_interval]
                    self.add_log_message(f"📊 大量データのため{sample_interval}日間隔でサンプリング")
                else:
                    daily_pnl_sampled = daily_pnl
                
                # Line plot with markers (smaller markers for large datasets)
                marker_size = 4 if len(daily_pnl_sampled) > 50 else 8
                line_width = 2.0 if len(daily_pnl_sampled) <= 50 else 1.5
                
                # Plot main line with better visibility
                ax4.plot(daily_pnl_sampled.index, daily_pnl_sampled.values, 
                        marker='o', linewidth=line_width, markersize=marker_size, 
                        color='#1f77b4', markerfacecolor='white', markeredgecolor='#1f77b4',
                        markeredgewidth=1.5, zorder=3)
                
                # Fill positive/negative areas with better colors and transparency
                ax4.fill_between(daily_pnl_sampled.index, daily_pnl_sampled.values, 0, 
                               where=(daily_pnl_sampled.values > 0), color='#2ca02c', alpha=0.5, 
                               label='利益', zorder=1)
                ax4.fill_between(daily_pnl_sampled.index, daily_pnl_sampled.values, 0,
                               where=(daily_pnl_sampled.values <= 0), color='#d62728', alpha=0.5, 
                               label='損失', zorder=2)
                
                ax4.set_title(f'日別収益推移 ({self.get_date_range_title()})', fontsize=12, fontweight='bold')
                ax4.set_xlabel('日付')
                ax4.set_ylabel('収益 (円)')
                ax4.grid(True, alpha=0.3)
                ax4.legend()
                
                # Format x-axis dates based on data span with shorter year format
                if len(daily_pnl) > 180:  # More than 6 months
                    ax4.xaxis.set_major_locator(mdates.MonthLocator())
                    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%y-%m'))  # Changed from %Y-%m to %y-%m
                elif len(daily_pnl) > 30:  # More than 1 month
                    ax4.xaxis.set_major_locator(mdates.WeekdayLocator())
                    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                else:
                    ax4.xaxis.set_major_locator(mdates.DayLocator())
                    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                
                # Set y-axis range to ensure data visibility
                y_min, y_max = daily_pnl_sampled.min(), daily_pnl_sampled.max()
                y_range = max(abs(y_max), abs(y_min))
                if y_range > 0:
                    ax4.set_ylim(y_min - y_range * 0.1, y_max + y_range * 0.1)
                
                # Add zero line for reference
                ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=0.8)
                
                # Rotate labels for better readability with smaller font size
                plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)  # Added fontsize=8
                
                # Add overall statistics text (use all data, not sampled)
                total_profit = df['total_pnl'].sum()
                avg_daily_profit = daily_pnl.mean()
                best_day = daily_pnl.idxmax()
                best_day_profit = daily_pnl.max()
                worst_day = daily_pnl.idxmin()
                worst_day_profit = daily_pnl.min()
                
                # Create compact stats text for better positioning
                stats_text = f"""収益サマリー ({self.get_date_range_title()}): 総収益 {total_profit:,.0f}円 | 平均日収 {avg_daily_profit:,.0f}円 | 最高 {best_day.strftime('%m/%d')}({best_day_profit:,.0f}円) | 最低 {worst_day.strftime('%m/%d')}({worst_day_profit:,.0f}円)"""
                
                # Position stats box at bottom to avoid overlap with any graphs
                self.revenue_figure.text(0.5, 0.02, stats_text, transform=self.revenue_figure.transFigure,
                                       fontsize=8, verticalalignment='bottom', horizontalalignment='center',
                                       fontweight='bold', bbox=dict(boxstyle='round,pad=0.3', 
                                       facecolor='lightblue', alpha=0.9))
                
                self.add_log_message("✅ グラフ4完了")
                
            except Exception as e:
                self.add_log_message(f"❌ グラフ4エラー: {e}")
                ax4.text(0.5, 0.5, f'日別推移グラフエラー:\n{str(e)}', 
                        ha='center', va='center', transform=ax4.transAxes)
            
            # Overall title with better positioning
            period_title = f"収益詳細分析 - {self.get_date_range_title()}"
            self.revenue_figure.suptitle(period_title, fontsize=14, fontweight='bold', y=0.97)
            
            # Adjust layout to prevent overlapping, accounting for bottom stats box
            self.revenue_figure.tight_layout(rect=[0, 0.08, 1, 0.95])
            
            self.revenue_canvas.draw()
            self.add_log_message("✅ update_revenue_details: グラフ描画完全完了")
            
        except Exception as e:
            self.add_log_message(f"❌ 収益詳細グラフ更新エラー: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            self.add_log_message(f"❌ エラー詳細: {error_details}")
            
            # Show error message on chart
            self.revenue_figure.clear()
            ax = self.revenue_figure.add_subplot(111)
            ax.text(0.5, 0.5, f'収益詳細グラフエラー:\n{str(e)}\n\n詳細はログを確認してください', 
                    horizontalalignment='center', verticalalignment='center', 
                    transform=ax.transAxes, fontsize=12, color='red')
            ax.set_title('収益詳細分析 - エラー')
            self.revenue_canvas.draw()
            
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
        
        # Rotate labels for better readability with smaller font size
        for ax in [ax1, ax2]:
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)  # Added fontsize=8
            
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
            self.initial_battery_input.setValue(2000)  # 50% of default capacity
            self.loss_rate_input.setValue(5.0)
            self.daily_cycle_input.setValue(1)
            self.forecast_period_input.setValue(48)
            self.eprx1_block_input.setValue(3)
            self.eprx1_cooldown_input.setValue(2)
            self.max_eprx1_input.setValue(6)
            self.yearly_cycle_input.setValue(365)
            self.degradation_input.setValue(3.0)
            self.eprx3_activation_input.setValue(100.0)
            self.v1_price_ratio_input.setValue(100.0)
            self.engine_version_combo.setCurrentIndex(0)  # V1 default
            
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
        
        # Prepare optimization data for context (ALWAYS use full data for AI analysis)
        optimization_context = None
        if self.optimization_results:
            # Get ALL results data (not filtered) for comprehensive AI analysis
            all_results = self.optimization_results.get("results", [])
            
            # Create a comprehensive summary of ALL optimization results for the AI
            optimization_context = {
                "summary": self.optimization_results.get("summary", {}),
                "total_rows": len(all_results),
                "date_range_full": "全期間" if all_results else "データなし",
                "current_display_filter": self.get_date_range_title(),
                "full_results_sample": all_results[-20:] if all_results else [],  # Last 20 rows for context
                "data_statistics": self._generate_ai_context_stats(all_results) if all_results else {}
            }
            
            self.add_log_message(f"🤖 AI用データ準備完了: 全{len(all_results)}行のデータを送信")
            self.add_log_message(f"🤖 サマリーキー数: {len(optimization_context['summary'])}個")
            self.add_log_message(f"🤖 統計データ準備: {len(optimization_context['data_statistics'])}カテゴリ")
            
            # Log key statistics for debugging
            if optimization_context['data_statistics']:
                revenue_stats = optimization_context['data_statistics'].get('revenue_analysis', {})
                if revenue_stats:
                    total_revenue = revenue_stats.get('total_revenue', 0)
                    self.add_log_message(f"🤖 総収益データ: ¥{total_revenue:,.0f}")
        else:
            self.add_log_message("🤖 最適化結果がないため、AIにデータを送信しません")
            QMessageBox.warning(self, "データ未準備", "最適化結果がありません。\nまず最適化を実行してからAI分析をご利用ください。")
            # Re-enable input
            self.chat_input.setEnabled(True)
            self.send_button.setEnabled(True)
            self.send_button.setText("送信")
            return
        
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
        
        # Add V2 specific information first if available
        if 'EPRX3_Activation_Rate' in summary_data or 'V1_Price_Ratio' in summary_data:
            summary_text += "=== V2エンジン設定 ===\n"
            if 'Initial_SOC_kWh' in summary_data:
                summary_text += f"初期蓄電量: {summary_data['Initial_SOC_kWh']:.1f} kWh\n"
            if 'EPRX3_Activation_Rate' in summary_data:
                summary_text += f"EPRX3発動率: {summary_data['EPRX3_Activation_Rate']:.1f}%\n"
            if 'V1_Price_Ratio' in summary_data:
                summary_text += f"V1価格比率: {summary_data['V1_Price_Ratio']:.1f}%\n"
            if 'EPRX3_Planned_Count' in summary_data:
                summary_text += f"EPRX3実行回数: {summary_data['EPRX3_Planned_Count']}回\n"
            summary_text += "\n"
        
        summary_text += "=== 財務結果 ===\n"
        
        for key, value in summary_data.items():
            # Skip V2 specific fields as they're already shown
            if key in ['EPRX3_Activation_Rate', 'V1_Price_Ratio', 'EPRX3_Planned_Count', 'Initial_SOC_kWh']:
                continue
                
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
    
    def _generate_ai_context_stats(self, results_data):
        """Generate comprehensive statistics for AI context"""
        try:
            if not results_data:
                return {}
                
            df = pd.DataFrame(results_data)
            
            # Date range analysis
            if 'date' in df.columns:
                dates = pd.to_datetime(df['date'], errors='coerce')
                date_stats = {
                    "start_date": dates.min().strftime('%Y-%m-%d') if not dates.isna().all() else "不明",
                    "end_date": dates.max().strftime('%Y-%m-%d') if not dates.isna().all() else "不明",
                    "total_days": (dates.max() - dates.min()).days + 1 if not dates.isna().all() else 0,
                    "unique_dates": dates.nunique()
                }
            else:
                date_stats = {}
            
            # Revenue analysis (全期間)
            revenue_stats = {}
            if all(col in df.columns for col in ['JEPX_PnL', 'EPRX1_PnL', 'EPRX3_PnL']):
                df['total_pnl'] = df['JEPX_PnL'] + df['EPRX1_PnL'] + df['EPRX3_PnL']
                
                revenue_stats = {
                    "total_revenue": float(df['total_pnl'].sum()),
                    "average_slot_revenue": float(df['total_pnl'].mean()),
                    "max_slot_revenue": float(df['total_pnl'].max()),
                    "min_slot_revenue": float(df['total_pnl'].min()),
                    "profitable_slots": int((df['total_pnl'] > 0).sum()),
                    "loss_slots": int((df['total_pnl'] < 0).sum()),
                    "breakeven_slots": int((df['total_pnl'] == 0).sum()),
                    "jepx_total": float(df['JEPX_PnL'].sum()),
                    "eprx1_total": float(df['EPRX1_PnL'].sum()),
                    "eprx3_total": float(df['EPRX3_PnL'].sum())
                }
                
                # Daily revenue analysis
                if 'date' in df.columns:
                    daily_pnl = df.groupby('date')['total_pnl'].sum()
                    revenue_stats.update({
                        "average_daily_revenue": float(daily_pnl.mean()),
                        "best_day_revenue": float(daily_pnl.max()),
                        "worst_day_revenue": float(daily_pnl.min()),
                        "profitable_days": int((daily_pnl > 0).sum()),
                        "loss_days": int((daily_pnl < 0).sum())
                    })
            
            # Action analysis
            action_stats = {}
            if 'action' in df.columns:
                action_counts = df['action'].value_counts().to_dict()
                action_stats = {
                    "action_distribution": action_counts,
                    "most_common_action": df['action'].mode().iloc[0] if not df['action'].empty else "不明",
                    "action_diversity": len(action_counts)
                }
            
            # Energy analysis
            energy_stats = {}
            energy_cols = ['charge_kWh', 'discharge_kWh', 'EPRX3_kWh', 'battery_level_kWh']
            available_energy_cols = [col for col in energy_cols if col in df.columns]
            
            for col in available_energy_cols:
                if df[col].dtype in ['int64', 'float64']:
                    energy_stats[f"{col}_total"] = float(df[col].sum())
                    energy_stats[f"{col}_average"] = float(df[col].mean())
                    energy_stats[f"{col}_max"] = float(df[col].max())
            
            return {
                "date_info": date_stats,
                "revenue_analysis": revenue_stats,
                "action_analysis": action_stats,
                "energy_analysis": energy_stats,
                "total_data_points": len(df),
                "data_completeness": "完全" if df.isnull().sum().sum() == 0 else "一部欠損あり"
            }
            
        except Exception as e:
            return {"error": f"統計生成エラー: {str(e)}"}
    
    def show_settings_dialog(self):
        """Show comprehensive settings dialog"""
        try:
            self.add_log_message("⚙️ 設定ダイアログを開いています...")
            
            dialog = QDialog(self)
            dialog.setWindowTitle("設定")
            dialog.setFixedSize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            # Create tab widget for different settings categories
            tab_widget = QTabWidget()
            
            # OpenAI API Tab
            try:
                api_tab = QWidget()
                api_layout = QFormLayout(api_tab)
                
                # API Key field
                self.settings_api_key = QLineEdit()
                self.settings_api_key.setEchoMode(QLineEdit.EchoMode.Password)
                current_api_key = self.get_api_key()
                if current_api_key:
                    self.settings_api_key.setText("*" * 20)  # Mask the key
                api_layout.addRow("OpenAI APIキー:", self.settings_api_key)
                
                # API key input toggle
                show_api_key = QPushButton("表示/非表示")
                show_api_key.clicked.connect(lambda: self.toggle_password_visibility(self.settings_api_key))
                api_layout.addRow("", show_api_key)
                
                # API test button
                test_api_button = QPushButton("APIテスト")
                test_api_button.clicked.connect(self.test_api_connection)
                api_layout.addRow("", test_api_button)
                
                tab_widget.addTab(api_tab, "🤖 AI設定")
                self.add_log_message("✅ API設定タブ作成完了")
                
            except Exception as e:
                self.add_log_message(f"❌ API設定タブエラー: {e}")
                return
            
            # Email Settings Tab
            try:
                email_tab = QWidget()
                email_layout = QFormLayout(email_tab)
                
                # SMTP Settings
                self.smtp_server = QLineEdit(self.settings.value("email/smtp_server", "smtp.gmail.com"))
                email_layout.addRow("SMTPサーバー:", self.smtp_server)
                
                self.smtp_port = QSpinBox()
                self.smtp_port.setRange(1, 65535)
                self.smtp_port.setValue(int(self.settings.value("email/smtp_port", 587)))
                email_layout.addRow("SMTPポート:", self.smtp_port)
                
                self.sender_email = QLineEdit(self.settings.value("email/sender_email", ""))
                email_layout.addRow("送信者メール:", self.sender_email)
                
                self.sender_password = QLineEdit(self.settings.value("email/sender_password", ""))
                self.sender_password.setEchoMode(QLineEdit.EchoMode.Password)
                email_layout.addRow("送信者パスワード:", self.sender_password)
                
                # Password visibility toggle
                show_email_pass = QPushButton("表示/非表示")
                show_email_pass.clicked.connect(lambda: self.toggle_password_visibility(self.sender_password))
                email_layout.addRow("", show_email_pass)
                
                self.admin_email = QLineEdit(self.settings.value("email/admin_email", ""))
                email_layout.addRow("管理者メール:", self.admin_email)
                
                # Email test button
                test_email_button = QPushButton("メールテスト")
                test_email_button.clicked.connect(self.test_email_settings)
                email_layout.addRow("", test_email_button)
                
                # Email help text
                help_text = QLabel("""
Gmailを使用する場合：
1. 2段階認証を有効にする
2. アプリパスワードを生成する
3. 生成されたパスワードを使用する

Outlook/Hotmailの場合：
- smtp-mail.outlook.com:587
                """)
                help_text.setStyleSheet("color: gray; font-size: 10px;")
                email_layout.addRow("ヘルプ:", help_text)
                
                tab_widget.addTab(email_tab, "📧 メール設定")
                self.add_log_message("✅ メール設定タブ作成完了")
                
            except Exception as e:
                self.add_log_message(f"❌ メール設定タブエラー: {e}")
                return
            
            # General Settings Tab
            try:
                general_tab = QWidget()
                general_layout = QFormLayout(general_tab)
                
                # Log level
                self.log_level = QComboBox()
                self.log_level.addItems(["ERROR", "WARNING", "INFO", "DEBUG"])
                current_log = self.settings.value("general/log_level", "INFO")
                self.log_level.setCurrentText(current_log)
                general_layout.addRow("ログレベル:", self.log_level)
                
                # Auto save results
                self.auto_save = QCheckBox()
                self.auto_save.setChecked(bool(self.settings.value("general/auto_save", True)))
                general_layout.addRow("結果自動保存:", self.auto_save)
                
                # Theme selection (placeholder for future)
                self.theme_combo = QComboBox()
                self.theme_combo.addItems(["ライト", "ダーク"])
                current_theme = self.settings.value("general/theme", "ライト")
                self.theme_combo.setCurrentText(current_theme)
                general_layout.addRow("テーマ:", self.theme_combo)
                
                tab_widget.addTab(general_tab, "⚙️ 一般")
                self.add_log_message("✅ 一般設定タブ作成完了")
                
            except Exception as e:
                self.add_log_message(f"❌ 一般設定タブエラー: {e}")
                return
            
            layout.addWidget(tab_widget)
            
            # Dialog buttons
            button_layout = QHBoxLayout()
            
            reset_button = QPushButton("リセット")
            reset_button.clicked.connect(lambda: self.reset_all_settings(dialog))
            button_layout.addWidget(reset_button)
            
            button_layout.addStretch()
            
            cancel_button = QPushButton("キャンセル")
            cancel_button.clicked.connect(dialog.reject)
            button_layout.addWidget(cancel_button)
            
            save_button = QPushButton("保存")
            save_button.clicked.connect(lambda: self.save_all_settings(dialog))
            save_button.setDefault(True)
            button_layout.addWidget(save_button)
            
            layout.addLayout(button_layout)
            
            self.add_log_message("✅ 設定ダイアログ作成完了")
            dialog.exec()
            
        except Exception as e:
            self.add_log_message(f"❌ 設定ダイアログエラー: {str(e)}")
            import traceback
            self.add_log_message(f"❌ 詳細: {traceback.format_exc()}")
            QMessageBox.critical(self, "エラー", f"設定画面でエラーが発生しました:\n{str(e)}")
    
    def toggle_password_visibility(self, line_edit):
        """Toggle password field visibility"""
        if line_edit.echoMode() == QLineEdit.EchoMode.Password:
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
    
    def test_api_connection(self):
        """Test OpenAI API connection"""
        api_key = self.settings_api_key.text()
        if api_key.startswith("*"):
            api_key = self.get_api_key()
        
        if not api_key:
            QMessageBox.warning(self, "警告", "APIキーが入力されていません")
            return
        
        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            QMessageBox.information(self, "成功", "API接続テスト成功")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"API接続テスト失敗:\n{str(e)}")
    
    def test_email_settings(self):
        """Test email settings"""
        # Save current settings temporarily
        self.settings.setValue("email/smtp_server", self.smtp_server.text())
        self.settings.setValue("email/smtp_port", self.smtp_port.value())
        self.settings.setValue("email/sender_email", self.sender_email.text())
        self.settings.setValue("email/sender_password", self.sender_password.text())
        self.settings.setValue("email/admin_email", self.admin_email.text())
        
        success, message = self.email_manager.test_email_settings()
        
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.warning(self, "エラー", message)
    
    def save_all_settings(self, dialog):
        """Save all settings from dialog"""
        try:
            # Save API settings
            api_key = self.settings_api_key.text()
            if api_key and not api_key.startswith("*"):
                self.save_api_key(api_key)
            
            # Save email settings
            self.settings.setValue("email/smtp_server", self.smtp_server.text())
            self.settings.setValue("email/smtp_port", self.smtp_port.value())
            self.settings.setValue("email/sender_email", self.sender_email.text())
            self.settings.setValue("email/sender_password", self.sender_password.text())
            self.settings.setValue("email/admin_email", self.admin_email.text())
            
            # Save general settings
            self.settings.setValue("general/log_level", self.log_level.currentText())
            self.settings.setValue("general/auto_save", self.auto_save.isChecked())
            self.settings.setValue("general/theme", self.theme_combo.currentText())
            
            self.settings.sync()
            
            # Update UI
            self.update_api_status()
            
            QMessageBox.information(dialog, "成功", "設定を保存しました")
            dialog.accept()
            
        except Exception as e:
            QMessageBox.critical(dialog, "エラー", f"設定保存エラー:\n{str(e)}")
    
    def reset_all_settings(self, dialog):
        """Reset all settings to defaults"""
        reply = QMessageBox.question(dialog, "確認", 
                                   "すべての設定をリセットしますか？\nこの操作は元に戻せません。",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.clear()
            self.settings.sync()
            QMessageBox.information(dialog, "完了", "設定をリセットしました。\nアプリケーションを再起動してください。")
            dialog.accept()
    
    def show_error_report_dialog(self):
        """Show error reporting dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("🐛 問題報告")
        dialog.setFixedSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Title
        title = QLabel("アプリケーションの問題を報告")
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel("発生した問題について詳しく教えてください：")
        layout.addWidget(desc)
        
        # Problem description text area
        self.problem_description = QTextEdit()
        self.problem_description.setPlaceholderText("""例：
- 収益グラフが表示されない
- 最適化が途中で止まる
- エラーメッセージが表示される
- データ読み込みができない

具体的な状況や再現手順も記載してください。""")
        layout.addWidget(self.problem_description)
        
        # Include log data checkbox
        self.include_logs = QCheckBox("ログデータを含める（推奨）")
        self.include_logs.setChecked(True)
        layout.addWidget(self.include_logs)
        
        # Status
        self.email_status_label = QLabel("")
        layout.addWidget(self.email_status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_button = QPushButton("キャンセル")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        button_layout.addStretch()
        
        send_button = QPushButton("📧 報告送信")
        send_button.clicked.connect(lambda: self.send_error_report(dialog))
        send_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(send_button)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def send_error_report(self, dialog):
        """Send error report via email"""
        description = self.problem_description.toPlainText().strip()
        
        if not description:
            QMessageBox.warning(dialog, "警告", "問題の説明を入力してください")
            return
        
        # Check email settings
        admin_email = self.settings.value("email/admin_email", "")
        if not admin_email:
            reply = QMessageBox.question(dialog, "設定が必要", 
                                       "メール設定が未設定です。設定画面を開きますか？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                dialog.accept()
                self.show_settings_dialog()
            return
        
        # Collect context information
        user_context = f"""
アプリケーションバージョン: Battery Optimizer 2.0
OS: {self.get_system_info()}
最後の最適化: {'あり' if self.optimization_results else 'なし'}
現在のファイル: {getattr(self, 'current_file_path', '未読み込み')}
"""
        
        # Collect log data if requested
        log_data = ""
        if self.include_logs.isChecked():
            log_data = self.log_text.toPlainText()[-2000:]  # Last 2000 characters
        
        # Send email
        self.email_status_label.setText("📧 送信中...")
        self.email_status_label.repaint()
        
        success, message = self.email_manager.send_error_report(
            error_message=description,
            user_context=user_context,
            log_data=log_data
        )
        
        if success:
            QMessageBox.information(dialog, "送信完了", 
                                  "問題報告を送信しました。\n管理者から回答があるまでお待ちください。")
            dialog.accept()
        else:
            QMessageBox.critical(dialog, "送信エラー", f"報告送信に失敗しました:\n{message}")
            self.email_status_label.setText(f"❌ エラー: {message}")
    
    def get_system_info(self):
        """Get system information for error reporting"""
        import platform
        return f"{platform.system()} {platform.release()}"
    
    def auto_send_error_report(self, error_message, traceback_info):
        """Automatically send error report"""
        try:
            user_context = f"""
アプリケーションバージョン: Battery Optimizer 2.0
OS: {self.get_system_info()}
最後の最適化: {'あり' if self.optimization_results else 'なし'}
現在のファイル: {getattr(self, 'current_file_path', '未読み込み')}
自動報告: True
"""
            
            log_data = self.log_text.toPlainText()[-1500:]  # Last 1500 characters
            
            success, message = self.email_manager.send_error_report(
                error_message=error_message,
                user_context=user_context,
                log_data=log_data
            )
            
            if success:
                self.add_log_message("📧 エラー報告を自動送信しました")
            else:
                self.add_log_message(f"📧 エラー報告送信失敗: {message}")
                
        except Exception as e:
            self.add_log_message(f"�� 自動エラー報告エラー: {e}")
    
    def get_api_key(self):
        """Get API key from secure storage"""
        try:
            # Try to get from QSettings (basic storage)
            api_key = self.settings.value("openai/api_key", "")
            return api_key
        except Exception as e:
            self.add_log_message(f"API キー取得エラー: {e}")
            return ""
    
    def save_api_key(self, api_key):
        """Save API key to secure storage"""
        try:
            self.settings.setValue("openai/api_key", api_key)
            self.settings.sync()
            self.add_log_message("API キーを保存しました")
            return True
        except Exception as e:
            self.add_log_message(f"API キー保存エラー: {e}")
            return False
    
    def show_ai_data_debug(self):
        """Show AI data debug dialog"""
        if not self.optimization_results:
            QMessageBox.warning(self, "データ未準備", "最適化結果がありません。\nまず最適化を実行してからご利用ください。")
            return
        
        # Create debug dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("AI送信データ詳細")
        dialog.setModal(True)
        dialog.resize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        # Title
        title = QLabel("AIに送信されるデータ内容")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Create tab widget for different data views
        tab_widget = QTabWidget()
        
        # Summary data tab
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        summary_text = QPlainTextEdit()
        summary_text.setReadOnly(True)
        summary_text.setFont(QFont("Monaco", 10))
        
        # Prepare the data that would be sent to AI
        all_results = self.optimization_results.get("results", [])
        optimization_context = {
            "summary": self.optimization_results.get("summary", {}),
            "total_rows": len(all_results),
            "date_range_full": "全期間" if all_results else "データなし",
            "current_display_filter": self.get_date_range_title(),
            "data_statistics": self._generate_ai_context_stats(all_results) if all_results else {}
        }
        
        # Format summary info
        summary_info = "【基本サマリー】\n"
        for key, value in optimization_context['summary'].items():
            if isinstance(value, (int, float)):
                if 'Profit' in key or 'Fee' in key:
                    summary_info += f"{key}: ¥{value:,.0f}\n"
                elif 'kWh' in key:
                    summary_info += f"{key}: {value:,.1f} kWh\n"
                else:
                    summary_info += f"{key}: {value:,.2f}\n"
            else:
                summary_info += f"{key}: {value}\n"
        
        summary_text.setPlainText(summary_info)
        summary_layout.addWidget(summary_text)
        tab_widget.addTab(summary_tab, "サマリー")
        
        # Statistics data tab
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        stats_text = QPlainTextEdit()
        stats_text.setReadOnly(True)
        stats_text.setFont(QFont("Monaco", 10))
        
        # Format statistics
        stats_info = f"【データ統計】\nデータ行数: {optimization_context['total_rows']:,}行\n\n"
        stats_dict = optimization_context.get('data_statistics', {})
        
        if stats_dict:
            # Revenue analysis
            revenue_analysis = stats_dict.get('revenue_analysis', {})
            if revenue_analysis:
                stats_info += "【収益分析】\n"
                for key, value in revenue_analysis.items():
                    if isinstance(value, (int, float)):
                        if 'revenue' in key.lower() or 'total' in key.lower():
                            stats_info += f"{key}: ¥{value:,.0f}\n"
                        else:
                            stats_info += f"{key}: {value:,}\n"
                    else:
                        stats_info += f"{key}: {value}\n"
                stats_info += "\n"
            
            # Date info
            date_info = stats_dict.get('date_info', {})
            if date_info:
                stats_info += "【期間情報】\n"
                for key, value in date_info.items():
                    stats_info += f"{key}: {value}\n"
                stats_info += "\n"
            
            # Action analysis
            action_analysis = stats_dict.get('action_analysis', {})
            if action_analysis:
                stats_info += "【アクション分析】\n"
                action_dist = action_analysis.get('action_distribution', {})
                for action, count in action_dist.items():
                    stats_info += f"{action}: {count:,}回\n"
                stats_info += f"最頻アクション: {action_analysis.get('most_common_action', '不明')}\n\n"
        
        stats_text.setPlainText(stats_info)
        stats_layout.addWidget(stats_text)
        tab_widget.addTab(stats_tab, "詳細統計")
        
        # Raw data sample tab
        raw_tab = QWidget()
        raw_layout = QVBoxLayout(raw_tab)
        raw_text = QPlainTextEdit()
        raw_text.setReadOnly(True)
        raw_text.setFont(QFont("Monaco", 9))
        
        # Show sample data
        sample_data = optimization_context.get('full_results_sample', [])
        raw_info = f"【生データサンプル（最新20行）】\n総データ行数: {optimization_context['total_rows']:,}行\n\n"
        
        if sample_data:
            # Show column headers
            if sample_data:
                headers = list(sample_data[0].keys())
                raw_info += "列: " + ", ".join(headers) + "\n\n"
                
                # Show sample rows
                for i, row in enumerate(sample_data[:10]):  # Show first 10 of the 20 samples
                    raw_info += f"行{len(all_results)-20+i+1}: "
                    row_data = []
                    for key, value in row.items():
                        if isinstance(value, float):
                            row_data.append(f"{key}={value:.2f}")
                        else:
                            row_data.append(f"{key}={value}")
                    raw_info += ", ".join(row_data) + "\n"
        
        raw_text.setPlainText(raw_info)
        raw_layout.addWidget(raw_text)
        tab_widget.addTab(raw_tab, "生データ")
        
        layout.addWidget(tab_widget)
        
        # Close button
        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        # Log debug access
        self.add_log_message("🔍 AI送信データデバッグダイアログを表示")
        
        dialog.exec()
        
    def create_wheeling_data_tab(self):
        """Create wheeling data management tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Title and controls
        title_layout = QHBoxLayout()
        title = QLabel("託送料金・損失率データ管理")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333; margin-bottom: 10px;")
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        # Control buttons
        refresh_btn = QPushButton("🔄 データ再読み込み")
        refresh_btn.clicked.connect(self.refresh_wheeling_data)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #17A2B8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        title_layout.addWidget(refresh_btn)
        
        reset_btn = QPushButton("🔧 デフォルト復元")
        reset_btn.clicked.connect(self.reset_wheeling_data)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFC107;
                color: #212529;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E0A800;
            }
        """)
        title_layout.addWidget(reset_btn)
        
        save_btn = QPushButton("💾 変更保存")
        save_btn.clicked.connect(self.save_wheeling_data)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        title_layout.addWidget(save_btn)
        
        layout.addLayout(title_layout)
        
        # Separator
        layout.addWidget(self.create_separator())
        
        # Information panel
        info_layout = QHBoxLayout()
        
        # Renewable energy surcharge
        surcharge_group = QGroupBox("再エネ賦課金")
        surcharge_layout = QVBoxLayout(surcharge_group)
        
        surcharge_info = QLabel("全国一律: 3.49円/kWh")
        surcharge_info.setStyleSheet("font-size: 14px; color: #666;")
        surcharge_layout.addWidget(surcharge_info)
        
        # Make it editable
        self.surcharge_input = QDoubleSpinBox()
        self.surcharge_input.setRange(0.0, 10.0)
        self.surcharge_input.setValue(3.49)
        self.surcharge_input.setSuffix(" 円/kWh")
        self.surcharge_input.setDecimals(2)
        surcharge_layout.addWidget(self.surcharge_input)
        
        info_layout.addWidget(surcharge_group)
        
        # Usage instructions
        usage_group = QGroupBox("使用方法")
        usage_layout = QVBoxLayout(usage_group)
        
        usage_text = QLabel("""
• 表中の値をダブルクリックで編集
• 変更後は「💾 変更保存」で反映
• 「🔧 デフォルト復元」で初期値に戻す
• 「🔄 データ再読み込み」で最新データ取得
        """)
        usage_text.setStyleSheet("font-size: 12px; color: #666;")
        usage_layout.addWidget(usage_text)
        
        info_layout.addWidget(usage_group)
        
        layout.addLayout(info_layout)
        
        # Create table for wheeling data
        self.wheeling_table = QTableWidget()
        self.wheeling_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.wheeling_table.setAlternatingRowColors(True)
        self.wheeling_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Setup table headers
        self.setup_wheeling_table()
        
        layout.addWidget(self.wheeling_table)
        
        # Status information
        status_layout = QHBoxLayout()
        self.wheeling_status_label = QLabel("データ読み込み済み")
        self.wheeling_status_label.setStyleSheet("color: #28A745; font-weight: bold;")
        status_layout.addWidget(self.wheeling_status_label)
        
        status_layout.addStretch()
        
        modified_label = QLabel("※ 変更は「💾 変更保存」で反映されます")
        modified_label.setStyleSheet("color: #666; font-size: 11px;")
        status_layout.addWidget(modified_label)
        
        layout.addLayout(status_layout)
        
        return tab
        
    def setup_wheeling_table(self):
        """Setup the wheeling data table"""
        from config.area_config import WHEELING_DATA, AREA_NUMBER_TO_NAME, VOLTAGE_TYPES
        
        # Column headers
        headers = [
            "エリア", "電圧区分", "電圧区分名", 
            "損失率 (%)", "託送基本料金 (円/kW)", "託送使用料 (円/kWh)"
        ]
        
        # Calculate total rows
        total_rows = len(AREA_NUMBER_TO_NAME) * len(VOLTAGE_TYPES)
        
        self.wheeling_table.setRowCount(total_rows)
        self.wheeling_table.setColumnCount(len(headers))
        self.wheeling_table.setHorizontalHeaderLabels(headers)
        
        # Populate data
        row = 0
        for area_num, area_name in AREA_NUMBER_TO_NAME.items():
            for voltage_code, voltage_desc in VOLTAGE_TYPES.items():
                # Get data for this area/voltage combination
                area_data = WHEELING_DATA["areas"].get(area_name, {})
                voltage_data = area_data.get(voltage_code, {})
                
                # Area
                area_item = QTableWidgetItem(f"{area_num}: {area_name}")
                area_item.setFlags(area_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Read-only
                area_item.setBackground(Qt.GlobalColor.lightGray)
                self.wheeling_table.setItem(row, 0, area_item)
                
                # Voltage code
                voltage_item = QTableWidgetItem(voltage_code)
                voltage_item.setFlags(voltage_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Read-only
                voltage_item.setBackground(Qt.GlobalColor.lightGray)
                self.wheeling_table.setItem(row, 1, voltage_item)
                
                # Voltage description
                desc_item = QTableWidgetItem(voltage_desc)
                desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Read-only
                desc_item.setBackground(Qt.GlobalColor.lightGray)
                self.wheeling_table.setItem(row, 2, desc_item)
                
                # Loss rate (editable)
                loss_rate = voltage_data.get("loss_rate", 0.0)
                loss_item = QTableWidgetItem(f"{loss_rate * 100:.3f}")
                loss_item.setToolTip("損失率（パーセント）- ダブルクリックで編集")
                self.wheeling_table.setItem(row, 3, loss_item)
                
                # Wheeling base charge (editable)
                base_charge = voltage_data.get("wheeling_base_charge", 0.0)
                base_item = QTableWidgetItem(f"{base_charge:.2f}")
                base_item.setToolTip("託送基本料金（円/kW）- ダブルクリックで編集")
                self.wheeling_table.setItem(row, 4, base_item)
                
                # Wheeling usage fee (editable)
                usage_fee = voltage_data.get("wheeling_usage_fee", 0.0)
                usage_item = QTableWidgetItem(f"{usage_fee:.2f}")
                usage_item.setToolTip("託送使用料（円/kWh）- ダブルクリックで編集")
                self.wheeling_table.setItem(row, 5, usage_item)
                
                row += 1
        
        # Resize columns to content
        self.wheeling_table.resizeColumnsToContents()
        
        # Set minimum column widths
        self.wheeling_table.setColumnWidth(0, 120)  # Area
        self.wheeling_table.setColumnWidth(1, 80)   # Voltage code
        self.wheeling_table.setColumnWidth(2, 200)  # Voltage description
        self.wheeling_table.setColumnWidth(3, 100)  # Loss rate
        self.wheeling_table.setColumnWidth(4, 150)  # Base charge
        self.wheeling_table.setColumnWidth(5, 150)  # Usage fee
        
        self.add_log_message("📊 託送料金・損失率データテーブルを設定しました")
        
    def refresh_wheeling_data(self):
        """Refresh wheeling data from config"""
        try:
            # Reimport the config to get fresh data
            import importlib
            from config import area_config
            importlib.reload(area_config)
            
            # Refresh the table
            self.setup_wheeling_table()
            
            # Update surcharge
            self.surcharge_input.setValue(area_config.RENEWABLE_ENERGY_SURCHARGE)
            
            self.wheeling_status_label.setText("データ再読み込み完了")
            self.wheeling_status_label.setStyleSheet("color: #28A745; font-weight: bold;")
            self.add_log_message("🔄 託送料金・損失率データを再読み込みしました")
            
        except Exception as e:
            self.wheeling_status_label.setText(f"エラー: {str(e)}")
            self.wheeling_status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.add_log_message(f"❌ データ再読み込みエラー: {str(e)}")
            
    def reset_wheeling_data(self):
        """Reset wheeling data to defaults"""
        reply = QMessageBox.question(
            self, "デフォルト復元", 
            "託送料金・損失率データを初期値に戻しますか？\n\n未保存の変更は失われます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Reset to default values by reloading the original config
                self.setup_wheeling_table()
                self.surcharge_input.setValue(3.49)
                
                self.wheeling_status_label.setText("デフォルト値に復元しました")
                self.wheeling_status_label.setStyleSheet("color: #FFC107; font-weight: bold;")
                self.add_log_message("🔧 託送料金・損失率データをデフォルト値に復元しました")
                
            except Exception as e:
                self.wheeling_status_label.setText(f"復元エラー: {str(e)}")
                self.wheeling_status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
                self.add_log_message(f"❌ デフォルト復元エラー: {str(e)}")
                
    def save_wheeling_data(self):
        """Save modified wheeling data"""
        try:
            from config.area_config import AREA_NUMBER_TO_NAME, VOLTAGE_TYPES
            
            # Create new data structure
            new_wheeling_data = {"areas": {}}
            
            # Parse table data
            row = 0
            changes_made = 0
            
            for area_num, area_name in AREA_NUMBER_TO_NAME.items():
                new_wheeling_data["areas"][area_name] = {}
                
                for voltage_code, voltage_desc in VOLTAGE_TYPES.items():
                    try:
                        # Get values from table
                        loss_rate_text = self.wheeling_table.item(row, 3).text()
                        base_charge_text = self.wheeling_table.item(row, 4).text()
                        usage_fee_text = self.wheeling_table.item(row, 5).text()
                        
                        # Convert to numbers
                        loss_rate = float(loss_rate_text) / 100.0  # Convert from percentage
                        base_charge = float(base_charge_text)
                        usage_fee = float(usage_fee_text)
                        
                        # Validate ranges
                        if not (0 <= loss_rate <= 1):
                            raise ValueError(f"損失率は0-100%の範囲で入力してください (行{row+1})")
                        if base_charge < 0:
                            raise ValueError(f"託送基本料金は0以上で入力してください (行{row+1})")
                        if usage_fee < 0:
                            raise ValueError(f"託送使用料は0以上で入力してください (行{row+1})")
                        
                        # Store data
                        new_wheeling_data["areas"][area_name][voltage_code] = {
                            "loss_rate": loss_rate,
                            "wheeling_base_charge": base_charge,
                            "wheeling_usage_fee": usage_fee
                        }
                        
                        changes_made += 1
                        
                    except ValueError as e:
                        QMessageBox.critical(self, "入力エラー", str(e))
                        return
                        
                    row += 1
            
            # Update renewable energy surcharge
            new_surcharge = self.surcharge_input.value()
            
            # Save to temporary variable (in a real app, you'd save to file)
            self.modified_wheeling_data = new_wheeling_data
            self.modified_surcharge = new_surcharge
            
            self.wheeling_status_label.setText(f"変更保存完了 ({changes_made}項目)")
            self.wheeling_status_label.setStyleSheet("color: #28A745; font-weight: bold;")
            
            self.add_log_message(f"💾 託送料金・損失率データを保存しました ({changes_made}項目)")
            self.add_log_message(f"💾 再エネ賦課金: {new_surcharge}円/kWh")
            
            # Show confirmation dialog
            QMessageBox.information(
                self, "保存完了", 
                f"託送料金・損失率データの変更を保存しました。\n\n"
                f"• 更新項目数: {changes_made}\n"
                f"• 再エネ賦課金: {new_surcharge}円/kWh\n\n"
                f"※ 次回の最適化実行時から新しい値が使用されます。"
            )
            
        except Exception as e:
            self.wheeling_status_label.setText(f"保存エラー: {str(e)}")
            self.wheeling_status_label.setStyleSheet("color: #DC3545; font-weight: bold;")
            self.add_log_message(f"❌ 託送料金・損失率データ保存エラー: {str(e)}")
            QMessageBox.critical(self, "保存エラー", f"データの保存中にエラーが発生しました:\n\n{str(e)}")
            
    def get_current_wheeling_data(self):
        """Get current wheeling data (modified or default)"""
        if hasattr(self, 'modified_wheeling_data'):
            return self.modified_wheeling_data
        else:
            from config.area_config import WHEELING_DATA
            return WHEELING_DATA
            
    def get_current_surcharge(self):
        """Get current renewable energy surcharge"""
        if hasattr(self, 'modified_surcharge'):
            return self.modified_surcharge
        else:
            from config.area_config import RENEWABLE_ENERGY_SURCHARGE
            return RENEWABLE_ENERGY_SURCHARGE
    
    def select_start_date(self):
        """Open calendar dialog to select start date"""
        try:
            current_date = self.start_date_edit.date()
            dialog = CalendarDialog(self, title="開始日選択", current_date=current_date)
            
            # Set date range based on available data
            if hasattr(self, 'csv_data') and self.csv_data is not None:
                df_dates = pd.to_datetime(self.csv_data['date'])
                min_date = df_dates.min().date()
                max_date = df_dates.max().date()
                
                dialog.calendar.setMinimumDate(QDate(min_date))
                dialog.calendar.setMaximumDate(QDate(max_date))
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_date = dialog.get_selected_date()
                self.start_date_edit.setDate(selected_date)
                self.add_log_message(f"開始日をカレンダーから選択: {selected_date.toString('yyyy-MM-dd')}")
                
                # Auto-update visualization if in range mode
                if self.date_range_mode == "range" and self.optimization_results:
                    self.update_visualization()
                    
        except Exception as e:
            self.add_log_message(f"開始日選択エラー: {str(e)}")
            QMessageBox.warning(self, "カレンダーエラー", f"開始日の選択中にエラーが発生しました:\n{str(e)}")
    
    def select_end_date(self):
        """Open calendar dialog to select end date"""
        try:
            current_date = self.end_date_edit.date()
            dialog = CalendarDialog(self, title="終了日選択", current_date=current_date)
            
            # Set date range based on available data
            if hasattr(self, 'csv_data') and self.csv_data is not None:
                df_dates = pd.to_datetime(self.csv_data['date'])
                min_date = df_dates.min().date()
                max_date = df_dates.max().date()
                
                dialog.calendar.setMinimumDate(QDate(min_date))
                dialog.calendar.setMaximumDate(QDate(max_date))
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_date = dialog.get_selected_date()
                self.end_date_edit.setDate(selected_date)
                self.add_log_message(f"終了日をカレンダーから選択: {selected_date.toString('yyyy-MM-dd')}")
                
                # Auto-update visualization if in range mode
                if self.date_range_mode == "range" and self.optimization_results:
                    self.update_visualization()
                    
        except Exception as e:
            self.add_log_message(f"終了日選択エラー: {str(e)}")
            QMessageBox.warning(self, "カレンダーエラー", f"終了日の選択中にエラーが発生しました:\n{str(e)}")
    
    def show_quick_help(self):
        """Show quick help with sample questions"""
        sample_questions = [
            "最も収益の高い時間帯はいつですか？",
            "今回の最適化結果の総収益を教えてください",
            "どのアクション（充電・放電・調整力）が最も多く使われていますか？",
            "1日の平均収益はいくらですか？", 
            "最も利益が出た日はいつですか？",
            "EPRX1とEPRX3のどちらがより収益に貢献していますか？",
            "バッテリーの稼働率はどの程度ですか？",
            "アプリが起動しない場合の対処法を教えてください",
            "最適化が遅い場合の改善方法を教えてください",
            "CSVデータの正しい形式を教えてください"
        ]
        
        help_text = """
🤖 **AIサポートデスクへようこそ！**

以下のような質問ができます：

📊 **データ分析系の質問例**:
"""
        
        for i, question in enumerate(sample_questions[:6], 1):
            help_text += f"{i}. {question}\n"
        
        help_text += """
🔧 **トラブルシューティング系の質問例**:
"""
        
        for i, question in enumerate(sample_questions[6:], 7):
            help_text += f"{i}. {question}\n"
        
        help_text += """

💡 **Tips**:
• 最適化を実行後にデータ分析の質問ができます
• 具体的な数値や期間を含めて質問するとより詳細な回答が得られます
• トラブルが発生した場合は症状を詳しく説明してください

質問を入力して「送信」ボタンを押してください！
"""
        
        # Display help in chat
        self.display_chat_message("ヘルプ", help_text, is_user=False)
        
        # Also show as dialog for better visibility
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("AIサポートデスク - クイックヘルプ")
        help_dialog.setModal(True)
        help_dialog.resize(600, 500)
        
        layout = QVBoxLayout(help_dialog)
        
        help_display = QTextEdit()
        help_display.setReadOnly(True)
        help_display.setPlainText(help_text)
        help_display.setFont(QFont("システムフォント", 11))
        layout.addWidget(help_display)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(help_dialog.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        help_dialog.exec()