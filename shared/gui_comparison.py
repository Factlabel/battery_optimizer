# macOS GUI Framework Comparison
# バッテリー最適化アプリのメイン画面サンプル

# ============================================
# Option 1: CustomTkinter (macOS での制限あり)
# ============================================

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class BatteryOptimizerTkinter:
    def __init__(self):
        # macOS での問題: フォント、スケーリング、ダークモード対応
        ctk.set_appearance_mode("auto")  # macOS ダークモード連動（不完全）
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("Battery Optimizer - CustomTkinter")
        self.root.geometry("1200x800")
        
        # macOS での問題: Retina ディスプレイでのスケーリング
        self.setup_ui()
    
    def setup_ui(self):
        # メインフレーム
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # パラメータ設定エリア
        params_frame = ctk.CTkFrame(main_frame)
        params_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(params_frame, text="基本パラメータ設定", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # エリア選択
        self.area_var = ctk.StringVar(value="3: Tokyo")
        area_menu = ctk.CTkOptionMenu(params_frame, variable=self.area_var,
                                     values=["1: Hokkaido", "2: Tohoku", "3: Tokyo"])
        area_menu.pack(pady=5)
        
        # バッテリー設定
        battery_frame = ctk.CTkFrame(params_frame)
        battery_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(battery_frame, text="バッテリー出力(kW)").pack(side="left")
        self.power_entry = ctk.CTkEntry(battery_frame, placeholder_text="1000")
        self.power_entry.pack(side="right", padx=10)
        
        # ファイルアップロード
        upload_frame = ctk.CTkFrame(main_frame)
        upload_frame.pack(fill="x", padx=10, pady=10)
        
        upload_btn = ctk.CTkButton(upload_frame, text="CSVファイル選択", 
                                  command=self.select_file)
        upload_btn.pack(pady=10)
        
        # 計算実行
        calc_btn = ctk.CTkButton(main_frame, text="最適化実行", 
                                command=self.run_optimization,
                                height=40, font=ctk.CTkFont(size=16))
        calc_btn.pack(pady=20)
        
        # グラフエリア（matplotlib 統合での問題）
        self.setup_graph_area(main_frame)
    
    def setup_graph_area(self, parent):
        # macOS での問題: matplotlib との統合でレンダリング問題
        graph_frame = ctk.CTkFrame(parent)
        graph_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
        canvas = FigureCanvasTkAgg(fig, graph_frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def select_file(self):
        # macOS での問題: ネイティブファイルダイアログとの見た目の違い
        filename = filedialog.askopenfilename(
            title="CSVファイルを選択",
            filetypes=[("CSV files", "*.csv")]
        )
        print(f"Selected: {filename}")
    
    def run_optimization(self):
        print("最適化実行中...")

# ============================================
# Option 2: PyQt6 (macOS 最適化)
# ============================================

import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                           QHBoxLayout, QWidget, QPushButton, QLabel, 
                           QComboBox, QLineEdit, QFileDialog, QFrame,
                           QSplitter, QTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class OptimizationThread(QThread):
    """非同期で最適化処理を実行"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int)
    
    def run(self):
        # 実際の最適化処理をここに実装
        for i in range(101):
            self.progress.emit(i)
            self.msleep(50)  # 50ms待機
        
        # 結果を返す
        result = {"status": "success", "data": "optimization_result"}
        self.finished.emit(result)

class BatteryOptimizerPyQt6(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Battery Optimizer - PyQt6")
        self.setGeometry(100, 100, 1400, 900)
        
        # macOS の利点: 自動的にネイティブな見た目、ダークモード対応
        self.setup_ui()
        self.setup_menubar()  # macOS ネイティブメニューバー
        
    def setup_menubar(self):
        """macOS ネイティブメニューバーの設定"""
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu('ファイル')
        file_menu.addAction('CSV読み込み', self.select_file)
        file_menu.addAction('結果保存', self.save_results)
        file_menu.addSeparator()
        file_menu.addAction('終了', self.close)
        
        # 表示メニュー
        view_menu = menubar.addMenu('表示')
        view_menu.addAction('ダークモード切替', self.toggle_theme)
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # 左パネル: パラメータ設定
        left_panel = self.create_parameter_panel()
        
        # 右パネル: グラフ・結果表示
        right_panel = self.create_results_panel()
        
        # スプリッター（サイズ調整可能）
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 1000])  # 初期サイズ比
        
        main_layout.addWidget(splitter)
    
    def create_parameter_panel(self):
        """パラメータ設定パネル"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMaximumWidth(450)
        
        layout = QVBoxLayout(panel)
        
        # タイトル
        title = QLabel("基本パラメータ設定")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # エリア選択
        layout.addWidget(QLabel("対象エリア:"))
        self.area_combo = QComboBox()
        self.area_combo.addItems([
            "1: 北海道", "2: 東北", "3: 東京", "4: 中部", 
            "5: 北陸", "6: 関西", "7: 中国", "8: 四国", "9: 九州"
        ])
        self.area_combo.setCurrentIndex(2)  # 東京をデフォルト
        layout.addWidget(self.area_combo)
        
        # 電圧区分
        layout.addWidget(QLabel("電圧区分:"))
        self.voltage_combo = QComboBox()
        self.voltage_combo.addItems(["SHV", "HV", "LV"])
        self.voltage_combo.setCurrentIndex(1)  # HVをデフォルト
        layout.addWidget(self.voltage_combo)
        
        # バッテリー設定
        battery_group = self.create_battery_settings()
        layout.addWidget(battery_group)
        
        # ファイル選択
        file_layout = QHBoxLayout()
        self.file_label = QLabel("ファイル未選択")
        self.file_button = QPushButton("CSV選択")
        self.file_button.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_button)
        layout.addLayout(file_layout)
        
        # 実行ボタン
        self.run_button = QPushButton("最適化実行")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056CC;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
        """)
        self.run_button.clicked.connect(self.run_optimization)
        layout.addWidget(self.run_button)
        
        # ログ表示エリア
        layout.addWidget(QLabel("実行ログ:"))
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        layout.addStretch()  # 余白を下に追加
        return panel
    
    def create_battery_settings(self):
        """バッテリー設定グループ"""
        group = QFrame()
        group.setFrameStyle(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout(group)
        
        # バッテリー出力
        power_layout = QHBoxLayout()
        power_layout.addWidget(QLabel("出力(kW):"))
        self.power_input = QLineEdit("1000")
        power_layout.addWidget(self.power_input)
        layout.addLayout(power_layout)
        
        # バッテリー容量
        capacity_layout = QHBoxLayout()
        capacity_layout.addWidget(QLabel("容量(kWh):"))
        self.capacity_input = QLineEdit("4000")
        capacity_layout.addWidget(self.capacity_input)
        layout.addLayout(capacity_layout)
        
        # 損失率
        loss_layout = QHBoxLayout()
        loss_layout.addWidget(QLabel("損失率:"))
        self.loss_input = QLineEdit("0.05")
        loss_layout.addWidget(self.loss_input)
        layout.addLayout(loss_layout)
        
        return group
    
    def create_results_panel(self):
        """結果表示パネル"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # グラフエリア
        self.figure = Figure(figsize=(12, 8))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # macOS の利点: 高解像度グラフの完全対応
        self.canvas.setStyleSheet("background-color: white;")
        
        return panel
    
    def select_file(self):
        """ファイル選択（macOS ネイティブダイアログ）"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "CSVファイルを選択", 
            "", 
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if filename:
            self.file_label.setText(f"選択: {filename.split('/')[-1]}")
            self.log_text.append(f"ファイル選択: {filename}")
    
    def run_optimization(self):
        """最適化実行（非同期処理）"""
        self.run_button.setEnabled(False)
        self.run_button.setText("実行中...")
        self.log_text.append("最適化処理を開始...")
        
        # 非同期で処理実行
        self.optimization_thread = OptimizationThread()
        self.optimization_thread.progress.connect(self.update_progress)
        self.optimization_thread.finished.connect(self.on_optimization_finished)
        self.optimization_thread.start()
    
    def update_progress(self, value):
        """進捗更新"""
        self.log_text.append(f"進捗: {value}%")
    
    def on_optimization_finished(self, result):
        """最適化完了時の処理"""
        self.run_button.setEnabled(True)
        self.run_button.setText("最適化実行")
        self.log_text.append("最適化処理完了!")
        
        # 結果をグラフ表示
        self.update_graph()
    
    def update_graph(self):
        """グラフ更新"""
        self.figure.clear()
        
        # サンプルデータでグラフ作成
        ax1 = self.figure.add_subplot(211)
        ax2 = self.figure.add_subplot(212)
        
        # バッテリー残量
        import numpy as np
        x = np.linspace(0, 48, 48)
        battery_level = 50 + 30 * np.sin(x * 0.3)
        ax1.bar(x, battery_level, color='lightblue', alpha=0.7)
        ax1.set_title('バッテリー残量 (kWh)')
        ax1.set_ylabel('kWh')
        
        # 価格推移
        price = 20 + 10 * np.sin(x * 0.5) + 5 * np.random.random(48)
        ax2.plot(x, price, color='red', linewidth=2)
        ax2.set_title('JEPX価格 (円/kWh)')
        ax2.set_ylabel('円/kWh')
        ax2.set_xlabel('スロット')
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def save_results(self):
        """結果保存"""
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "結果を保存", 
            "optimization_results.csv", 
            "CSV Files (*.csv)"
        )
        if filename:
            self.log_text.append(f"結果保存: {filename}")
    
    def toggle_theme(self):
        """テーマ切り替え（macOS ダークモード対応）"""
        app = QApplication.instance()
        palette = app.palette()
        
        # macOS ダークモードの状態を取得して切り替え
        # 実装は省略（システム設定に従う）
        pass

def run_tkinter_app():
    """CustomTkinter版の実行"""
    app = BatteryOptimizerTkinter()
    app.root.mainloop()

def run_pyqt6_app():
    """PyQt6版の実行"""
    app = QApplication(sys.argv)
    
    # macOS の利点: 自動的にシステム設定（ダークモード等）を反映
    app.setStyle('Fusion')  # より美しい見た目
    
    window = BatteryOptimizerPyQt6()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    # どちらかを選択して実行
    print("Choose GUI framework:")
    print("1. CustomTkinter (macOS compatibility issues)")
    print("2. PyQt6 (Recommended for macOS)")
    
    choice = input("Enter choice (1 or 2): ")
    
    if choice == "1":
        run_tkinter_app()
    else:
        run_pyqt6_app() 