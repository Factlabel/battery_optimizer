"""
optimization.py

このスクリプトは、バッテリーの充放電最適化問題を線形計画法（PuLP）で解くものです。
各スロットにおいて、アクションは以下の5つのうち排他的に一つだけ選択されます：
  - charge: バッテリー充電（送電ロスを補正）
  - discharge: バッテリー放電（内部ロスを考慮）
  - eprx1: EPRX1ブロックとして運用（特定のSoC制約あり）
  - eprx3: EPRX3取引として運用（放電は常に最大値、かつその分だけバッテリー残量が減少し、減少量に対してimbalance単価の報酬が発生）
  - idle: 何もしない

各スロットで、選択されたアクションに応じたエネルギーの入出力がbattery_socの遷移に反映され、最終的な収益（PnL）は各アクションの予測価格と実績価格を用いて計算されます。

Copyright (C) 2025 YourName
"""

import streamlit as st
import pandas as pd
import numpy as np
import pulp

from src.config import WHEELING_DATA, AREA_NUMBER_TO_NAME, RENEWABLE_ENERGY_SURCHARGE

TAX = 1.1  # 税率（例：10%）


def run_optimization(
        target_area_name: str,
        voltage_type: str,
        battery_power_kW: float,
        battery_capacity_kWh: float,
        battery_loss_rate: float,
        daily_cycle_limit: float,
        yearly_cycle_limit: float,
        annual_degradation_rate: float,
        forecast_period: int,
        eprx1_block_size: int,
        eprx1_block_cooldown: int,
        max_daily_eprx1_slots: int,
        df_all: pd.DataFrame
):
    """
    バッテリーの充放電最適化問題を解き、各スロットのアクションとその収益、
    バッテリー残量の推移などの詳細な取引結果を返す。

    入力：
      - df_all: 各スロットの価格予測や実績、imbalanceなどのデータ（CSVから読み込み）
      - その他パラメータはバッテリー性能、制約、地域情報など
    出力：
      - all_transactions: 各スロットの取引詳細のリスト
      - total_profit, final_profit: 全体の収益・最終収益（託送料金控除後）
    """

    # 1) 地域の託送料金・損失率を取得
    wh = WHEELING_DATA["areas"].get(target_area_name, {}).get(voltage_type, {})
    wheeling_loss_rate = wh.get("loss_rate", 0.0)
    wheeling_base_charge = wh.get("wheeling_base_charge", 0.0)
    wheeling_usage_fee = wh.get("wheeling_usage_fee", 0.0)

    # 2) CSV カラムのチェック
    required_cols = {
        "date", "slot",
        "JEPX_prediction", "JEPX_actual",
        "EPRX1_prediction", "EPRX3_prediction",
        "EPRX1_actual", "EPRX3_actual",
        "imbalance"
    }
    if not required_cols.issubset(df_all.columns):
        st.error(f"CSV is missing required columns: {required_cols}")
        return None, None, None

    # 3) データを日付+slotでソート
    df_all.sort_values(by=["date", "slot"], inplace=True, ignore_index=True)
    total_slots = len(df_all)
    num_days = (total_slots + forecast_period - 1) // forecast_period

    carry_over_soc = 0.0
    all_transactions = []
    total_profit = 0.0
    total_cycles_used = 0.0

    # 1スロットあたりの充放電量 (0.5h)
    half_power_kWh = battery_power_kW * 0.5

    # 4) 日ごとのループ
    for day_idx in range(num_days):
        start_i = day_idx * forecast_period
        end_i = min(start_i + forecast_period, total_slots)
        if start_i >= total_slots:
            break

        df_day = df_all.iloc[start_i:end_i].copy()
        df_day.reset_index(drop=True, inplace=True)
        day_slots = len(df_day)
        if day_slots == 0:
            break

        # ---------------------
        # 線形最適化問題の構築
        # ---------------------
        prob = pulp.LpProblem(f"Battery_Optimization_Day{day_idx + 1}", pulp.LpMaximize)

        # 連続変数：charge, discharge（量は0～1の割合で決定）
        charge = pulp.LpVariable.dicts(
            f"charge_day{day_idx + 1}", range(day_slots),
            lowBound=0, upBound=1, cat=pulp.LpContinuous
        )
        discharge = pulp.LpVariable.dicts(
            f"discharge_day{day_idx + 1}", range(day_slots),
            lowBound=0, upBound=1, cat=pulp.LpContinuous
        )
        # EPRX1ブロック開始はis_in_blockで表現（バイナリ変数）
        block_start = pulp.LpVariable.dicts(
            f"block_start_day{day_idx + 1}", range(day_slots),
            cat=pulp.LpBinary
        )
        # バッテリー残量（State of Charge）
        battery_soc = pulp.LpVariable.dicts(
            f"soc_day{day_idx + 1}", range(day_slots + 1),
            lowBound=0, upBound=battery_capacity_kWh,
            cat=pulp.LpContinuous
        )

        M = eprx1_block_size
        C = eprx1_block_cooldown
        bigM = 999999

        # バイナリ変数で各スロットのアクションを決定
        # is_in_block : EPRX1ブロックとして運用（EPRX1）
        # is_charge, is_discharge, is_eprx3, is_idle : その他のアクション
        is_in_block = {}
        is_charge = {}
        is_discharge = {}
        is_eprx3 = {}
        is_idle = {}
        for i in range(day_slots):
            is_in_block[i] = pulp.LpVariable(f"in_block_{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_charge[i] = pulp.LpVariable(f"is_charge_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_discharge[i] = pulp.LpVariable(f"is_discharge_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_eprx3[i] = pulp.LpVariable(f"is_eprx3_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_idle[i] = pulp.LpVariable(f"is_idle_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            # アクションは排他的：どれか1つだけ選択
            prob += is_charge[i] + is_discharge[i] + is_in_block[i] + is_eprx3[i] + is_idle[i] == 1

            # 連続変数はそれぞれのアクションが選択されている場合にのみ正の値を持つ
            prob += charge[i] <= is_charge[i]
            prob += discharge[i] <= is_discharge[i]
            # EPRX3は数量調整不可なので、量は固定（binaryとして扱う）
            # 後のbattery_socの更新で直接使用するので、is_eprx3[i]を用いる

        # (A) is_in_block の定義（EPRX1ブロックの連続性を表す）
        for i in range(day_slots):
            possible_starts = []
            for x in range(max(0, i - (M - 1)), i + 1):
                if x + M - 1 >= i:
                    possible_starts.append(block_start[x])
            prob += is_in_block[i] == pulp.lpSum(possible_starts)

        # (A') EPRX3予測が0またはNaNの場合、EPRX3アクションは不可
        for i in range(day_slots):
            e3pred = df_day.loc[i, "EPRX3_prediction"]
            if pd.isna(e3pred) or e3pred == 0:
                prob += is_eprx3[i] == 0

        # (C) バッテリー残量（SoC）の遷移
        # 充電：charge[i]*half_power_kWh, 放電：discharge[i]*half_power_kWh,
        # EPRX3：固定で half_power_kWh が減少（内部ロスは後で考慮）
        for i in range(day_slots):
            next_soc = battery_soc[i] + charge[i] * half_power_kWh - discharge[i] * half_power_kWh - is_eprx3[i] * half_power_kWh
            prob += battery_soc[i + 1] == next_soc

        # (D) 初期SoCは前日の繰越
        prob += battery_soc[0] == carry_over_soc

        # (E) EPRX1ブロックの制約
        for i in range(day_slots):
            end_j = min(day_slots, i + M + C)
            for j in range(i + 1, end_j):
                prob += block_start[i] + block_start[j] <= 1
            if i > day_slots - M:
                prob += block_start[i] == 0

        # (F) 日次充電量の上限制約
        if daily_cycle_limit > 0:
            daily_charge_sum = pulp.lpSum(charge[i] for i in range(day_slots)) * half_power_kWh
            prob += daily_charge_sum <= daily_cycle_limit * battery_capacity_kWh

        # (G) EPRX1予測が0またはNaNの場合、ブロック開始不可
        for i in range(day_slots):
            for slot_in_block in range(i, min(i + M, day_slots)):
                e1pred = df_day.loc[slot_in_block, "EPRX1_prediction"]
                if pd.isna(e1pred) or e1pred == 0:
                    prob += block_start[i] <= 0

        # (H) EPRX1ブロック中のSoC制約（40～60%の範囲に維持）
        for i in range(day_slots):
            prob += battery_soc[i] >= 0.4 * battery_capacity_kWh - (1 - is_in_block[i]) * bigM
            prob += battery_soc[i] <= 0.6 * battery_capacity_kWh + (1 - is_in_block[i]) * bigM

        # (I) 1日あたりのEPRX1ブロック数の上限制約
        if max_daily_eprx1_slots > 0:
            prob += pulp.lpSum(is_in_block[i] for i in range(day_slots)) <= max_daily_eprx1_slots

        # (J) 目的関数：各スロットの収益を最大化
        # － charge: 購入コスト (JEPX_predictionを用いて送電ロス補正)
        # － discharge: 放電収入（JEPX_prediction × discharge量 × (1–battery_loss_rate)）
        # － EPRX1: 固定出力による収益（EPRX1_prediction × battery_power_kW）
        # － EPRX3: 固定放電（half_power_kWh）により、以下の2要素で収益発生
        #        ・kW価値： battery_power_kW × EPRX3_prediction
        #        ・kWh価値： half_power_kWh×(1–battery_loss_rate) × imbalance
        profit_terms = []
        for i in range(day_slots):
            # 予測価格を取得（NaNの場合は0）
            jpred = df_day.loc[i, "JEPX_prediction"]
            if pd.isna(jpred):
                jpred = 0.0
            e1pred = df_day.loc[i, "EPRX1_prediction"]
            if pd.isna(e1pred):
                e1pred = 0.0
            e3pred = df_day.loc[i, "EPRX3_prediction"]
            if pd.isna(e3pred):
                e3pred = 0.0
            imb = df_day.loc[i, "imbalance"]
            if pd.isna(imb):
                imb = 0.0

            cost_c = jpred * (charge[i] * half_power_kWh / (1 - wheeling_loss_rate))
            rev_d = jpred * (discharge[i] * half_power_kWh * (1 - battery_loss_rate))
            rev_e1 = e1pred * battery_power_kW * is_in_block[i]
            rev_e3 = TAX * is_eprx3[i] * (battery_power_kW * e3pred + half_power_kWh * (1 - battery_loss_rate) * imb)

            slot_profit = -cost_c + rev_d + rev_e1 + rev_e3
            profit_terms.append(slot_profit)
        prob += pulp.lpSum(profit_terms)

        solver = pulp.PULP_CBC_CMD(msg=0, threads=4)
        prob.solve(solver)
        if pulp.LpStatus[prob.status] != "Optimal":
            continue

        # 収益計算と取引結果の出力
        day_profit = 0.0
        final_soc = pulp.value(battery_soc[day_slots])
        carry_over_soc = final_soc

        day_transactions = []
        for i in range(day_slots):
            c_val = pulp.value(charge[i]) if pulp.value(charge[i]) is not None else 0
            d_val = pulp.value(discharge[i]) if pulp.value(discharge[i]) is not None else 0

            if pulp.value(is_in_block[i]) > 0.5:
                act = "eprx1"
            elif pulp.value(is_charge[i]) > 0.5:
                act = "charge"
            elif pulp.value(is_discharge[i]) > 0.5:
                act = "discharge"
            elif pulp.value(is_eprx3[i]) > 0.5:
                act = "eprx3"
            else:
                act = "idle"

            j_a = df_day.loc[i, "JEPX_actual"] if not pd.isna(df_day.loc[i, "JEPX_actual"]) else 0.0
            e1_a = df_day.loc[i, "EPRX1_actual"] if not pd.isna(df_day.loc[i, "EPRX1_actual"]) else 0.0
            e3_a = df_day.loc[i, "EPRX3_actual"] if not pd.isna(df_day.loc[i, "EPRX3_actual"]) else 0.0
            imb_a = df_day.loc[i, "imbalance"] if not pd.isna(df_day.loc[i, "imbalance"]) else 0.0

            if act == "charge":
                c_kwh = c_val * half_power_kWh
                effective_kwh = c_kwh
                loss_kwh = 0.0
                cost = j_a * TAX * (c_kwh / (1 - wheeling_loss_rate))
                slot_jepx_pnl = -cost
                slot_eprx1_pnl = 0.0
                slot_eprx3_pnl = 0.0
            elif act == "discharge":
                d_kwh = d_val * half_power_kWh
                effective_kwh = d_kwh * (1 - battery_loss_rate)
                loss_kwh = d_kwh * battery_loss_rate
                slot_jepx_pnl = j_a * TAX * effective_kwh
                slot_eprx1_pnl = 0.0
                slot_eprx3_pnl = 0.0
            elif act == "eprx1":
                effective_kwh = 0.0
                loss_kwh = 0.0
                slot_eprx1_pnl = e1_a * TAX * battery_power_kW
                slot_jepx_pnl = 0.0
                slot_eprx3_pnl = 0.0
            elif act == "eprx3":
                # EPRX3は数量調整せず、常に最大放電量からロス分を引いた値を使用
                effective_kwh = half_power_kWh * (1 - battery_loss_rate)
                loss_kwh = half_power_kWh * battery_loss_rate
                kW_value = battery_power_kW * e3_a
                kWh_value = half_power_kWh * (1 - battery_loss_rate) * imb_a
                slot_eprx3_pnl = TAX * (kW_value + kWh_value)
                slot_jepx_pnl = 0.0
                slot_eprx1_pnl = 0.0
            else:  # idle
                effective_kwh = 0.0
                loss_kwh = 0.0
                slot_jepx_pnl = 0.0
                slot_eprx1_pnl = 0.0
                slot_eprx3_pnl = 0.0

            slot_total_pnl = slot_jepx_pnl + slot_eprx1_pnl + slot_eprx3_pnl
            day_profit += slot_total_pnl

            row = {
                "date": df_day.loc[i, "date"],
                "slot": int(df_day.loc[i, "slot"]),
                "action": act,
                "battery_level_kWh": round(pulp.value(battery_soc[i + 1]), 2),
                "charge_kWh": round(c_val * half_power_kWh, 3) if act == "charge" else 0,
                "discharge_kWh": round(effective_kwh, 3) if act == "discharge" else 0,
                # EPRX3の場合、ロス分を差し引いた effective_kwh を記録
                "EPRX3_kWh": round(effective_kwh, 3) if act == "eprx3" else 0,
                "loss_kWh": round(loss_kwh, 3),
                "JEPX_actual": round(j_a, 3),
                "EPRX1_actual": round(e1_a, 3),
                "EPRX3_actual": round(e3_a, 3),
                "imbalance": round(imb_a, 3),
                "JEPX_PnL": round(slot_jepx_pnl),
                "EPRX1_PnL": round(slot_eprx1_pnl),
                "EPRX3_PnL": round(slot_eprx3_pnl),
                "Total_Daily_PnL": round(slot_total_pnl)
            }
            day_transactions.append(row)

        all_transactions.extend(day_transactions)
        total_profit += day_profit

        day_charge_kWh = sum(pulp.value(charge[i]) for i in range(day_slots)) * half_power_kWh
        day_cycle_count = day_charge_kWh / battery_capacity_kWh
        total_cycles_used += day_cycle_count

        if (yearly_cycle_limit > 0) and (total_cycles_used > yearly_cycle_limit):
            break

    # 最終利益計算（charge, discharge, eprx3について集計）
    total_charge_kWh = 0.0
    total_discharge_kWh = 0.0
    total_loss_kWh = 0.0
    for r in all_transactions:
        if r["action"] == "charge":
            total_charge_kWh += r["charge_kWh"]
        elif r["action"] == "discharge":
            total_discharge_kWh += r["discharge_kWh"]
            total_loss_kWh += r["loss_kWh"]
        elif r["action"] == "eprx3":
            total_discharge_kWh += r["EPRX3_kWh"]
            total_loss_kWh += r["loss_kWh"]

    usage_fee_kWh = max(0, total_charge_kWh - total_discharge_kWh)
    monthly_fee = wheeling_base_charge * battery_power_kW + wheeling_usage_fee * total_loss_kWh
    final_profit = total_profit - monthly_fee

    return all_transactions, round(total_profit), round(final_profit)


def generate_monthly_summary(
        transactions: list,
        battery_loss_rate: float,
        battery_power_kW: float,
        target_area_name: str,
        voltage_type: str
):
    """
    月別に取引結果を集計し、各項目（充放電量、ロス、収益など）を
    四捨五入した整数値でまとめたDataFrameを返す。
    ただし、_price の項目は小数点以下2位まで表記する。
    また、Total_Imbalance を Total_EPRX3_kWh に変更し、
    Average_EPRX3_Price はactionがeprx3のスロットのEPRX3_actualの平均値とする。
    """
    df = pd.DataFrame(transactions)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["month"] = df["date"].dt.to_period("M").astype(str)
    summary_list = []

    for month, group in df.groupby("month"):
        monthly_charge = group[group["action"] == "charge"]["charge_kWh"].sum()
        effective_discharge = (
            group[group["action"] == "discharge"]["discharge_kWh"].sum() +
            group[group["action"] == "eprx3"]["EPRX3_kWh"].sum()
        )
        total_loss = group["loss_kWh"].sum()
        monthly_total_pnl = group["Total_Daily_PnL"].sum()

        wh = WHEELING_DATA["areas"].get(target_area_name, {}).get(voltage_type, {})
        wheeling_base_charge = wh.get("wheeling_base_charge", 0.0)
        wheeling_usage_fee = wh.get("wheeling_usage_fee", 0.0)
        monthly_wheeling_fee = wheeling_base_charge * battery_power_kW + wheeling_usage_fee * total_loss
        monthly_renewable_energy_surcharge = RENEWABLE_ENERGY_SURCHARGE * total_loss

        action_counts = group["action"].value_counts().to_dict()
        action_counts_str = " ".join(f"{k} {v}" for k, v in action_counts.items())

        charge_group = group[group["action"] == "charge"]
        if charge_group["charge_kWh"].sum() > 0:
            avg_charge_price = charge_group["JEPX_PnL"].sum() / charge_group["charge_kWh"].sum()
        else:
            avg_charge_price = None

        discharge_group = group[group["action"] == "discharge"]
        if discharge_group["discharge_kWh"].sum() > 0:
            avg_discharge_price = discharge_group["JEPX_PnL"].sum() / discharge_group["discharge_kWh"].sum()
        else:
            avg_discharge_price = None

        eprx3_group = group[group["action"] == "eprx3"]
        # Average_EPRX3_Priceは、actionがeprx3のスロットのEPRX3_actualの平均値
        if not eprx3_group.empty:
            avg_eprx3_price = eprx3_group["EPRX3_actual"].mean()
        else:
            avg_eprx3_price = None

        eprx1_group = group[group["action"] == "eprx1"]
        if not eprx1_group.empty:
            avg_eprx1_price = eprx1_group["EPRX1_actual"].mean()
        else:
            avg_eprx1_price = None

        summary_list.append({
            "Month": month,
            "Total_Charge_kWh": round(monthly_charge),
            "Total_Discharge_KWh": round(effective_discharge),
            "Total_Loss_KWh": round(total_loss),
            # Total_Imbalance を Total_EPRX3_kWh に変更：actionがeprx3のスロットのEPRX3_kWhの合計
            "Total_EPRX3_kWh": round(eprx3_group["EPRX3_kWh"].sum()),
            "Total_Daily_PnL": round(monthly_total_pnl),
            "Total_Wheeling_Usage_Fee": round(monthly_wheeling_fee),
            "Total_Renewable_Energy_Surcharge": round(monthly_renewable_energy_surcharge),
            "Action_Counts": action_counts_str,
            "Average_Charge_Price": round(avg_charge_price, 2) if avg_charge_price is not None else None,
            "Average_Discharge_Price": round(avg_discharge_price, 2) if avg_discharge_price is not None else None,
            "Average_EPRX3_Price": round(avg_eprx3_price, 2) if avg_eprx3_price is not None else None,
            "Average_EPRX1_Price": round(avg_eprx1_price, 2) if avg_eprx1_price is not None else None,
        })

    return pd.DataFrame(summary_list)