# Battery Optimizer GUI 2.0

PyQt6-based desktop application for battery storage optimization in Japanese electricity markets (JEPX, EPRX1, EPRX3).

## 🚀 Features

- **Native Desktop Application**: Professional macOS/Windows/Linux desktop app with PyQt6
- **Real-time Optimization**: Live progress updates during optimization process
- **Advanced Visualization**: Interactive charts and graphs using matplotlib
- **Multi-market Support**: JEPX spot market and EPRX1/EPRX3 adjustment markets
- **9-Area Coverage**: All Japanese power areas with accurate wheeling fees
- **Professional UI**: Native look and feel with dark mode support on macOS

## 📋 Requirements

- Python 3.8 or higher
- macOS 10.14+ (recommended), Windows 10+, or Linux
- 4GB RAM minimum, 8GB recommended for large datasets

## 🛠 Installation

### Option 1: Automatic Setup (Recommended)

```bash
cd battery_optimizer_gui
python setup.py
```

This will automatically:
- Install all dependencies
- Check CBC solver functionality
- Fix common macOS permission issues
- Create a launcher script

### Option 2: Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For macOS users, also install CBC via Homebrew (if issues occur)
brew install cbc
```

## 🏃‍♂️ Running the Application

### Using the launcher script:
```bash
python run_battery_optimizer.py
```

### Direct execution:
```bash
python -m battery_optimizer_gui.main
```

### From battery_optimizer_gui directory:
```bash
python main.py
```

## 📱 Usage Guide

### 1. **Set Parameters**
   - Select target area (1-9: Hokkaido to Kyushu)
   - Choose voltage class (SHV/HV/LV)
   - Configure battery specifications (power, capacity, loss rate)
   - Adjust advanced settings (cycle limits, EPRX parameters)

### 2. **Load Data**
   - Click "CSVファイルを選択..." to load price data
   - Use "CSVテンプレートをダウンロード" for the correct format
   - Required columns: date, slot, JEPX_prediction, JEPX_actual, EPRX1_prediction, EPRX1_actual, EPRX3_prediction, EPRX3_actual, imbalance

### 3. **Run Optimization**
   - Click "最適化を実行" to start the process
   - Monitor real-time progress and status updates
   - View results in multiple tabs (graphs, detailed data, summary)

### 4. **Analyze Results**
   - **グラフ**: Interactive visualizations of battery operation and prices
   - **詳細データ**: Complete transaction data in table format
   - **サマリー**: Financial summary with total profit/loss breakdown

### 5. **Export Results**
   - Save results as CSV files
   - Export graphs as images
   - Generate reports for stakeholders

## 📊 CSV Data Format

The application expects CSV files with the following columns:

| Column | Description | Unit |
|--------|-------------|------|
| date | Date (YYYY-MM-DD) | - |
| slot | Time slot (1-48) | - |
| JEPX_prediction | JEPX predicted price | ¥/kWh |
| JEPX_actual | JEPX actual price | ¥/kWh |
| EPRX1_prediction | EPRX1 predicted price | ¥/kW |
| EPRX1_actual | EPRX1 actual price | ¥/kW |
| EPRX3_prediction | EPRX3 predicted price | ¥/kW |
| EPRX3_actual | EPRX3 actual price | ¥/kW |
| imbalance | Imbalance price | ¥/kWh |

Download the template from within the application for the exact format.

## ⚙️ Configuration

### Battery Parameters
- **Power (kW)**: Maximum charge/discharge rate
- **Capacity (kWh)**: Total battery storage capacity
- **Loss Rate (%)**: Round-trip efficiency loss

### Market Parameters
- **Daily Cycle Limit**: Maximum daily charge/discharge cycles
- **Forecast Period**: Number of slots to optimize simultaneously (24-168)
- **EPRX1 Settings**: Block size and cooldown periods
- **Regional Settings**: Automatic wheeling fees and loss rates

## 🔧 Troubleshooting

### CBC Solver Issues (macOS)
If you encounter CBC solver problems:

1. **Try the automatic fix:**
   ```bash
   python setup.py
   ```

2. **Manual fix via Homebrew:**
   ```bash
   brew install cbc
   ```

3. **Alternative solver:**
   The application can fall back to other solvers if CBC fails.

### Performance Issues
- For datasets >10,000 slots, consider reducing forecast period
- Close other applications to free up memory
- Use SSD storage for better I/O performance

### GUI Issues on macOS
- Ensure you're using Python 3.8+ 
- Update to latest PyQt6 version
- Enable Retina display support in system preferences

## 📁 Project Structure

```
battery_optimizer_gui/
├── __init__.py              # Package metadata
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── setup.py                 # Installation and setup script
├── README.md               # This file
├── run_battery_optimizer.py # Launcher script (created by setup)
├── core/
│   ├── __init__.py
│   └── optimization_engine.py  # Core optimization logic
├── config/
│   ├── __init__.py
│   └── area_config.py          # Regional configuration data
└── gui/
    ├── __init__.py
    └── main_window.py          # Main application window
```

## 🔄 Migration from Streamlit Version

This PyQt6 version provides all features from the original Streamlit application plus:

- **Better Performance**: Native desktop performance vs. web browser
- **Offline Operation**: No need for web server or internet connection
- **Professional UI**: Native OS integration and appearance
- **Advanced Features**: Multi-threading, progress monitoring, enhanced visualization
- **Data Security**: All processing happens locally

To migrate your data:
1. Export CSV results from Streamlit version
2. Use the same CSV format in this PyQt6 version
3. Parameters should transfer directly

## 🆘 Support

For technical support or feature requests:

1. **Check the logs**: View the log panel in the application for error details
2. **Verify CBC solver**: Run `python setup.py` to diagnose issues
3. **Update dependencies**: `pip install -r requirements.txt --upgrade`
4. **Contact support**: Include log files and system information

## 📄 License

See the main project LICENSE file.

## 🔄 Version History

- **2.0.0**: Initial PyQt6 desktop version
  - Complete UI rewrite with PyQt6
  - Native macOS/Windows/Linux support
  - Real-time progress monitoring
  - Enhanced visualization capabilities
  - Professional desktop application experience

---

**© 2024 Factlabel** | Built with PyQt6, PuLP, and matplotlib 