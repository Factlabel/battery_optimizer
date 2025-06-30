#!/bin/bash

# Battery Optimizer Desktop App - One-Click Launch Script
# バッテリー最適化デスクトップアプリ - ワンクリック起動スクリプト

echo "🚀 Battery Optimizer Desktop App Starting..."
echo "バッテリー最適化デスクトップアプリを起動しています..."
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📂 Working Directory: $SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚙️  Creating virtual environment..."
    echo "仮想環境を作成しています..."
    python3 -m venv venv
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        echo "仮想環境の作成に失敗しました"
        exit 1
    fi
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
echo "仮想環境をアクティベートしています..."
source venv/bin/activate

# Check if dependencies are installed
if [ ! -f "venv/lib/python*/site-packages/PyQt6/__init__.py" ]; then
    echo "📦 Installing dependencies..."
    echo "依存関係をインストールしています..."
    pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        echo "依存関係のインストールに失敗しました"
        exit 1
    fi
fi

# Launch the application
echo "🎯 Launching Battery Optimizer..."
echo "バッテリー最適化アプリを起動しています..."
echo ""
echo "💡 Tips / ヒント:"
echo "   - Load CSV data using 'CSV読み込み' button"
echo "   - CSVデータを'CSV読み込み'ボタンで読み込んでください"
echo "   - Configure parameters and click '最適化実行'"
echo "   - パラメータを設定して'最適化実行'をクリックしてください"
echo "   - View results in the 'グラフ' tab with new date range selection"
echo "   - '結果タブ'で新しい期間選択機能付きのグラフを確認してください"
echo ""

# Start the application
python main.py

# Check if the application started successfully
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Application closed successfully"
    echo "アプリケーションが正常に終了しました"
else
    echo ""
    echo "❌ Application encountered an error"
    echo "アプリケーションでエラーが発生しました"
    echo ""
    echo "🔍 Troubleshooting / トラブルシューティング:"
    echo "   1. Check Python version: python3 --version"
    echo "   2. Ensure you have GUI support (macOS: XQuartz might be needed)"
    echo "   3. Try running manually: source venv/bin/activate && python main.py"
    echo ""
    read -p "Press Enter to close / Enterキーで終了..."
fi 