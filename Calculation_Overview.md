# バッテリー最適化プロジェクト 計算メモ

---

## 1. まず知っておく数字

| 名前 | 意味                    | 例 |
|------|-----------------------|----|
| `battery_power_kW` | 30分で充電/放電できる電気 (kW)   | **100 kW** |
| `battery_capacity_kWh` | 電池に入る電力量の最大値 (kWh)    | **200 kWh** |
| `battery_loss_rate` | バッテリー内部損失             | **0.05 → 5 %** |
| `wheeling_loss_rate` | 送電損失                  | **0.03 → 3 %** |
| `half_power_kWh` | 1スロット (=30分) で動かせる電力量 | `battery_power_kW × 0.5` |

---

## 2. アクション別の電気の動き

1 スロットで必ず **1つだけ** 下のどれかを選びます。

| アクション | 電池の出入り                                          | ポイント                                                                  |
|-----------|-------------------------------------------------|-----------------------------------------------------------------------|
| **charge** (充電) | 調達量 = `charge割合 × half_power_kWh`  <br>ただし送電ロス分多く調達 | 調達量 = 充電量 ÷ (1－`wheeling_loss_rate`)                                  |
| **discharge** (放電) | 放電量 = `discharge割合 × half_power_kWh`            | 販売量 = 放電量 × (1－`battery_loss_rate`)                                   |
| **eprx1** | 30分間一定の出力                                       | 電池残量を **40〜60 %** で保持する                                               |
| **eprx3** | `half_power_kWh` を必ず放電                          | 収入：<br>① kW価値 = `battery_power_kW × 価格`<br>② kWh価値 = 有効kWh × インバランス価格 |
| **idle** | 何もしない                                           | 残量変変化なし                                                               |

---

## 3. 電池残量 (SoC) の計算

```
次の残量 ＝ 現在の残量
　　　　＋ 充電量
　　　　－ 放電量
　　　　－ eprx3固定放電量
```

- **充電量** = `charge率 × half_power_kWh`  
- **放電量** = `discharge率 × half_power_kWh`

---

## 4. 収益 (PnL) の計算

### 4‑1. 充電 (コスト)

```
支払 = JEPX予想価格 × 調達kWh + 消費税
調達kWh = 充電量 ÷ (1－送電ロス率)
```

### 4‑2. 放電 (収入)

```
受取 = JEPX予想価格 × 販売kWh + 消費税
販売kWh = 放電量 × (1－電池ロス率)
```

### 4‑3. EPRX1

```
EPRX収入 = EPRX1予想価格 × battery_power_kW × 税率
```

### 4‑4. EPRX3

```
EPRX収入 = battery_power_kW × EPRX3予想価格
JEPX収入 = 有効kWh × インバランス価格
有効kWh = half_power_kWh × (1－電池ロス率)
収入合計 = (EPRX収入 ＋ JEPX収入) × 税率
```

### 4‑5. スロットPnL

```
PnL = －充電支払 ＋ 放電収入 ＋ EPRX1収入 ＋ EPRX3収入
```

---

## 5. 日ごとの追加チェック

- 1日の充電量が **設定した`daily_cycle_limit × battery_capacity_kWh`** を超えない  
- EPRX1ブロックは **設定したクールダウン** 時間を空ける  
- 1日のEPRX1稼働スロット数は **設定した上限を超えない**

---

## 6. 月末のまとめ

| 項目 | 計算方法                                          |
|------|-----------------------------------------------|
| **Total_Charge_kWh** | `charge` 行の `charge_kWh` の合計                  |
| **Total_Discharge_kWh** | `discharge` 行と `eprx3` 行の有効kWhの合計             |
| **Total_Loss_kWh** | `loss_kWh` の合計                                |
| **Total_EPRX3_kWh** | `eprx3` 行の有効kWhの合計                            |
| **Total_Daily_PnL** | スロットPnLの合計                                    |
| **Wheeling_Usage_Fee** | `wheeling_usage_fee × Total_Loss_kWh`         |
| **Renewable_Energy_Surcharge** | 固定単価 × `Total_Loss_KWh`                       |
| **最終利益** | `Total_Daily_PnL － 基本料金 － Wheeling_Usage_Fee` |

---

## 7. ケーススタディ

- **電池ロス率** 5 %  
- **送電ロス率** 3 %  
- **充電量** 100 kWh

### 調達量 (充電時)

```
100 ÷ (1－0.03) = 103 kWh
```
→ 3 kWh は送電ロス　（100充電するためには103調達する必要がある）

### 売れる量 (放電時)

```
100 × (1－0.05) = 95 kWh
```
→ 5 kWh は電池内部で消える  
→ **この 5 kWh 分にだけ託送料金が発生**

---
