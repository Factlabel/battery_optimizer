# バッテリー最適化 計算ロジック フローチャート

このドキュメントには、バッテリー最適化システムの計算ロジックを視覚化するMermaidフローチャートが含まれています。

## 1. メイン処理フロー

以下のMermaidコードをコピーして、任意のMermaid対応エディタで編集・表示できます：

```mermaid
flowchart TD
    A["🔄 最適化開始<br/>OptimizationEngine.run()"] --> B{"📋 入力データ検証<br/>_validate_input_data()"}
    
    B -->|"エラー"| ERROR["❌ 最適化失敗<br/>optimization_failed.emit()"]
    B -->|"成功"| C["📍 托送データ取得<br/>_get_wheeling_data()"]
    
    C --> D["🔧 パラメータ設定<br/>• バッテリー容量/出力<br/>• 損失率<br/>• デバッグモード"]
    
    D --> E["📊 データ前処理<br/>• 日付・スロット順ソート<br/>• 日数計算<br/>• 初期SOC設定"]
    
    E --> F["🔄 日別最適化ループ開始<br/>_run_battery_optimization()"]
    
    F --> G["📅 Day N データ抽出<br/>forecast_period分のスロット"]
    
    G --> H["🔨 PuLP最適化問題構築<br/>_solve_daily_optimization()"]
    
    H --> I["⚙️ 決定変数定義"]
    
    I --> J["📈 連続変数<br/>• charge[i]: 充電量<br/>• discharge[i]: 放電量<br/>• battery_soc[i]: SOC"]
    
    J --> K["🔢 バイナリ変数<br/>• is_charge[i]<br/>• is_discharge[i]<br/>• is_eprx3[i]<br/>• is_idle[i]"]
    
    K --> L{"🎯 デバッグモード判定"}
    
    L -->|"simple"| M["🎯 シンプルモード<br/>EPRX1ブロックなし"]
    L -->|"basic"| N["🎯 ベーシックモード<br/>基本EPRX1制約のみ"]
    L -->|"full"| O["🎯 フルモード<br/>全EPRX1制約"]
    
    M --> P["📋 基本制約設定"]
    N --> Q["📋 EPRX1基本制約設定"]
    O --> R["📋 EPRX1フル制約設定"]
    
    P --> S["🎯 シンプル目的関数<br/>JEPX + EPRX3のみ"]
    Q --> T["🎯 EPRX1目的関数<br/>JEPX + EPRX1 + EPRX3"]
    R --> T
    
    S --> U["⚡ 制約条件設定"]
    T --> U
    
    U --> V["🔗 SOC遷移制約<br/>battery_soc[i+1] = battery_soc[i]<br/>+ charge - discharge - eprx3"]
    
    V --> W["🚫 排他制約<br/>各スロットで1つのアクションのみ"]
    
    W --> X["📊 価格データ制約<br/>予測価格が0またはNaNの場合<br/>該当アクション無効化"]
    
    X --> Y["🔧 最適化実行<br/>PuLP.solve()"]
    
    Y --> Z{"✅ 解が見つかったか？"}
    
    Z -->|"No"| AA["⚠️ フォールバック処理<br/>全スロットアイドル"]
    Z -->|"Yes"| BB["📊 最適解から結果抽出"]
    
    AA --> CC["💾 日別結果保存"]
    BB --> DD["🔄 SOC値抽出<br/>pulp.value(battery_soc[i+1])"]
    
    DD --> EE["💰 P&L計算<br/>_calculate_slot_pnl()"]
    
    EE --> FF["📈 スロット別詳細計算<br/>• 充電コスト<br/>• 放電収益<br/>• EPRX収益<br/>• 税込み計算"]
    
    FF --> CC
    
    CC --> GG["🔄 次期SOC更新<br/>carry_over_soc"]
    
    GG --> HH{"📅 全日完了？"}
    
    HH -->|"No"| G
    HH -->|"Yes"| II["📊 全体結果集計"]
    
    II --> JJ["📋 サマリー生成<br/>_generate_summary()"]
    
    JJ --> KK["📈 月次サマリー生成<br/>_generate_monthly_summary()"]
    
    KK --> LL["✅ 最適化完了<br/>optimization_completed.emit()"]
    
    %% エラーハンドリング
    Y -.->|"ソルバーエラー"| ERROR
    G -.->|"キャンセル"| CANCEL["⏹️ 最適化キャンセル<br/>is_cancelled = True"]
    
    %% スタイル設定
    classDef startEnd fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef process fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef data fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    
    class A,LL startEnd
    class B,C,D,E,F,G,H,I,J,K,M,N,O,P,Q,R,S,T,U,V,W,X,Y,BB,CC,DD,EE,FF,GG,II,JJ,KK process
    class L,Z,HH decision
    class ERROR,CANCEL error
    class AA data
```

## 2. 最適化問題の数学的構造

```mermaid
flowchart TD
    A["🎯 最適化問題の数学的構造"] --> B["📊 決定変数 Variables"]
    
    B --> C["📈 連続変数<br/>• charge[i] ∈ [0,1]<br/>• discharge[i] ∈ [0,1]<br/>• battery_soc[i] ∈ [0, capacity]"]
    
    B --> D["🔢 バイナリ変数<br/>• is_charge[i] ∈ {0,1}<br/>• is_discharge[i] ∈ {0,1}<br/>• is_eprx3[i] ∈ {0,1}<br/>• is_idle[i] ∈ {0,1}"]
    
    B --> E["🧱 EPRX1ブロック変数<br/>（フルモードのみ）<br/>• block_start[i] ∈ {0,1}<br/>• is_in_block[i] ∈ {0,1}"]
    
    C --> F["🔧 制約条件 Constraints"]
    D --> F
    E --> F
    
    F --> G["⚖️ 基本制約"]
    F --> H["🔗 SOC制約"]
    F --> I["🚫 排他制約"]
    F --> J["📊 価格制約"]
    F --> K["🧱 EPRX1制約"]
    
    G --> G1["🔗 変数リンク制約<br/>charge[i] ≤ is_charge[i]<br/>discharge[i] ≤ is_discharge[i]"]
    
    H --> H1["🔄 SOC遷移制約<br/>battery_soc[i+1] = battery_soc[i]<br/>+ charge[i] × half_power_kWh<br/>- discharge[i] × half_power_kWh<br/>- is_eprx3[i] × half_power_kWh"]
    
    H --> H2["📍 初期SOC制約<br/>battery_soc[0] = initial_soc"]
    
    H --> H3["🔋 SOC範囲制約<br/>0 ≤ battery_soc[i] ≤ capacity"]
    
    I --> I1["🎯 アクション排他制約<br/>is_charge[i] + is_discharge[i]<br/>+ is_eprx3[i] + is_idle[i] = 1"]
    
    J --> J1["📉 価格ゼロ制約<br/>if EPRX3_pred[i] = 0 or NaN:<br/>  is_eprx3[i] = 0"]
    
    J --> J2["📉 EPRX1価格制約<br/>if EPRX1_pred[j] = 0 for j in block:<br/>  block_start[i] = 0"]
    
    K --> K1{"🎯 EPRX1モード判定"}
    
    K1 -->|"simple"| K2["❌ EPRX1制約なし"]
    K1 -->|"basic"| K3["🔧 基本EPRX1制約<br/>• ブロック連続性<br/>• 価格制約のみ"]
    K1 -->|"full"| K4["⚡ 完全EPRX1制約<br/>• ブロック連続性<br/>• クールダウン制約<br/>• SOC範囲制約<br/>• 日次制限制約"]
    
    K3 --> K5["🔗 ブロック連続性制約<br/>is_in_block[i] = Σ block_start[x]<br/>for x where block covers slot i"]
    
    K4 --> K5
    K4 --> K6["⏳ クールダウン制約<br/>block_start[i] + block_start[j] ≤ 1<br/>for j in [i+1, i+M+C-1]"]
    
    K4 --> K7["📊 EPRX1時SOC制約<br/>if is_in_block[i] = 1:<br/>  0.4×capacity ≤ soc[i] ≤ 0.6×capacity"]
    
    K4 --> K8["🔄 日次サイクル制限<br/>Σ charge[i] × half_power ≤<br/>cycle_limit × capacity"]
    
    K4 --> K9["📅 日次EPRX1制限<br/>Σ is_in_block[i] ≤ max_daily_slots"]
    
    F --> L["🎯 目的関数 Objective Function"]
    
    L --> M["💰 利益最大化<br/>Maximize: Σ slot_profit[i]"]
    
    M --> N["💸 充電コスト<br/>cost_charge = JEPX_pred[i] ×<br/>charge[i] × half_power /<br/>(1 - wheeling_loss)"]
    
    M --> O["💵 放電収益<br/>revenue_discharge = JEPX_pred[i] ×<br/>discharge[i] × half_power ×<br/>(1 - battery_loss)"]
    
    M --> P["💎 EPRX3収益<br/>revenue_eprx3 = TAX × is_eprx3[i] ×<br/>(power × EPRX3_pred[i] +<br/>half_power × (1-loss) × imbalance[i])"]
    
    M --> Q["🧱 EPRX1収益<br/>（フル/ベーシックモードのみ）<br/>revenue_eprx1 = TAX × is_in_block[i] ×<br/>(power × EPRX1_pred[i] +<br/>half_power × (1-loss) × imbalance[i])"]
    
    N --> R["⚡ スロット利益<br/>slot_profit[i] = -cost_charge +<br/>revenue_discharge + revenue_eprx3 +<br/>revenue_eprx1"]
    O --> R
    P --> R
    Q --> R
    
    R --> S["🔧 PuLP求解<br/>prob.solve()"]
    
    S --> T{"✅ 最適解発見？"}
    
    T -->|"Yes"| U["📊 解抽出<br/>• charge_kWh = pulp.value(charge[i]) × half_power<br/>• discharge_kWh = pulp.value(discharge[i]) × half_power<br/>• current_soc = pulp.value(battery_soc[i+1])"]
    
    T -->|"No"| V["⚠️ フォールバック<br/>全スロットアイドル状態"]
    
    U --> W["💰 P&L計算<br/>_calculate_slot_pnl()"]
    V --> W
    
    W --> X["✅ 日別結果完了"]
    
    %% スタイル設定
    classDef header fill:#e3f2fd,stroke:#0277bd,stroke-width:3px
    classDef variable fill:#f1f8e9,stroke:#388e3c,stroke-width:2px
    classDef constraint fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef objective fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef decision fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef result fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    
    class A header
    class B,C,D,E variable
    class F,G,H,I,J,K,G1,H1,H2,H3,I1,J1,J2,K2,K3,K4,K5,K6,K7,K8,K9 constraint
    class L,M,N,O,P,Q,R objective
    class K1,T decision
    class S,U,V,W,X result
```

## 3. 主要な計算要素の説明

### 決定変数
- **charge[i]**: スロットiでの充電割合 (0-1)
- **discharge[i]**: スロットiでの放電割合 (0-1)
- **battery_soc[i]**: スロットi終了時のバッテリー蓄電量 (kWh)
- **is_charge[i]**: スロットiで充電を行うかのバイナリ変数
- **is_discharge[i]**: スロットiで放電を行うかのバイナリ変数
- **is_eprx3[i]**: スロットiでEPRX3を行うかのバイナリ変数
- **is_idle[i]**: スロットiでアイドル状態かのバイナリ変数

### 制約条件
1. **SOC遷移制約**: バッテリーの蓄電量の時系列的な変化を表現
2. **排他制約**: 各スロットで1つのアクションのみ実行可能
3. **容量制約**: バッテリーの最大・最小容量制限
4. **価格制約**: 予測価格が無効な場合の動作制限

### 目的関数
各スロットでの利益を合計し、総利益を最大化：
- 充電コスト（JEPX価格 + 托送損失）
- 放電収益（JEPX価格 - バッテリー損失）
- EPRX収益（EPRX1/EPRX3価格 + インバランス収益）

## 4. 編集方法

このファイルのMermaidコードは以下の方法で編集・表示できます：

1. **オンラインエディタ**: https://mermaid.live/ でコードを貼り付け
2. **VS Code**: Mermaid Preview拡張機能をインストール
3. **GitHubのマークダウン**: 直接レンダリング可能
4. **Notion, Obsidian**: Mermaid対応プラグインで表示

## 5. カスタマイズ例

### 色の変更
```mermaid
classDef newStyle fill:#yourcolor,stroke:#yourstroke,stroke-width:2px
class NodeName newStyle
```

### ノードの追加
```mermaid
NewNode["新しい処理"] --> ExistingNode
```

### 接続線の変更
```mermaid
A -.->|"条件付き"| B  %% 点線
A ==>|"太線"| C        %% 太線
``` 