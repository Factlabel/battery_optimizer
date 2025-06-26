# Battery Optimizer (Pilot Version)

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.42.2-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Battery Optimizer** は、日本の電力市場におけるバッテリー蓄電システムの運用最適化を行うWebアプリケーションです。PuLP線形計画法ライブラリとCBCソルバーを使用して、JEPX（日本卸電力取引所）市場とEPRX（需給調整市場）での最適な充放電スケジュールを算出し、収益最大化を実現します。

## 🌟 主な特徴

### 📊 **多市場対応の最適化**
- **JEPX市場**: スポット市場での充放電最適化
- **EPRX1市場**: 一次調整力（30分連続ブロック運用）
- **EPRX3市場**: 三次調整力（需給バランス調整）
- **複合戦略**: 複数市場の同時考慮による収益最大化

### 🗾 **全国エリア対応**
- 北海道〜九州の全9エリアに対応
- エリア別託送料金・損失率の自動適用
- 特高（SHV）・高圧（HV）・低圧（LV）の電圧区分対応

### ⚡ **高度な制約処理**
- バッテリー物理制約（SoC上下限、出力制約）
- 日次・年次充放電サイクル制限
- EPRX1ブロック運用制約（SoC40-60%維持）
- クールダウン期間とブロック数制限

### 📈 **詳細分析機能**
- リアルタイムグラフ表示（バッテリー残量・価格推移）
- 月次サマリー自動生成
- CSV形式での詳細データエクスポート
- 税込み収益計算（託送料金・再エネ賦課金含む）

## 🚀 クイックスタート

### 前提条件
- **Python 3.11以上**
- **pip** パッケージマネージャー

### インストール

1. **リポジトリのクローン**
   ```bash
   git clone https://github.com/Factlabel/battery_optimizer.git
   cd battery_optimizer
   ```

2. **仮想環境の作成（推奨）**
   ```bash
   python -m venv .venv
   
   # macOS/Linux
   source .venv/bin/activate
   
   # Windows
   .venv\Scripts\activate
   ```

3. **依存関係のインストール**
   ```bash
   pip install -r requirements.txt
   ```

### アプリケーション起動

```bash
streamlit run main.py
```

ブラウザで `http://localhost:8501` にアクセスしてアプリケーションを使用できます。

## 📖 使用方法

### 1. 基本パラメータ設定
- **対象エリア**: 運用地域（1:北海道 〜 9:九州）
- **電圧区分**: SHV（特高）/ HV（高圧）/ LV（低圧）
- **バッテリー仕様**: 出力(kW)・容量(kWh)・損失率

### 2. 運用制約設定
- **充放電サイクル**: 日次・年次上限設定
- **EPRX1設定**: ブロックサイズ・クールダウン・日次上限
- **予測期間**: 最適化対象スロット数（通常48スロット=1日）

### 3. 価格データのアップロード
CSVテンプレートをダウンロードし、以下の価格データを入力：

| 列名 | 説明 | 必須 |
|------|------|------|
| `date` | 日付 (YYYY-MM-DD) | ✅ |
| `slot` | スロット番号 (1-48) | ✅ |
| `JEPX_prediction` | JEPX予想価格 (円/kWh) | ✅ |
| `JEPX_actual` | JEPX実績価格 (円/kWh) | ✅ |
| `EPRX1_prediction` | EPRX1予想価格 (円/kW) | ✅ |
| `EPRX1_actual` | EPRX1実績価格 (円/kW) | ✅ |
| `EPRX3_prediction` | EPRX3予想価格 (円/kW) | ✅ |
| `EPRX3_actual` | EPRX3実績価格 (円/kW) | ✅ |
| `imbalance` | インバランス価格 (円/kWh) | ✅ |

### 4. 最適化実行・結果確認
- **計算ボタン**: 最適化を実行
- **グラフ表示**: バッテリー残量と価格の時系列推移
- **データエクスポート**: 詳細結果・月次サマリーのCSV出力

## 🏗️ プロジェクト構成

```
battery_optimizer/
├── 📁 .venv/                       # Python仮想環境
├── 📁 assets/                      # 静的リソース
│   ├── 📁 images/
│   │   └── LOGO_factlabel.png      # アプリケーションロゴ
│   └── csv_template_sample.csv     # 価格データテンプレート
├── 📁 docs/                        # プロジェクト文書
│   ├── hands_on_guide.md           # ハンズオンガイド
│   └── user_manual.md              # ユーザーマニュアル
├── 📁 src/                         # ソースコード
│   ├── __init__.py
│   ├── optimization.py             # 🧠 最適化エンジン（PuLP使用）
│   └── config.py                   # 📋 エリア設定・託送料金データ
├── main.py                         # 🚀 Streamlitアプリケーション
├── requirements.txt                # 📦 Python依存関係
├── calculation_overview.md         # 📊 計算仕様書
├── README.md                       # 📖 このファイル
├── LICENSE                         # ⚖️ ライセンス
└── .gitignore                      # 🙈 Git除外設定
```

## ⚙️ 技術仕様

### 依存関係
```python
streamlit~=1.42.2       # Webアプリケーションフレームワーク
pandas~=2.2.3           # データ処理・分析
numpy~=2.2.3            # 数値計算
PuLP~=3.0.2             # 線形計画法ライブラリ
matplotlib~=3.10.0      # グラフ描画
```

### 最適化アルゴリズム
- **手法**: 線形計画法（Linear Programming）
- **ソルバー**: CBC (Coin-or Branch and Cut)
- **変数**: 混合整数（連続変数 + バイナリ変数）
- **制約**: 物理制約・運用制約・市場制約

### サポート対象

#### 電力エリア（全9エリア）
| エリア番号 | エリア名 | 対応電圧 |
|-----------|----------|----------|
| 1 | 北海道 | SHV/HV/LV |
| 2 | 東北 | SHV/HV/LV |
| 3 | 東京 | SHV/HV/LV |
| 4 | 中部 | SHV/HV/LV |
| 5 | 北陸 | SHV/HV/LV |
| 6 | 関西 | SHV/HV/LV |
| 7 | 中国 | SHV/HV/LV |
| 8 | 四国 | SHV/HV/LV |
| 9 | 九州 | SHV/HV/LV |

#### アクション種別
1. **charge**: 市場からの充電（送電損失考慮）
2. **discharge**: 市場への放電（バッテリー損失考慮）
3. **eprx1**: 一次調整力ブロック運用
4. **eprx3**: 三次調整力（固定放電+インバランス精算）
5. **idle**: 待機状態

## 🔧 トラブルシューティング

### CBCソルバーエラー対策

#### エラー例
```bash
pulp.apis.core.PulpSolverError: PULP_CBC_CMD: Not Available (check permissions on .../cbc)
```

#### 解決方法

**1. 実行権限の付与**
```bash
chmod +x .venv/lib/python3.11/site-packages/pulp/solverdir/cbc/osx/arm64/cbc
```

**2. Homebrew経由でのCBCインストール（Apple Silicon推奨）**
```bash
brew install cbc
```

**3. ソルバーパスの手動指定**
```python
import pulp
solver = pulp.PULP_CBC_CMD(path="/opt/homebrew/bin/cbc", msg=0)
```

### パフォーマンス最適化

- **大規模データ**: 予測対象スロット数を調整（48-96スロット推奨）
- **計算時間短縮**: 制約条件の簡素化、期間分割
- **メモリ使用量**: 日次最適化での段階的処理

## 📊 計算仕様

詳細な計算ロジックについては [`calculation_overview.md`](calculation_overview.md) を参照してください。

### 重要な計算ポイント
- **調達量** = 充電量 ÷ (1 - 送電損失率)
- **販売量** = 放電量 × (1 - バッテリー損失率)
- **託送料金** = バッテリー損失分のみに課金
- **最終利益** = 日次PnL合計 - 託送基本料 - 託送従量料 - 再エネ賦課金

## 🗺️ プロジェクトロードマップ

### 現在: Streamlit版（Pilot 1.0）
- ✅ 基本最適化機能
- ✅ 全エリア対応
- ✅ CSV入出力
- ✅ 基本グラフ表示

### 次期: 独自UI版（Version 2.0）- 開発予定
独自UIによる次世代バージョンを開発中です。以下の機能強化を予定：

#### 🎨 **UI/UX改善**
- モダンなレスポンシブデザイン
- インタラクティブなダッシュボード
- リアルタイムデータ更新
- カスタマイズ可能なグラフ・チャート

#### ⚡ **パフォーマンス向上**
- 非同期処理による高速化
- 大規模データセット対応
- メモリ効率の最適化
- 並列計算処理

#### 🔧 **機能拡張**
- ユーザー管理・認証システム
- 複数シナリオの比較分析
- 自動レポート生成
- API連携機能

#### 🏗️ **技術スタック（予定）**
- **バックエンド**: FastAPI
- **フロントエンド**: React/Next.js
- **データベース**: PostgreSQL
- **キャッシュ**: Redis
- **デプロイ**: Docker + Kubernetes

### 移行計画
1. **Phase 1** (準備): プロジェクト構造再編・共通ロジック分離
2. **Phase 2** (基盤): バックエンドAPI・フロントエンド基盤構築
3. **Phase 3** (移植): 既存機能の移植・機能拡張
4. **Phase 4** (テスト): 並行運用・パフォーマンステスト
5. **Phase 5** (移行): 本格運用開始・Streamlit版廃止

## 📄 ライセンス

このプロジェクトは [MIT License](LICENSE) の下で公開されています。

## 📞 サポート・お問い合わせ

- **GitHub Issues**: バグレポート・機能要求
- **Documentation**: [`docs/`](docs/) ディレクトリ内の各種ガイド
- **計算仕様**: [`calculation_overview.md`](calculation_overview.md)

---

**開発者**: Factlabel  
**更新日**: 2025年5月  
**バージョン**: Pilot 1.0

---

⚡ **免責事項**: このソフトウェアはパイロット版であり、実際の取引での使用は自己責任で行ってください。計算結果の正確性について開発者は責任を負いません。