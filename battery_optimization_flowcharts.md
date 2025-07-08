# Battery Optimizer v2.1 - システムフローチャート

このドキュメントには、PyQt6版 Battery Optimizer v2.1の処理フローを視覚化するMermaidフローチャートが含まれています。

## 1. アプリケーション全体フロー

```mermaid
flowchart TD
    A["🚀 アプリケーション起動<br/>main.py"] --> B["⚙️ GUI初期化<br/>BatteryOptimizerMainWindow"]
    
    B --> C["📋 6タブインターフェース作成<br/>• Graphs<br/>• Revenue Details<br/>• Data<br/>• Summary<br/>• AI Chat<br/>• 託送料金・損失率"]
    
    C --> D["📊 パラメータ設定画面<br/>• バッテリー仕様<br/>• エリア・電圧選択<br/>• 市場参加設定"]
    
    D --> E["📂 CSVファイル読み込み<br/>ユーザー操作待ち"]
    
    E --> F["🔍 データ検証<br/>_validate_input_data()"]
    
    F --> G{"✅ データ有効？"}
    
    G -->|"❌ 無効"| H["⚠️ エラー表示<br/>• 詳細ログ出力<br/>• 修正提案"]
    
    G -->|"✅ 有効"| I["🔄 最適化エンジン起動<br/>OptimizationEngine(QThread)"]
    
    I --> J["📈 リアルタイム進捗表示<br/>• プログレスバー<br/>• ステータス更新<br/>• ログ出力"]
    
    J --> K["🎯 最適化実行<br/>PuLP線形計画法"]
    
    K --> L{"✅ 最適化成功？"}
    
    L -->|"❌ 失敗"| M["❌ エラー処理<br/>• 自動エラー報告<br/>• フォールバック処理"]
    
    L -->|"✅ 成功"| N["📊 結果表示<br/>6タブ更新"]
    
    N --> O["🤖 AI分析機能<br/>ChatBotWorker(QThread)"]
    
    O --> P["📤 結果エクスポート<br/>CSV・グラフ出力"]
    
    H --> E
    M --> E
    P --> Q["✅ 完了"]
    
    %% スタイル設定
    classDef startEnd fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef success fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    
    class A,Q startEnd
    class B,C,D,E,F,I,J,K,N,O,P process
    class G,L decision
    class H,M error
```

## 2. 最適化エンジン詳細フロー (OptimizationEngine)

```mermaid
flowchart TD
    A["🔄 OptimizationEngine.run()<br/>QThread開始"] --> B["📋 データ検証<br/>_validate_input_data()"]
    
    B --> C["🧹 Step 1: NaN値除去<br/>必須列チェック"]
    C --> D["🔧 Step 2: データ型変換<br/>数値列の正規化"]
    D --> E["🎯 Step 3: スロット検証<br/>1-48範囲チェック"]
    E --> F["📅 Step 4: 日付検証<br/>pandas自動検出"]
    F --> G["📊 Step 5: データ統計<br/>品質レポート生成"]
    
    G --> H{"✅ 検証完了？"}
    
    H -->|"❌"| ERROR["❌ 検証エラー<br/>optimization_failed.emit()"]
    H -->|"✅"| I["🗺️ 託送データ取得<br/>_get_wheeling_data()"]
    
    I --> J["📊 データ前処理<br/>• 日付・スロット順ソート<br/>• 期間計算<br/>• 初期SOC設定"]
    
    J --> K["🔄 日別最適化ループ<br/>_run_battery_optimization()"]
    
    K --> L["📅 Day N データ抽出<br/>forecast_period分"]
    
    L --> M["🔨 PuLP問題構築<br/>_solve_daily_optimization()"]
    
    M --> N["⚙️ 決定変数定義<br/>• 連続変数: charge, discharge<br/>• バイナリ変数: is_charge, is_discharge<br/>• SOC変数: battery_soc"]
    
    N --> O["📋 制約条件設定<br/>• SOC遷移制約<br/>• 排他制約<br/>• 容量制約<br/>• サイクル制限"]
    
    O --> P["🧱 EPRX1制約<br/>（フルモード）"]
    
    P --> Q["🎯 目的関数設定<br/>利益最大化<br/>• JEPX収益<br/>• EPRX1収益<br/>• EPRX3収益"]
    
    Q --> R["⚡ ソルバー実行<br/>• COIN_CMD（優先）<br/>• HiGHS（次点）<br/>• 時間制限なし"]
    
    R --> S{"✅ 最適解発見？"}
    
    S -->|"❌"| T["⚠️ フォールバック<br/>全スロットアイドル"]
    S -->|"✅"| U["📊 解抽出<br/>• Action決定<br/>• SOC計算<br/>• 数値精度処理"]
    
    T --> V["💰 P&L計算<br/>_calculate_slot_pnl()"]
    U --> V
    
    V --> W["📈 結果蓄積<br/>all_transactions.extend()"]
    
    W --> X{"📅 全日完了？"}
    
    X -->|"❌"| L
    X -->|"✅"| Y["📊 サマリー生成<br/>_generate_summary()"]
    
    Y --> Z["📅 月次サマリー<br/>_generate_monthly_summary()"]
    
    Z --> AA["✅ 最適化完了<br/>optimization_completed.emit()"]
    
    %% エラーハンドリング
    R -.->|"ソルバーエラー"| ERROR
    L -.->|"キャンセル"| CANCEL["⏹️ 最適化キャンセル<br/>is_cancelled = True"]
    
    %% スタイル設定
    classDef startEnd fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef calc fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    
    class A,AA startEnd
    class B,C,D,E,F,G,I,J,K,L,M,N,O,P,Q,R,T,U,V,W,Y,Z process
    class H,S,X decision
    class ERROR,CANCEL error
    class AA calc
```

## 3. AI分析機能フロー (v2.1新機能)

```mermaid
flowchart TD
    A["🤖 AI Chat機能開始<br/>ユーザーメッセージ入力"] --> B["📊 送信データ確認<br/>show_ai_data_debug()"]
    
    B --> C["🔍 データ準備<br/>_generate_ai_context_stats()"]
    
    C --> D["📈 統計分析<br/>• 収益分析<br/>• 期間情報<br/>• アクション分析<br/>• エネルギー分析"]
    
    D --> E["📋 構造化データ作成<br/>• サマリー情報<br/>• 詳細統計<br/>• 生データサンプル"]
    
    E --> F["🧵 ChatBotWorker起動<br/>QThread開始"]
    
    F --> G["💬 OpenAI API呼び出し<br/>GPT-4o"]
    
    G --> H{"✅ API成功？"}
    
    H -->|"❌"| I["❌ エラー処理<br/>• APIキー確認<br/>• ネットワーク診断<br/>• エラー報告"]
    
    H -->|"✅"| J["📝 回答処理<br/>• Markdown変換<br/>• 構造化表示"]
    
    J --> K["💾 チャット履歴保存<br/>会話継続"]
    
    K --> L["🔄 次の質問待ち"]
    
    I --> M["🐛 問題報告機能<br/>自動エラー報告"]
    
    M --> N["📧 管理者通知<br/>SMTP送信"]
    
    L --> A
    N --> L
    
    %% データデバッグ分岐
    B --> O["📊 送信データ確認ダイアログ<br/>3タブ表示"]
    O --> P["📋 サマリータブ<br/>基本収益情報"]
    O --> Q["📈 詳細統計タブ<br/>収益・期間・アクション分析"]
    O --> R["🗂️ 生データタブ<br/>最適化結果サンプル"]
    
    P --> S["✅ データ確認完了"]
    Q --> S
    R --> S
    S --> F
    
    %% スタイル設定
    classDef ai fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef data fill:#f1f8e9,stroke:#388e3c,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px
    
    class A,F,G,J ai
    class B,C,D,E,O,P,Q,R data
    class K,L,M,N,S process
    class H decision
    class I,M,N error
```

## 4. Revenue Details生成フロー (v2.1新機能)

```mermaid
flowchart TD
    A["📊 Revenue Detailsタブ選択<br/>update_revenue_details()"] --> B["📋 最適化結果確認<br/>optimization_results"]
    
    B --> C{"📊 データ存在？"}
    
    C -->|"❌"| D["❌ 空チャート表示<br/>init_empty_revenue_chart()"]
    
    C -->|"✅"| E["🔍 データフィルタリング<br/>get_filtered_data()"]
    
    E --> F["📅 期間選択処理<br/>• 全期間<br/>• 最近7日<br/>• 最近30日<br/>• 期間指定"]
    
    F --> G["📈 データ前処理<br/>• datetime列作成<br/>• total_pnl計算<br/>• 統計情報生成"]
    
    G --> H["🎨 Figure初期化<br/>matplotlib 4subplot構成"]
    
    H --> I["📊 グラフ1: 時間別収益分布<br/>バーチャート"]
    
    I --> J["💹 グラフ2: 市場別収益貢献<br/>パイチャート（JEPX/EPRX1/EPRX3）"]
    
    J --> K["🎯 グラフ3: アクション分布<br/>パイチャート（charge/discharge/eprx1/eprx3/idle）"]
    
    K --> L["📈 グラフ4: 日別収益推移<br/>ラインチャート（利益・損失エリア）"]
    
    L --> M["📋 統計情報追加<br/>• 総収益<br/>• 平均日収<br/>• 最高・最低収益日"]
    
    M --> N["🎨 レイアウト調整<br/>tight_layout()"]
    
    N --> O["🖼️ キャンバス描画<br/>revenue_canvas.draw()"]
    
    O --> P["✅ 表示完了"]
    
    %% エラーハンドリング
    I -.->|"エラー"| ERROR1["❌ グラフ1エラー<br/>エラーメッセージ表示"]
    J -.->|"エラー"| ERROR2["❌ グラフ2エラー<br/>エラーメッセージ表示"]
    K -.->|"エラー"| ERROR3["❌ グラフ3エラー<br/>エラーメッセージ表示"]
    L -.->|"エラー"| ERROR4["❌ グラフ4エラー<br/>エラーメッセージ表示"]
    
    ERROR1 --> J
    ERROR2 --> K
    ERROR3 --> L
    ERROR4 --> M
    
    %% 大容量データ対応
    G --> OPTIMIZE["⚡ 大容量データ最適化<br/>• サンプリング処理<br/>• フォントサイズ調整<br/>• マーカーサイズ調整"]
    
    OPTIMIZE --> I
    
    %% スタイル設定
    classDef chart fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef optimize fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    
    class A,I,J,K,L,O,P chart
    class B,E,F,G,H,M,N process
    class C decision
    class D,ERROR1,ERROR2,ERROR3,ERROR4 error
    class OPTIMIZE optimize
```

## 5. 6タブシステム構成

```mermaid
flowchart LR
    A["🖥️ メインウィンドウ<br/>BatteryOptimizerMainWindow"] --> B["📊 6タブインターフェース<br/>QTabWidget"]
    
    B --> C["📈 Graphsタブ<br/>• バッテリー残量推移<br/>• JEPX価格推移<br/>• 期間フィルタ機能"]
    
    B --> D["💰 Revenue Detailsタブ<br/>• 時間別収益分布<br/>• 市場別収益貢献<br/>• アクション分布<br/>• 日別収益推移"]
    
    B --> E["📋 Dataタブ<br/>• 詳細最適化結果<br/>• CSVエクスポート<br/>• ソート・検索機能"]
    
    B --> F["📊 Summaryタブ<br/>• 財務サマリー<br/>• 運用統計<br/>• 月次分析"]
    
    B --> G["🤖 AI Chatタブ<br/>• GPT-4o分析<br/>• 送信データ確認<br/>• 問題報告機能"]
    
    B --> H["⚙️ 託送料金・損失率タブ<br/>• 全エリア・電圧データ<br/>• リアルタイム編集<br/>• 再エネ賦課金設定"]
    
    C --> I["🎛️ 期間選択機能<br/>• 全期間<br/>• 最近7日<br/>• 最近30日<br/>• カレンダー選択"]
    
    D --> J["📊 4つのグラフ<br/>matplotlib統合"]
    
    E --> K["📤 エクスポート機能<br/>CSV・Excel対応"]
    
    F --> L["📈 KPI表示<br/>収益性指標"]
    
    G --> M["🔧 AI機能<br/>• 分析・レポート<br/>• 質問応答<br/>• エラー診断"]
    
    H --> N["💾 データ管理<br/>• 編集・保存<br/>• リセット機能"]
    
    %% スタイル設定
    classDef main fill:#e1f5fe,stroke:#01579b,stroke-width:3px
    classDef tab fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef feature fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    
    class A main
    class B,C,D,E,F,G,H tab
    class I,J,K,L,M,N feature
```

## 6. データフロー概要

```mermaid
flowchart TD
    A["📂 CSVファイル入力<br/>価格予測データ"] --> B["🔍 データ検証<br/>7段階品質チェック"]
    
    B --> C["⚙️ パラメータ設定<br/>• バッテリー仕様<br/>• エリア・電圧<br/>• 市場参加設定"]
    
    C --> D["🔄 最適化計算<br/>PuLP線形計画法"]
    
    D --> E["📊 結果データ<br/>スロット別最適化結果"]
    
    E --> F["📈 6タブ表示"]
    
    F --> G["📈 Graphs<br/>バッテリー残量・価格推移"]
    F --> H["💰 Revenue Details<br/>4種収益分析グラフ"]
    F --> I["📋 Data<br/>詳細結果テーブル"]
    F --> J["📊 Summary<br/>財務・運用サマリー"]
    F --> K["🤖 AI Chat<br/>GPT-4o分析"]
    F --> L["⚙️ 託送料金・損失率<br/>データ管理"]
    
    E --> M["📤 エクスポート<br/>• CSV結果<br/>• グラフ画像<br/>• レポート"]
    
    K --> N["💬 AI分析結果<br/>• 収益性分析<br/>• 改善提案<br/>• 質問応答"]
    
    %% 外部連携
    O["🌐 外部データ<br/>• 気象データ<br/>• 市場価格<br/>• 需要予測"] -.-> A
    
    P["⚙️ 設定ファイル<br/>• 託送料金<br/>• 損失率<br/>• APIキー"] -.-> C
    
    M --> Q["📊 レポート出力<br/>• 経営報告<br/>• 運用実績<br/>• 改善提案"]
    
    %% スタイル設定
    classDef input fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef output fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef external fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class A,O,P input
    class B,C,D,E,F process
    class G,H,I,J,K,L,M,N,Q output
    class O,P external
```

このフローチャートは、Battery Optimizer v2.1の最新機能と処理フローを包括的に表現しています。実際の実装と正確に対応しており、AI機能、Revenue Details、6タブ構成などの新機能が反映されています。 