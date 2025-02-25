import streamlit as st
import pandas as pd
import numpy as np
import pulp

from src.config import WHEELING_DATA, AREA_NUMBER_TO_NAME

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

    # -----------------------------

    # 1) 地域の託送料金・損失率を取得
    wh = WHEELING_DATA["areas"].get(target_area_name, {}).get(voltage_type, {})
    wheeling_loss_rate = wh.get("loss_rate", 0.0)
    wheeling_base_charge = wh.get("wheeling_base_charge", 0.0)
    wheeling_usage_fee = wh.get("wheeling_usage_fee", 0.0)

    # 2) CSV カラムのチェック
    required_cols = {
        "date", "slot",
        "JEPX_prediction", "JEPX_actual",
        "EPRX1_prediction", "EPRX1_actual",
        "EPRX3_prediction", "EPRX3_actual",
        "imbalance"
    }
    if not required_cols.issubset(df_all.columns):
        st.error(f"CSV is missing required columns: {required_cols}")
        return None, None, None

    # 3) データを日付+slotでソート
    df_all.sort_values(by=["date", "slot"], inplace=True, ignore_index=True)
    total_slots = len(df_all)

    # 全体スロット数に対し、1日あたり forecast_period スロットとして何日分あるか
    num_days = (total_slots + forecast_period - 1) // forecast_period

    # 状態保持用
    carry_over_soc = 0.0
    all_transactions = []
    total_profit = 0.0
    total_cycles_used = 0.0

    # 放充電量(1スロット=0.5h)
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
        # パラメータ設定 (線形最適化)
        # ---------------------
        prob = pulp.LpProblem(f"Battery_Optimization_Day{day_idx+1}", pulp.LpMaximize)

        charge = pulp.LpVariable.dicts(
            f"charge_day{day_idx+1}", range(day_slots),
            lowBound=0, upBound=1, cat=pulp.LpContinuous
        )
        discharge = pulp.LpVariable.dicts(
            f"discharge_day{day_idx+1}", range(day_slots),
            lowBound=0, upBound=1, cat=pulp.LpContinuous
        )
        eprx3 = pulp.LpVariable.dicts(
            f"eprx3_day{day_idx+1}", range(day_slots),
            lowBound=0, upBound=1, cat=pulp.LpContinuous
        )

        block_start = pulp.LpVariable.dicts(
            f"block_start_day{day_idx+1}", range(day_slots),
            cat=pulp.LpBinary
        )

        battery_soc = pulp.LpVariable.dicts(
            f"soc_day{day_idx+1}", range(day_slots+1),
            lowBound=0, upBound=battery_capacity_kWh,
            cat=pulp.LpContinuous
        )

        M = eprx1_block_size
        C = eprx1_block_cooldown
        bigM = 999999

        is_in_block = {}
        for i in range(day_slots):
            is_in_block[i] = pulp.LpVariable(
                f"in_block_{day_idx+1}_slot{i}",
                cat=pulp.LpBinary
            )

        # (A) is_in_block[i] の定義
        for i in range(day_slots):
            possible_starts = []
            for x in range(max(0, i - (M - 1)), i+1):
                if x + M - 1 >= i:
                    possible_starts.append(block_start[x])
            prob += is_in_block[i] == pulp.lpSum(possible_starts)

        # (A') EPRX3 が 0 or NaN ならスロット使用不可
        for i in range(day_slots):
            e3pred = df_day.loc[i, "EPRX3_prediction"]
            if pd.isna(e3pred) or e3pred == 0:
                prob += eprx3[i] <= 0

        # (B) 同一スロットで EPRX1ブロック中なら 他動作(充電等)禁止
        for i in range(day_slots):
            prob += (charge[i] + discharge[i] + eprx3[i]) <= (1 - is_in_block[i])

        # (C) SoC の遷移
        for i in range(day_slots):
            next_soc = (
                battery_soc[i]
                + charge[i] * half_power_kWh
                - discharge[i] * half_power_kWh
                - eprx3[i] * half_power_kWh
            )
            prob += battery_soc[i+1] == next_soc

        # (D) その日の初期 SoC = 前日繰越
        prob += battery_soc[0] == carry_over_soc

        # (E) EPRX1ブロック終了後のSoC調整
        for i in range(day_slots):
            end_j = min(day_slots, i + M + C)
            for j in range(i+1, end_j):
                prob += block_start[i] + block_start[j] <= 1
            if i > day_slots - M:
                prob += block_start[i] == 0

        # (F) 日次充電量 <= 日次サイクル上限
        if daily_cycle_limit > 0:
            daily_charge_sum = pulp.lpSum(charge[i] for i in range(day_slots)) * half_power_kWh
            prob += daily_charge_sum <= daily_cycle_limit * battery_capacity_kWh

        # (G) EPRX1 の予測値が 0 or NaN ならブロック開始不可
        for i in range(day_slots):
            for slot_in_block in range(i, min(i+M, day_slots)):
                e1pred = df_day.loc[slot_in_block, "EPRX1_prediction"]
                if pd.isna(e1pred) or e1pred == 0:
                    prob += block_start[i] <= 0

        # (H) EPRX1スロット中の SoC は 40〜60% に制限
        for i in range(day_slots):
            prob += battery_soc[i] >= 0.4 * battery_capacity_kWh - (1 - is_in_block[i]) * bigM
            prob += battery_soc[i] <= 0.6 * battery_capacity_kWh + (1 - is_in_block[i]) * bigM

        # (I) 1日あたりの EPRX1スロット最大数
        if max_daily_eprx1_slots > 0:
            prob += pulp.lpSum(is_in_block[i] for i in range(day_slots)) <= max_daily_eprx1_slots

        # (J) 目的関数: 予測価格ベースでの収益最大化
        profit_terms = []
        for i in range(day_slots):
            jpred = df_day.loc[i, "JEPX_prediction"]
            if pd.isna(jpred):
                jpred = 0.0

            cost_c = jpred * (charge[i] * half_power_kWh / (1 - wheeling_loss_rate))
            rev_d = jpred * (discharge[i] * half_power_kWh * (1 - battery_loss_rate))

            e3pred = df_day.loc[i, "EPRX3_prediction"]
            if pd.isna(e3pred):
                e3pred = 0.0
            imb = df_day.loc[i, "imbalance"]
            if pd.isna(imb):
                imb = 0.0

            rev_e3 = e3pred * (eprx3[i] * battery_power_kW)
            rev_e3 += (half_power_kWh * (1 - battery_loss_rate)) * imb * eprx3[i]

            e1pred = df_day.loc[i, "EPRX1_prediction"]
            if pd.isna(e1pred):
                e1pred = 0.0

            rev_e1 = e1pred * (battery_power_kW) * is_in_block[i]

            slot_profit = -cost_c + rev_d + rev_e3 + rev_e1
            profit_terms.append(slot_profit)

        prob += pulp.lpSum(profit_terms)

        solver = pulp.PULP_CBC_CMD(msg=0, threads=4)
        prob.solve(solver)
        status = pulp.LpStatus[prob.status]
        if status != "Optimal":
            continue

        # 実際価格ベースの損益計算
        day_profit = 0.0
        final_soc = pulp.value(battery_soc[day_slots])
        carry_over_soc = final_soc

        TAX = 1.1  # 10%

        day_transactions = []
        for i in range(day_slots):
            c_val = pulp.value(charge[i])
            d_val = pulp.value(discharge[i])
            e3_val = pulp.value(eprx3[i])
            in_b_val = pulp.value(is_in_block[i])

            act = "idle"
            if in_b_val > 0.5:
                act = "EPRX1"
            elif c_val > 0:
                act = "charge"
            elif d_val > 0:
                act = "discharge"
            elif e3_val > 0:
                act = "EPRX3"

            j_a  = df_day.loc[i, "JEPX_actual"]  if not pd.isna(df_day.loc[i, "JEPX_actual"]) else 0.0
            e1_a = df_day.loc[i, "EPRX1_actual"] if not pd.isna(df_day.loc[i, "EPRX1_actual"]) else 0.0
            e3_a = df_day.loc[i, "EPRX3_actual"] if not pd.isna(df_day.loc[i, "EPRX3_actual"]) else 0.0
            imb_a= df_day.loc[i, "imbalance"]    if not pd.isna(df_day.loc[i, "imbalance"])    else 0.0

            c_kwh = c_val * half_power_kWh
            d_kwh = d_val * half_power_kWh
            e3_kwh = e3_val * half_power_kWh

            slot_jepx_pnl = 0.0
            slot_eprx1_pnl = 0.0
            slot_eprx3_pnl = 0.0

            if act == "charge":
                cost = j_a * TAX * (c_kwh / (1 - wheeling_loss_rate))
                slot_jepx_pnl -= cost

            elif act == "discharge":
                rev = j_a * TAX * (d_kwh * (1 - battery_loss_rate))
                slot_jepx_pnl += rev

            elif act == "EPRX3":
                rev = e3_a * TAX * battery_power_kW
                rev += TAX * (e3_kwh * (1 - battery_loss_rate)) * imb_a
                slot_eprx3_pnl += rev

            elif act == "EPRX1":
                rev = e1_a * TAX * battery_power_kW
                slot_eprx1_pnl += rev

            slot_total_pnl = slot_jepx_pnl + slot_eprx1_pnl + slot_eprx3_pnl
            day_profit += slot_total_pnl

            row = {
                "date": df_day.loc[i, "date"],
                "slot": int(df_day.loc[i, "slot"]),
                "action": act,
                "battery_level_kWh": round(pulp.value(battery_soc[i+1]), 2),
                "charge_kWh": round(c_kwh, 3),
                "discharge_kWh": round(d_kwh, 3),
                "EPRX3_kWh": round(e3_kwh, 3),
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

    # 託送料金を差し引いた最終利益計算
    total_charge_kWh = 0.0
    total_discharge_kWh = 0.0
    for r in all_transactions:
        if r["action"] == "charge":
            total_charge_kWh += r["charge_kWh"]
        elif r["action"] == "discharge":
            total_discharge_kWh += r["discharge_kWh"] * (1 - battery_loss_rate)
        elif r["action"] == "EPRX3":
            total_discharge_kWh += r["EPRX3_kWh"] * (1 - battery_loss_rate)

    usage_fee_kWh = max(0, total_charge_kWh - total_discharge_kWh)
    monthly_fee = wheeling_base_charge * battery_power_kW + wheeling_usage_fee * usage_fee_kWh
    final_profit = total_profit - monthly_fee

    return all_transactions, round(total_profit), round(final_profit)