# Battery Optimizer GUI

PyQt6-based desktop application for battery storage optimization in Japanese electricity markets.

## Features

- Native desktop application with PyQt6
- Real-time optimization with progress updates
- Multi-market support (JEPX, EPRX1, EPRX3)
- All 9 Japanese power areas with accurate wheeling fees
- AI analysis integration with GPT-4o
- Professional UI with dark mode support

## Requirements

- Python 3.8 or higher
- macOS 10.14+, Windows 10+, or Linux
- 4GB RAM minimum, 8GB recommended

## Installation & Setup

### Automatic Setup (Recommended)
```bash
./start_app.sh
```

### Manual Installation
```bash
pip install -r requirements.txt
python setup.py
```

## Running the Application

```bash
python main.py
```

## Usage

1. **Configure Parameters**: Set battery specifications and market settings
2. **Load Data**: Import CSV price data (use template for format)
3. **Run Optimization**: Execute optimization and monitor progress
4. **Analyze Results**: View graphs, detailed data, and AI analysis

## CSV Data Format

Required columns: `date`, `slot`, `JEPX_prediction`, `JEPX_actual`, `EPRX1_prediction`, `EPRX1_actual`, `EPRX3_prediction`, `EPRX3_actual`, `imbalance`

## Key Features

- **6 Tabs**: Graphs, Revenue Details, Data, Summary, AI Chat, Wheeling Fees
- **AI Integration**: GPT-4o analysis and reporting
- **Date Filtering**: Period selection for focused analysis
- **Export Options**: CSV results and graph exports

## Troubleshooting

### CBC Solver Issues (macOS)
```bash
brew install cbc
# or
python setup.py
```

### Performance Issues
- Reduce forecast period for large datasets
- Use SSD storage for better performance
- Close other applications to free memory

## Project Structure

```
battery_optimizer_gui/
├── main.py                     # Application entry point
├── start_app.sh               # One-click launcher
├── requirements.txt           # Dependencies
├── setup.py                   # Setup script
├── core/
│   └── optimization_engine.py # Core logic
├── gui/
│   └── main_window.py         # Main UI
└── config/
    └── area_config.py         # Regional data
```

## Migration from Streamlit

The PyQt6 version provides enhanced performance, offline operation, and professional UI compared to the Streamlit version while maintaining full compatibility with existing data formats.

## Support

For technical issues:
1. Check application logs
2. Run `python setup.py` for diagnostics
3. Update dependencies: `pip install -r requirements.txt --upgrade`

## License

See main project LICENSE file. 