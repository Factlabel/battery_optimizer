# Battery Optimizer Project

バッテリー蓄電最適化システム - 日本電力市場（JEPX、EPRX1、EPRX3）対応

## プロジェクト構造

このリポジトリには、Battery Optimizerの2つのバージョンが含まれています：

```
battery_optimizer_pilot/
├── streamlit_app/          # Streamlit版 (Web App)
│   ├── main.py            # メインアプリケーション
│   ├── src/               # 最適化ロジック
│   ├── assets/            # CSVテンプレート・画像
│   ├── docs/              # ユーザーマニュアル
│   └── requirements.txt   # 依存関係
├── desktop_app/           # PyQt6版 (Desktop App)
│   └── battery_optimizer_gui/
│       ├── main.py        # デスクトップアプリ起動点
│       ├── start_app.sh   # ワンクリック起動スクリプト
│       ├── core/          # 最適化エンジン
│       ├── gui/           # ユーザーインターフェース
│       ├── config/        # 設定・エリアデータ
│       └── requirements.txt
└── shared/                # 共通資料
    ├── README.md          # 詳細プロジェクト説明
    ├── LICENSE            # ライセンス
    ├── calculation_overview.md  # 計算仕様書
    ├── migration_plan.md  # 移行計画
    └── gui_comparison.py  # GUI比較デモ
```

## セットアップ手順

### Streamlit版 (推奨: 初回利用・デモ)

```bash
cd streamlit_app
pip install -r requirements.txt
streamlit run main.py
```

**特徴:**
- ブラウザベースのシンプルなインターフェース
- 迅速なプロトタイピング・検証
- 軽量で導入が容易

### PyQt6版 (推奨: プロダクション利用)

**ワンクリック起動:**
```bash
cd desktop_app/battery_optimizer_gui
./start_app.sh  # macOS/Linux
# または start_app.sh をダブルクリック
```

**または従来の方法:**
```bash
cd desktop_app/battery_optimizer_gui
python setup.py  # 自動セットアップ
python run_battery_optimizer.py
```

**特徴:**
- ネイティブデスクトップアプリケーション
- リアルタイム進捗表示・詳細ログ
- 3段階のパフォーマンスモード選択
- 日付範囲フィルタ機能
- プロフェッショナルUI・オフライン動作

## 機能比較

| 機能 | Streamlit版 | PyQt6版 v2.1 |
|------|-------------|-------------|
| **UI/UX** | Web基本UI | ネイティブデスクトップ |
| **パフォーマンス** | 標準 | 高速（完全精度保証） |
| **リアルタイム進捗** | ❌ | ✅ |
| **日付フィルタ** | 基本 | 高機能 |
| **AI分析** | ❌ | GPT-4o統合 |
| **Revenue Details** | ❌ | 4種分析グラフ |
| **導入の簡単さ** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **プロダクション利用** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **データセキュリティ** | サーバー経由 | 完全ローカル |
| **オフライン動作** | ❌ | ✅ |
| **ファイル操作** | ブラウザ制限 | ネイティブ統合 |
| **エラー報告** | ❌ | 自動報告 |

## 利用用途別推奨

### 研究・検証・デモ → Streamlit版
- 素早いプロトタイピング
- 関係者への機能説明
- 初期検証・テスト

### 業務・プロダクション → PyQt6版
- 日常的な最適化業務
- 大規模データ処理
- セキュアな環境での運用
- 高速処理が必要な場合

## PyQt6版 バージョン履歴

### v2.1 - Critical Bug Fix & AI Integration

#### バグ修正
- データ検証エラーで全データが削除される問題を解決
- 日付形式対応: `2023/4/1`形式の単桁月日に対応
- pandas自動検出: より柔軟で確実な日付変換
- 変数未定義エラー修正: `final_rows`, `data_retention_rate`の適切な計算

#### AI機能統合
- OpenAI GPT-4o: 最適化結果の詳細分析とレポート生成
- Revenue Details: 時間別・市場別・アクション別・日別の4種収益分析
- インテリジェントチャット: 文脈理解型AI分析アシスタント
- 自動エラー報告: 管理者への自動報告システム

#### UI/UX改善
- 6タブインターフェース: Graphs, Revenue Details, Data, Summary, AI Chat, 託送料金・損失率
- 統合設定画面: ⚙️ボタンからAI・メール・一般設定を一元管理
- 複数エンコーディング対応: UTF-8, Shift_JIS, CP932, EUC-JP
- 自動データ品質検証: 7段階の詳細データ検証プロセス

### v2.0 - パフォーマンス改善

#### パフォーマンス改善
- ソルバー時間制限削除: 30秒制限 → 無制限で完全最適化
- フルモード統一: Streamlit版と同等の精度で高速処理
- デバッグログ最適化: オーバーヘッド削減（90%削減）
- メモリ使用量最適化: 大規模データセット対応

#### バグ修正・安定性向上
- Action決定ロジック修正: "charge actionなのに charge_kWh=0" 問題を解決
- 数値精度対応: 1e-6閾値で数値誤差を適切に処理
- 一貫性保証: actionと実際の充放電量の完全一致

#### 使いやすさ向上
- ワンクリック起動: `start_app.sh` でダブルクリック起動
- 日付範囲フィルタ: 全期間/最近7日/最近30日/期間指定
- 詳細ログ: 最適化プロセスの完全可視化

## 共通仕様

両バージョンとも以下の機能を提供：

### 最適化機能
- **市場対応**: JEPX現物、EPRX1/EPRX3調整力
- **エリア対応**: 日本全国9エリア（北海道〜九州）
- **電圧区分**: 特高圧・高圧・低圧
- **制約条件**: サイクル制限、EPRX1ブロック制約

### 入出力
- **入力**: CSV形式の価格データ
- **出力**: 最適化結果、収益サマリー
- **可視化**: バッテリー動作チャート、価格グラフ

### パラメータ設定
- バッテリー仕様（出力・容量・損失率）
- 市場参加設定
- 地域別託送料金自動計算

## 詳細ドキュメント

- **[詳細README](shared/README.md)**: 完全な機能説明・技術仕様
- **[計算仕様書](shared/calculation_overview.md)**: 最適化アルゴリズム詳細
- **[移行計画](shared/migration_plan.md)**: Streamlit→PyQt6移行ガイド
- **[GUI比較](shared/gui_comparison.py)**: インターフェース比較デモ
- **[起動ガイド](desktop_app/battery_optimizer_gui/README_LAUNCH.md)**: ワンクリック起動説明

## システム要件

### 最小要件
- Python 3.8+
- 4GB RAM
- 100MB ディスク空間

### 推奨要件 (PyQt6版)
- Python 3.10+
- 8GB RAM
- macOS 10.14+ / Windows 10+ / Linux
- SSDストレージ

## パフォーマンス指標

| データサイズ | Streamlit版 | PyQt6版 v2.1 |
|-------------|-------------|-------------|
| 1,000スロット | 30秒 | 18秒 |
| 10,000スロット | 5分 | 2分 |
| 100,000スロット | 50分 | 25分 |
| **精度** | 100% | 100% |
| **AI分析** | ❌ | GPT-4o |

## サポート

### よくある問題

1. **CBC solver エラー (macOS)**
   ```bash
   brew install cbc  # HomebrewでCBCインストール
   # または
   ./start_app.sh    # 自動修復機能付き
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

## ロードマップ

### Phase 1: 完成 ✅
- Streamlit版完成
- PyQt6版完成・パフォーマンス改善
- ドキュメント整備
- ワンクリック起動機能

### Phase 2: 今後の予定
- バッチ処理機能
- API連携
- レポート生成機能
- 多言語対応

## ライセンス

詳細は [LICENSE](shared/LICENSE) を参照してください。

---

**Factlabel** | © 2024 | Battery Storage Optimization Solutions 

**最新更新**: パフォーマンス改善・バグ修正・ワンクリック起動対応 