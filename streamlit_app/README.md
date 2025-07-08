# Battery Optimizer - Streamlit版

Web-based Battery Storage Optimization System

このディレクトリには、Streamlitを使用したWebアプリケーション版のBattery Optimizerが含まれています。

## セットアップ手順

### 1. セットアップ
```bash
# このディレクトリに移動
cd streamlit_app

# 依存関係のインストール
pip install -r requirements.txt
```

### 2. アプリケーション起動
```bash
streamlit run main.py
```

ブラウザで `http://localhost:8501` にアクセス

## ディレクトリ構造

```
streamlit_app/
├── main.py              # メインアプリケーション
├── requirements.txt     # Python依存関係
├── src/                 # ソースコード
│   ├── __init__.py
│   ├── optimization.py  # 最適化エンジン
│   └── config.py        # エリア設定データ
├── assets/              # リソース
│   ├── images/
│   │   └── LOGO_factlabel.png
│   └── csv_template_sample.csv
└── docs/                # ドキュメント
    ├── hands_on_guide.md
    └── user_manual.md
```

## 主な特徴

- **容易な導入**: ブラウザですぐに利用開始
- **直感的UI**: Streamlitのシンプルなインターフェース
- **リアルタイム**: パラメータ変更時の即座更新
- **軽量**: 最小限の依存関係

## 機能概要

### 基本機能
- バッテリー最適化計算
- 全9エリア対応（北海道〜九州）
- JEPX・EPRX1・EPRX3市場対応
- CSV入出力

### 可視化
- バッテリー残量推移グラフ
- 価格チャート
- 収益サマリー表示

### 設定項目
- バッテリー仕様（出力・容量・損失率）
- エリア・電圧区分選択
- 市場参加設定

## 利用シーン

### 適している用途
- **プロトタイピング**: 新しいアイデアの検証
- **デモンストレーション**: 関係者への機能説明
- **学習・研究**: アルゴリズムの理解・検証
- **クイック分析**: 簡単な計算とチェック

### 制限事項
- **パフォーマンス**: 大規模データでは処理が重い
- **UI制約**: Streamlitの基本機能に限定
- **プロダクション**: 本格運用には不向き

## システム要件

- **Python**: 3.8以上
- **RAM**: 最小2GB、推奨4GB以上
- **ブラウザ**: Chrome, Firefox, Safari, Edge

## 次のステップ

より高度な機能が必要な場合は、**PyQt6版（Desktop App）**をご検討ください：

```bash
cd ../desktop_app/battery_optimizer_gui
python setup.py
python run_battery_optimizer.py
```

## 詳細ドキュメント

- **[ユーザーマニュアル](docs/user_manual.md)**: 詳細な使用方法
- **[ハンズオンガイド](docs/hands_on_guide.md)**: ステップバイステップガイド
- **[計算仕様書](../shared/calculation_overview.md)**: アルゴリズム詳細

## サポート

### よくある問題

1. **Streamlit起動エラー**
   ```bash
   pip install streamlit --upgrade
   streamlit --version
   ```

2. **CBC solver エラー (macOS)**
   ```bash
   brew install cbc
   ```

3. **パッケージエラー**
   ```bash
   pip install -r requirements.txt --upgrade
   ```

---

**[メインプロジェクト](../README.md)に戻る** 