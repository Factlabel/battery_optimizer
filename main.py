import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import pulp

from src.optimization import run_optimization
from src.config import AREA_NUMBER_TO_NAME

def main():
    # ★ ロゴの表示
    st.image("assets/images/LOGO_factlabel.png", width=100)
    st.markdown("<div style='margin-top:-20px;'></div>", unsafe_allow_html=True)
    st.title("Battery Optimizer (Pilot Version)")

    # --------------------------
    #  1) 基本パラメータ入力
    # --------------------------
    st.header("基本パラメータ設定")

    # エリア選択
    selected_area_num = st.selectbox(
        "対象エリア (1-9)",
        options=list(AREA_NUMBER_TO_NAME.keys()),
        format_func=lambda x: f"{x}: {AREA_NUMBER_TO_NAME[x]}"
    )
    target_area_name = AREA_NUMBER_TO_NAME[selected_area_num]

    voltage_type = st.selectbox("電圧区分", ["SHV", "HV", "LV"], index=1)

    battery_power_kW = st.number_input("バッテリー出力(kW)", min_value=10, value=1000, step=100)
    battery_capacity_kWh = st.number_input("バッテリー容量(kWh) *使用可能容量", min_value=10, value=4000, step=100)
    battery_loss_rate = st.number_input("バッテリー損失率 (0.05=5%)", min_value=0.0, max_value=1.0, value=0.05, step=0.01)

    st.subheader("充放電サイクル上限")
    daily_cycle_limit = st.number_input("日次上限 (0=上限なし)", min_value=0, value=1, step=1)
    yearly_cycle_limit = st.number_input("年次上限 (0=上限なし)", min_value=0, value=365, step=1)
    annual_degradation_rate = st.number_input("バッテリー劣化率 (0.03=3%)", min_value=0.0, max_value=1.0, value=0.03, step=0.01)

    forecast_period = st.number_input("予測対象スロット数", min_value=48, value=48, step=48)

    # EPRX1ブロック設定
    st.subheader("EPRX1ブロック設定")
    eprx1_block_size = st.number_input("EPRX1 連続スロット数 (M)", min_value=1, value=3, step=1)
    eprx1_block_cooldown = st.number_input("EPRX1 ブロック終了後のSoC調整スロット数 (C)", min_value=0, value=2, step=1)
    max_daily_eprx1_slots = st.number_input("1日のEPRX1スロット最大数 (0=制限なし)", min_value=0, value=6, step=1)

    # --------------------------
    #  2) CSVテンプレートダウンロード
    # --------------------------
    st.header("CSVテンプレートのダウンロード")
    csv_template = (
        "date,slot,JEPX_prediction,JEPX_actual,EPRX1_prediction,EPRX3_prediction,EPRX1_actual,EPRX3_actual,imbalance\n"
        "2023/4/1,1,6.19,10.5,19.5,0.34,19.5,0.34,10.5\n"
    )

    st.download_button(
        label="CSVテンプレートをダウンロード",
        data=csv_template,
        file_name="csv_template.csv",
        mime="text/csv"
    )

    # --------------------------
    #  3) CSVアップロード
    # --------------------------
    st.header("価格データ (CSV) アップロード")
    data_file = st.file_uploader("DATA_CSV", type=["csv"])

    if "calc_results" not in st.session_state:
        st.session_state["calc_results"] = None
        st.session_state["calc_day_profit"] = 0.0
        st.session_state["calc_final_profit"] = 0.0

    # --------------------------
    #  4) 計算実行
    # --------------------------
    if data_file:
        df_all = pd.read_csv(data_file)
        if "date" in df_all.columns:
            df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")

        if st.button("Calculate"):
            results, day_profit, final_profit = run_optimization(
                target_area_name=target_area_name,
                voltage_type=voltage_type,
                battery_power_kW=battery_power_kW,
                battery_capacity_kWh=battery_capacity_kWh,
                battery_loss_rate=battery_loss_rate,
                daily_cycle_limit=daily_cycle_limit,
                yearly_cycle_limit=yearly_cycle_limit,
                annual_degradation_rate=annual_degradation_rate,
                forecast_period=forecast_period,
                eprx1_block_size=eprx1_block_size,
                eprx1_block_cooldown=eprx1_block_cooldown,
                max_daily_eprx1_slots=max_daily_eprx1_slots,
                df_all=df_all
            )

            if results is None:
                st.warning("No optimal solution found or missing columns.")
            else:
                st.session_state["calc_results"] = results
                st.session_state["calc_day_profit"] = day_profit
                st.session_state["calc_final_profit"] = final_profit

    # --------------------------
    #  5) 結果表示
    # --------------------------
    if st.session_state["calc_results"] is not None:
        results = st.session_state["calc_results"]
        day_profit = st.session_state["calc_day_profit"]
        final_profit = st.session_state["calc_final_profit"]

        st.success("Calculation Completed.")
        st.write(f"**Total Profit(実際価格ベース・税込)**: {day_profit:,d} 円")
        st.write(f"**Final Profit (託送料金控除後・税込)**: {final_profit:,d} 円")

        df_res = pd.DataFrame(results)
        df_res.sort_values(by=["date", "slot"], inplace=True, ignore_index=True)
        st.dataframe(df_res, height=600)

        # グラフ表示
        st.subheader("バッテリー残量と JEPX実際価格 の推移")
        min_date = df_res["date"].min()
        max_date = df_res["date"].max()
        if pd.isnull(min_date) or pd.isnull(max_date):
            st.warning("Date column not found or invalid.")
            return

        default_start = min_date
        default_end = min_date + pd.Timedelta(days=2)
        if default_end > max_date:
            default_end = max_date

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=default_start, min_value=min_date, max_value=max_date)
        with col2:
            end_date = st.date_input("End Date", value=default_end, min_value=min_date, max_value=max_date)

        if start_date > end_date:
            st.warning("Invalid date range.")
            return

        df_g = df_res[
            (df_res["date"] >= pd.to_datetime(start_date)) & (df_res["date"] <= pd.to_datetime(end_date))
        ].copy()
        df_g.reset_index(drop=True, inplace=True)

        if len(df_g) == 0:
            st.warning("No data in the selected date range.")
            return

        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax2 = ax1.twinx()
        x_vals = range(len(df_g))

        # バッテリー残量 (kWh)
        ax1.bar(x_vals, df_g["battery_level_kWh"], color="lightblue", label="Battery(kWh)")

        # JEPX実際価格
        if "JEPX_actual" in df_g.columns:
            ax2.plot(x_vals, df_g["JEPX_actual"], color="red", label="JEPX(Actual)")

        ax1.set_ylabel("Battery Level (kWh)")
        ax2.set_ylabel("JEPX Price")
        ax1.legend(loc="upper left")
        ax2.legend(loc="upper right")
        st.pyplot(fig)

        # ダウンロードボタン
        csv_data = df_res.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name="optimal_transactions.csv",
            mime="text/csv"
        )
    else:
        st.write("ファイルをアップロード後、Calculate ボタンを押してください。")


if __name__ == "__main__":
    main()