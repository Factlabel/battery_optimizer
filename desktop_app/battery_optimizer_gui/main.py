#!/usr/bin/env python3
"""
Battery Optimizer GUI Application - Main Entry Point

PyQt6-based desktop application for battery storage optimization
in Japanese electricity markets.

Usage:
    python main.py

Author: Factlabel
Version: 2.0.0
"""

import sys
import os
from pathlib import Path

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtCore import QSettings, QCoreApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

# Use absolute imports for standalone execution
from gui.main_window import BatteryOptimizerMainWindow

# Application metadata (define locally to avoid import issues)
APP_NAME = "Battery Optimizer"
APP_VERSION = "2.0.0"
APP_ORGANIZATION = "Factlabel"
APP_DOMAIN = "factlabel.com"

def setup_application():
    """Setup QApplication with proper configuration for macOS"""
    app = QApplication(sys.argv)
    
    # Application metadata
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setOrganizationDomain(APP_DOMAIN)
    
    # macOS specific settings
    if sys.platform == "darwin":  # macOS
        app.setStyle('Fusion')  # Better looking style
    
    return app

def main():
    """Main application entry point"""
    try:
        # Setup application
        app = setup_application()
        
        # Check for required dependencies
        try:
            import pandas
            import numpy
            import matplotlib
            import pulp
        except ImportError as e:
            QMessageBox.critical(
                None, 
                "依存関係エラー", 
                f"必要なライブラリが見つかりません:\n{e}\n\n"
                "requirements.txtを使用してインストールしてください:\n"
                "pip install -r requirements.txt"
            )
            return 1
        
        # Create and show main window
        main_window = BatteryOptimizerMainWindow()
        main_window.show()
        
        # Start application event loop
        return app.exec()
        
    except Exception as e:
        # Handle any unexpected errors
        print(f"Application error: {e}")
        if 'app' in locals():
            QMessageBox.critical(
                None,
                "アプリケーションエラー",
                f"予期しないエラーが発生しました:\n{e}"
            )
        return 1

if __name__ == "__main__":
    sys.exit(main()) 