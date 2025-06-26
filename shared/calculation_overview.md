# バッテリー最適化プロジェクト 計算概要

**作成日**: 2025年5月  

---

## 目次

1. [用語集](#1-用語集)
2. [アクション別の動作仕様](#2-アクション別の動作仕様)
3. [電池残量（SoC）の計算](#3-電池残量socの計算)
4. [収益（PnL）の計算](#4-収益pnlの計算)
5. [制約条件](#5-制約条件)
6. [月次集計](#6-月次集計)
7. [計算例](#7-計算例)

---

<div style="page-break-before: always;"></div>

## 1. 用語集

### 1.1 基本パラメータ

| 項目 | 説明 | 単位 | 例 |
|------|------|------|-----|
| `battery_power_kW` | バッテリーの最大充放電電力<br>（60分間での最大充放電量） | kW | 100 kW |
| `battery_capacity_kWh` | バッテリーの蓄電容量 | kWh | 200 kWh |
| `half_power_kWh` | 1スロット（30分）での最大充放電量<br>`battery_power_kW × 0.5` | kWh | 50 kWh |

### 1.2 損失率

| 項目 | 説明 | 例 |
|------|------|-----|
| `battery_loss_rate` | バッテリー内部損失率（放電時） | 0.05（5%） |
| `wheeling_loss_rate` | 送電損失率（充電時） | 0.03（3%） |

### 1.3 料金体系

| 項目 | 説明 | 単位 |
|------|------|------|
| `wheeling_basic_fee` | 託送基本料金 | 円/kW・月 |
| `wheeling_usage_fee` | 託送料金単価 | 円/kWh |
| `renewable_energy_surcharge` | 再エネ賦課金単価 | 円/kWh |

---

<div style="page-break-before: always;"></div>

## 2. アクション別の動作仕様

### 2.1 アクション概要

各スロット（30分間）で以下のいずれか1つのアクションを実行：

| アクション | 概要 | 主な用途 |
|-----------|------|----------|
| **charge** | 市場から電力を調達してバッテリーに充電 | 安価な時間帯での蓄電 |
| **discharge** | バッテリーから放電して市場に販売 | 高価な時間帯での売電 |
| **eprx1** | 一次調整力（30分間一定出力） | 系統安定化サービス |
| **eprx3** | 三次調整力（指令に応じた出力調整） | 需給バランス調整 |
| **idle** | 待機状態 | 市場条件が不利な場合 |

### 2.2 各アクションの詳細仕様

#### 2.2.1 charge（充電）

**動作**：
- 充電量 = `charge割合 × half_power_kWh`
- 調達量 = `充電量 ÷ (1 - wheeling_loss_rate)`

**制約**：
- 充電後のSoCが`battery_capacity_kWh`を超えない
- `charge割合`は0.0〜1.0の範囲

#### 2.2.2 discharge（放電）

**動作**：
- 放電量 = `discharge割合 × half_power_kWh`
- 販売量 = `放電量 × (1 - battery_loss_rate)`

**制約**：
- 放電後のSoCが0を下回らない
- `discharge割合`は0.0〜1.0の範囲

#### 2.2.3 eprx1（一次調整力）

**動作**：
- 30分間一定の出力を維持
- SoCを40〜60%の範囲で保持

**制約**：
- クールダウン期間の遵守
- 1日あたりの稼働スロット数上限

#### 2.2.4 eprx3（三次調整力）

**動作**：
- `half_power_kWh`を必ず放電
- 有効放電量 = `half_power_kWh × (1 - battery_loss_rate)`

**収入構成**：
1. kW価値：`battery_power_kW × EPRX3価格`
2. kWh価値：`有効放電量 × インバランス価格`

---

<div style="page-break-before: always;"></div>

## 3. 電池残量（SoC）の計算

### 3.1 基本計算式

```
次スロットのSoC (kWh) = 現在のSoC (kWh) + 充電量 - 放電量 - eprx3固定放電量
```

### 3.2 アクション別のSoC変化

| アクション | SoC変化量 |
|-----------|-----------|
| charge | `+charge割合 × half_power_kWh` |
| discharge | `-discharge割合 × half_power_kWh` |
| eprx1 | SoCを40〜60%範囲で調整 |
| eprx3 | `-half_power_kWh` |
| idle | 変化なし |

### 3.3 制約条件

- **上限制約**：`SoC ≤ battery_capacity_kWh`
- **下限制約**：`SoC ≥ 0`
- **EPRX1制約**：`0.4 × battery_capacity_kWh ≤ SoC ≤ 0.6 × battery_capacity_kWh`

---

<div style="page-break-before: always;"></div>

## 4. 収益（PnL）の計算

### 4.1 充電時のコスト

```
充電コスト (円) = JEPX予想価格 (円/kWh) × 調達量 (kWh) × 税率

調達量 (kWh) = 充電量 ÷ (1 - wheeling_loss_rate)
```

**例**：
- 充電量：100 kWh
- 送電損失率：3%
- 調達量：100 ÷ (1 - 0.03) = 103.09 kWh

### 4.2 放電時の収入

```
放電収入 (円) = JEPX予想価格 (円/kWh) × 販売量 (kWh) × 税率

販売量 (kWh) = 放電量 × (1 - battery_loss_rate)
```

**例**：
- 放電量：100 kWh
- バッテリー損失率：5%
- 販売量：100 × (1 - 0.05) = 95 kWh

### 4.3 EPRX1収入

```
EPRX1収入 (円) = EPRX1予想価格 (円/kW) × battery_power_kW × 税率
```

### 4.4 EPRX3収入

```
kW価値収入 (円) = battery_power_kW × EPRX3予想価格 (円/kW)
kWh価値収入 (円) = 有効放電量 × インバランス価格 (円/kWh)
EPRX3収入 (円) = (kW価値収入 + kWh価値収入) × 税率

有効放電量 (kWh) = half_power_kWh × (1 - battery_loss_rate)
```

### 4.5 スロット別PnL

```
スロットPnL (円) = -充電コスト + 放電収入 + EPRX1収入 + EPRX3収入
```


## 5. 制約条件

### 5.1 日次制約

#### 5.1.1 充電サイクル制限
```
1日の総充電量 ≤ daily_cycle_limit × battery_capacity_kWh
```

#### 5.1.2 EPRX1制約
- **クールダウン期間**：連続稼働後の最小休止時間
- **日次稼働上限**：1日あたりの最大稼働スロット数

### 5.2 物理制約

#### 5.2.1 SoC制約
- **最小値**：0 kWh
- **最大値**：`battery_capacity_kWh`
- **EPRX1動作範囲**：40〜60%

#### 5.2.2 出力制約
- **最大充電電力**：`battery_power_kW`
- **最大放電電力**：`battery_power_kW`

---

<div style="page-break-before: always;"></div>

## 6. 月次集計

### 6.1 集計項目

| 項目 | 計算方法 | 単位 |
|------|----------|------|
| **Total_Charge_kWh** | chargeアクションの充電量合計 | kWh |
| **Total_Discharge_kWh** | discharge + eprx3の有効放電量合計 | kWh |
| **Total_Loss_kWh** | バッテリー損失量の合計 | kWh |
| **Total_EPRX3_kWh** | eprx3の有効放電量合計 | kWh |
| **Total_Daily_PnL** | 全スロットPnLの合計 | 円 |

### 6.2 月次費用

| 費用項目 | 計算式 | 説明 |
|----------|---------|------|
| **託送基本料金** | `wheeling_basic_fee × battery_power_kW` | 固定費 |
| **託送使用料** | `wheeling_usage_fee × Total_Loss_kWh` | 損失分に対する従量料金 |
| **再エネ賦課金** | `renewable_energy_surcharge × Total_Loss_kWh` | 損失分に対する賦課金 |

### 6.3 最終利益

```
月次最終利益 (円) = Total_Daily_PnL 
                  - 託送基本料金 
                  - 託送使用料 
                  - 再エネ賦課金
```

---

<div style="page-break-before: always;"></div>

## 7. 計算例

### 7.1 前提条件

- **バッテリー仕様**：
  - 最大電力：100 kW
  - 容量：200 kWh
  - 30分最大充放電量：50 kWh

- **損失率**：
  - バッテリー損失率：5%
  - 送電損失率：3%

### 7.2 充電時の計算例

**シナリオ**：50 kWh充電（charge割合 = 1.0）

1. **充電量**：50 kWh
2. **調達量**：50 ÷ (1 - 0.03) = 51.55 kWh
3. **送電損失**：1.55 kWh
4. **SoC増加**：50 kWh

### 7.3 放電時の計算例

**シナリオ**：50 kWh放電（discharge割合 = 1.0）

1. **放電量**：50 kWh
2. **販売量**：50 × (1 - 0.05) = 47.5 kWh
3. **バッテリー損失**：2.5 kWh
4. **SoC減少**：50 kWh

### 7.4 EPRX3の計算例

**シナリオ**：EPRX3実行

1. **固定放電量**：50 kWh
2. **有効放電量**：50 × (1 - 0.05) = 47.5 kWh
3. **kW価値収入**：100 kW × EPRX3価格
4. **kWh価値収入**：47.5 kWh × インバランス価格

### 7.5 損失の取り扱い

**重要**：託送料金は**バッテリー損失分のみ**に課金

- **充電時の送電損失**：託送料金対象外
- **放電時のバッテリー損失**：託送料金対象（この例では2.5 kWh）

---
