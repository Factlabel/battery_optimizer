# Battery Optimizer Project

バッテリー蓄電最適化システム - 日本電力市場（JEPX、EPRX1、EPRX3）対応

## 📁 プロジェクト構造

このリポジトリには、Battery Optimizerの2つのバージョンが含まれています：

```
battery_optimizer_pilot/
├── streamlit_app/          # 🌐 Streamlit版 (Web App)
│   ├── main.py            # メインアプリケーション
│   ├── src/               # 最適化ロジック
│   ├── assets/            # CSVテンプレート・画像
│   ├── docs/              # ユーザーマニュアル
│   └── requirements.txt   # 依存関係
├── desktop_app/           # 🖥️ PyQt6版 (Desktop App)
│   └── battery_optimizer_gui/
│       ├── main.py        # デスクトップアプリ起動点
│       ├── core/          # 最適化エンジン
│       ├── gui/           # ユーザーインターフェース
│       ├── config/        # 設定・エリアデータ
│       └── requirements.txt
└── shared/                # 📚 共通資料
    ├── README.md          # 詳細プロジェクト説明
    ├── LICENSE            # ライセンス
    ├── calculation_overview.md  # 計算仕様書
    ├── migration_plan.md  # 移行計画
    └── gui_comparison.py  # GUI比較デモ
```

## 🚀 クイックスタート

### 🌐 Streamlit版 (推奨: 初回利用・デモ)

```bash
cd streamlit_app
pip install -r requirements.txt
streamlit run main.py
```

**特徴:**
- ブラウザベースの簡単なインターフェース
- 迅速なプロトタイピング・検証
- 軽量で導入が簡単

### 🖥️ PyQt6版 (推奨: プロダクション利用)

```bash
cd desktop_app/battery_optimizer_gui
python setup.py  # 自動セットアップ
python run_battery_optimizer.py
```

**特徴:**
- ネイティブデスクトップアプリケーション
- 高速処理・リアルタイム進捗表示
- プロフェッショナルUI・オフライン動作

## 📊 機能比較

| 機能 | Streamlit版 | PyQt6版 |
|------|-------------|---------|
| **UI/UX** | Web基本UI | ネイティブデスクトップ |
| **パフォーマンス** | 中程度 | 高速 |
| **リアルタイム進捗** | ❌ | ✅ |
| **導入の簡単さ** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **プロダクション利用** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **データセキュリティ** | サーバー経由 | 完全ローカル |
| **オフライン動作** | ❌ | ✅ |
| **ファイル操作** | ブラウザ制限 | ネイティブ統合 |

## 🎯 利用用途別推奨

### 🔬 **研究・検証・デモ** → Streamlit版
- 素早いプロトタイピング
- 関係者への機能説明
- 初期検証・テスト

### 🏢 **業務・プロダクション** → PyQt6版
- 日常的な最適化業務
- 大規模データ処理
- セキュアな環境での運用

## 📋 共通仕様

両バージョンとも以下の機能を提供：

### 🔧 **最適化機能**
- **市場対応**: JEPX現物、EPRX1/EPRX3調整力
- **エリア対応**: 日本全国9エリア（北海道〜九州）
- **電圧区分**: 特高圧・高圧・低圧
- **制約条件**: サイクル制限、EPRX1ブロック制約

### 📊 **入出力**
- **入力**: CSV形式の価格データ
- **出力**: 最適化結果、収益サマリー
- **可視化**: バッテリー動作チャート、価格グラフ

### ⚙️ **パラメータ設定**
- バッテリー仕様（出力・容量・損失率）
- 市場参加設定
- 地域別託送料金自動計算

## 📚 詳細ドキュメント

- **[詳細README](shared/README.md)**: 完全な機能説明・技術仕様
- **[計算仕様書](shared/calculation_overview.md)**: 最適化アルゴリズム詳細
- **[移行計画](shared/migration_plan.md)**: Streamlit→PyQt6移行ガイド
- **[GUI比較](shared/gui_comparison.py)**: インターフェース比較デモ

## 🛠 システム要件

### 最小要件
- Python 3.8+
- 4GB RAM
- 100MB ディスク空間

### 推奨要件 (PyQt6版)
- Python 3.10+
- 8GB RAM
- macOS 10.14+ / Windows 10+ / Linux
- SSDストレージ

## ⚡ パフォーマンス指標

| データサイズ | Streamlit版 | PyQt6版 |
|-------------|-------------|---------|
| 1,000スロット | 30秒 | 15秒 |
| 10,000スロット | 5分 | 2分 |
| 100,000スロット | 50分 | 20分 |

## 🆘 サポート

### よくある問題

1. **CBC solver エラー (macOS)**
   ```bash
   brew install cbc  # HomebrewでCBCインストール
   ```

2. **PyQt6 インストールエラー**
   ```bash
   pip install --upgrade pip
   pip install PyQt6 --no-cache-dir
   ```

3. **Streamlit 起動問題**
   ```bash
   streamlit --version  # バージョン確認
   pip install streamlit --upgrade
   ```

## 📈 ロードマップ

### Phase 1: 現在 ✅
- Streamlit版完成
- PyQt6版完成
- ドキュメント整備

### Phase 2: 今後の予定
- バッチ処理機能
- API連携
- レポート生成機能
- 多言語対応

## 📄 ライセンス

詳細は [LICENSE](shared/LICENSE) を参照してください。

## 👥 貢献

プロジェクトへの貢献を歓迎します：

1. Issue報告
2. 機能要望
3. Pull Request
4. ドキュメント改善

---

**🏢 Factlabel** | © 2024 | Battery Storage Optimization Solutions 