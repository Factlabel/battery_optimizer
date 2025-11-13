# Battery Optimizer Project

蓄電池運用の最適化を支援するシステムです。日本の電力市場（JEPX、EPRX1、EPRX3）への対応と、業務利用向けのローカル実行環境を中心に設計されています。

## バージョン構成

### V1: Streamlit Web Edition
- ブラウザ上で動作する簡易版です。
- 初期検証やデモンストレーション向けに最小限の構成で提供しています。
- セットアップ例
  ```bash
  cd streamlit_app
  pip install -r requirements.txt
  streamlit run main.py
  ```

### V2: PyQt6 Desktop Edition (Local)
- 完全ローカルで稼働するデスクトップアプリケーションです。
- ネイティブ UI、詳細な分析ビュー、AI レポート、オフライン運用をサポートします。
- 起動方法
  ```bash
  cd desktop_app/battery_optimizer_gui
  ./start_app.sh              # macOS/Linux
  # または
  python main.py
  ```
- 依存関係のセットアップを自動化する `python setup.py` も同梱しています。

## リポジトリ構造

```
battery_optimizer_pilot/
├── README.md
├── desktop_app/
│   └── battery_optimizer_gui/    # V2 Desktop Edition
├── streamlit_app/                # V1 Web Edition
└── shared/                       # 共通ドキュメント（計算仕様など）
```

## 機能概要

| 項目                     | V1 Streamlit | V2 PyQt6 Desktop |
|--------------------------|--------------|------------------|
| 提供形態                 | Web アプリ   | ローカルアプリ   |
| 主な用途                 | 検証・デモ   | 業務運用         |
| 収益分析ビュー           | 基本構成     | グラフ4種および月次サマリー |
| AI アシスタント          | なし         | OpenAI 連携      |
| オフライン動作           | 不可         | 可能             |
| データ処理性能           | 中           | 高               |

両バージョンとも CSV 形式の価格データを入力として利用し、最適化結果と統計サマリーを出力します。

## V2 Desktop Edition の主な機能
- 6 つのタブで構成された分析 UI（グラフ、収益詳細、データテーブル、サマリー、AI チャット、託送料金管理）
- 日付フィルターおよび月次サマリー表示
- AI アシスタントによる解釈とレポート生成
- 地域別託送料金および損失率の管理画面
- 依存関係診断および CBC ソルバー確認ツール

詳細な機能や操作手順については `desktop_app/battery_optimizer_gui/README.md` と `desktop_app/battery_optimizer_gui/README_LAUNCH.md` を参照してください。

## ドキュメント

- `desktop_app/battery_optimizer_gui/README.md` : デスクトップ版の概要とセットアップ
- `desktop_app/battery_optimizer_gui/README_LAUNCH.md` : 起動および運用ガイド
- `desktop_app/battery_optimizer_gui/USER_MANUAL.md` : 操作マニュアル
- `shared/calculation_overview.md` : 最適化アルゴリズムの仕様
- `streamlit_app/docs/user_manual.md` : Web 版の利用ガイド

## システム要件

| 項目                | 最小構成             | 推奨構成            |
|---------------------|----------------------|---------------------|
| Python              | 3.8 以上             | 3.10 以上           |
| メモリ              | 4 GB                 | 8 GB 以上           |
| OS                  | macOS / Windows / Linux | macOS 12+/Windows 11+/最新 Linux |
| ストレージ          | 100 MB               | SSD 環境            |

## よくある質問

1. **CBC ソルバーが見つからない**
   ```bash
   brew install cbc            # macOS
   python setup.py             # セットアップスクリプトで診断
   ```
2. **PyQt6 のインストールに失敗する**
   ```bash
   pip install --upgrade pip
   pip install PyQt6 --no-cache-dir
   ```
3. **Streamlit が起動しない**
   ```bash
   pip install streamlit --upgrade
   streamlit --version
   ```

## ライセンス

ライセンス情報は `shared/LICENSE` を参照してください。