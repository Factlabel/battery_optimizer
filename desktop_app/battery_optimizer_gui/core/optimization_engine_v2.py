"""
Battery Optimization Engine v2 for PyQt6 Application

This module contains the enhanced optimization logic with EPRX3 activation probability
and V1 price settings for more realistic simulation.
"""

import pandas as pd
import numpy as np
import pulp
import random
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from typing import Dict, List, Optional, Tuple
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptimizationEngineV2(QThread):
    """
    Enhanced battery optimization engine with EPRX3 probability and V1 pricing
    """
    
    # Qt Signals for progress updates
    progress_updated = pyqtSignal(int)  # Progress percentage (0-100)
    status_updated = pyqtSignal(str)    # Status message
    log_updated = pyqtSignal(str)       # Log message
    optimization_completed = pyqtSignal(dict)  # Results
    optimization_failed = pyqtSignal(str)      # Error message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.optimization_params = {}
        self.price_data = None
        self.is_cancelled = False
        
    def set_parameters(self, params: Dict, data: pd.DataFrame):
        """Set optimization parameters and price data"""
        self.optimization_params = params
        self.price_data = data.copy()
        
    def cancel_optimization(self):
        """Cancel the optimization process"""
        self.is_cancelled = True
        
    def run(self):
        """Main optimization execution (runs in separate thread)"""
        try:
            self.is_cancelled = False
            self.status_updated.emit("最適化を開始しています...")
            self.progress_updated.emit(0)
            
            # Validate input data
            self._validate_input_data()
            self.progress_updated.emit(10)
            
            # Extract parameters
            params = self.optimization_params
            df_all = self.price_data
            
            # Get regional data
            wheeling_data = self._get_wheeling_data(
                params['target_area_name'], 
                params['voltage_type']
            )
            self.progress_updated.emit(20)
            
            # Run optimization
            results = self._run_battery_optimization(params, df_all, wheeling_data)
            self.progress_updated.emit(90)
            
            # Generate summary
            summary = self._generate_summary(results, params, wheeling_data)
            monthly_summary = self._generate_monthly_summary(results, params, wheeling_data)
            self.progress_updated.emit(100)
            
            # Emit results
            self.status_updated.emit("最適化が完了しました！")
            self.log_updated.emit(f"🎉 最適化完了! 総利益: {summary.get('total_profit', 0):.0f}円")
            self.optimization_completed.emit({
                'results': results,
                'summary': summary,
                'monthly_summary': monthly_summary,
                'params': params
            })
            
        except Exception as e:
            error_msg = f"最適化エラー: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.optimization_failed.emit(error_msg)
    
    def _validate_input_data(self):
        """Validate input data and parameters with enhanced checks"""
        if self.price_data is None or self.price_data.empty:
            raise ValueError("価格データが設定されていません")
            
        required_cols = {
            "date", "slot",
            "JEPX_prediction", "JEPX_actual",
            "EPRX1_prediction", "EPRX3_prediction",
            "EPRX1_actual", "EPRX3_actual",
            "imbalance"
        }
        
        missing_cols = required_cols - set(self.price_data.columns)
        if missing_cols:
            # Check if we have critical columns at least
            critical_cols = {"date", "slot", "JEPX_prediction"}
            missing_critical = critical_cols - set(self.price_data.columns)
            
            if missing_critical:
                raise ValueError(f"重要な列が不足しています: {missing_critical}")
            else:
                # Warn about missing non-critical columns and provide defaults
                self.log_updated.emit(f"⚠️ 一部の列が不足していますが、デフォルト値で補完します: {missing_cols}")
                
                # Add missing columns with default values
                if "JEPX_actual" not in self.price_data.columns:
                    self.price_data["JEPX_actual"] = self.price_data["JEPX_prediction"]
                    self.log_updated.emit("📝 JEPX_actual をJEPX_predictionからコピーしました")
                
                if "EPRX1_prediction" not in self.price_data.columns:
                    self.price_data["EPRX1_prediction"] = 0
                    self.log_updated.emit("📝 EPRX1_prediction にデフォルト値(0)を設定しました")
                
                if "EPRX1_actual" not in self.price_data.columns:
                    self.price_data["EPRX1_actual"] = self.price_data.get("EPRX1_prediction", 0)
                    self.log_updated.emit("📝 EPRX1_actual をEPRX1_predictionからコピーしました")
                
                if "EPRX3_prediction" not in self.price_data.columns:
                    self.price_data["EPRX3_prediction"] = 0
                    self.log_updated.emit("📝 EPRX3_prediction にデフォルト値(0)を設定しました")
                
                if "EPRX3_actual" not in self.price_data.columns:
                    self.price_data["EPRX3_actual"] = self.price_data.get("EPRX3_prediction", 0)
                    self.log_updated.emit("📝 EPRX3_actual をEPRX3_predictionからコピーしました")
                
                if "imbalance" not in self.price_data.columns:
                    self.price_data["imbalance"] = self.price_data.get("JEPX_actual", self.price_data["JEPX_prediction"])
                    self.log_updated.emit("📝 imbalance をJEPX価格からコピーしました")
        
        # Log original data shape
        original_rows = len(self.price_data)
        self.log_updated.emit(f"📊 元データ: {original_rows}行, {len(self.price_data.columns)}列")
        
        # 1. Remove rows where any required column has NaN values
        self.log_updated.emit("🧹 Step 1: NaN値を含む行を除去中...")
        clean_mask = pd.notna(self.price_data[list(required_cols)]).all(axis=1)
        clean_data = self.price_data[clean_mask].copy()
        
        removed_rows = original_rows - len(clean_data)
        if removed_rows > 0:
            self.log_updated.emit(f"⚠️ {removed_rows}行を除去しました (NaN値を含む行)")
        
        if clean_data.empty:
            raise ValueError("有効なデータがありません（全行にNaN値が含まれています）")
        
        # Reset index after cleaning
        clean_data = clean_data.reset_index(drop=True)
        
        # 2. Data type conversion and validation
        self.log_updated.emit("🔧 Step 2: データ型を正規化中...")
        numeric_cols = [
            "slot", "JEPX_prediction", "JEPX_actual",
            "EPRX1_prediction", "EPRX3_prediction", 
            "EPRX1_actual", "EPRX3_actual", "imbalance"
        ]
        
        for col in numeric_cols:
            if col in clean_data.columns:
                original_values = clean_data[col].copy()
                clean_data[col] = pd.to_numeric(clean_data[col], errors='coerce')
                
                # Check if conversion introduced new NaNs
                new_nans = pd.isna(clean_data[col]).sum() - pd.isna(original_values).sum()
                if new_nans > 0:
                    self.log_updated.emit(f"⚠️ {col}: {new_nans}個の値が数値変換できませんでした")
                
                # If all values became NaN, try to recover or use defaults
                if pd.isna(clean_data[col]).all():
                    self.log_updated.emit(f"❌ {col}: 全ての値が数値変換に失敗しました")
                    if col == "slot":
                        # Try to generate slot numbers if they're all invalid
                        clean_data[col] = range(1, len(clean_data) + 1)
                        self.log_updated.emit(f"🔧 {col}: 連番で自動生成しました")
                    elif col in ["JEPX_prediction", "JEPX_actual"]:
                        # For price columns, this is more serious
                        raise ValueError(f"{col}の数値変換が全て失敗しました。データの形式を確認してください。")
                    else:
                        # For other columns, use 0 as default
                        clean_data[col] = 0
                        self.log_updated.emit(f"🔧 {col}: デフォルト値(0)で補完しました")
        
        # Remove rows that got NaN during conversion (only for critical columns)
        critical_numeric_cols = ["slot", "JEPX_prediction", "JEPX_actual"]
        available_critical = [col for col in critical_numeric_cols if col in clean_data.columns]
        
        if available_critical:
            critical_clean_mask = pd.notna(clean_data[available_critical]).all(axis=1)
            final_data = clean_data[critical_clean_mask].copy()
            
            final_removed = len(clean_data) - len(final_data)
            if final_removed > 0:
                self.log_updated.emit(f"⚠️ さらに{final_removed}行を除去しました (重要列のNaN値)")
            
            if final_data.empty:
                raise ValueError("有効なデータがありません（重要な価格データに問題があります）")
                
            self.price_data = final_data.reset_index(drop=True)
        else:
            self.price_data = clean_data
        
        final_rows = len(self.price_data)
        self.log_updated.emit(f"✅ Step 3: 最終データ: {final_rows}行 (元の{original_rows}行から{original_rows - final_rows}行除去)")
        
        # 3. Validate parameter ranges and enhanced EPRX3 parameters
        params = self.optimization_params
        
        # Validate EPRX3 probability parameter (new)
        eprx3_activation_rate = params.get('eprx3_activation_rate', 100.0)
        if not (0.0 <= eprx3_activation_rate <= 100.0):
            raise ValueError(f"EPRX3発動率は0-100%の範囲で設定してください: {eprx3_activation_rate}")
        
        # Validate V1 price ratio parameter (new)
        v1_price_ratio = params.get('v1_price_ratio', 100.0)
        if not (0.0 <= v1_price_ratio <= 200.0):
            raise ValueError(f"V1価格比率は0-200%の範囲で設定してください: {v1_price_ratio}")
        
        # Log new parameters
        self.log_updated.emit(f"🎲 EPRX3発動率: {eprx3_activation_rate:.1f}%")
        self.log_updated.emit(f"💰 V1価格比率: {v1_price_ratio:.1f}%")
        
        # Validate battery parameters
        if params.get('battery_power_kW', 0) <= 0:
            raise ValueError("バッテリー定格出力は正の値である必要があります")
        if params.get('battery_capacity_kWh', 0) <= 0:
            raise ValueError("バッテリー容量は正の値である必要があります")
        if not (0 <= params.get('battery_loss_rate', 0) < 1):
            raise ValueError("バッテリーロス率は0以上1未満である必要があります")
        
        # Check for date column format
        try:
            self.price_data['date'] = pd.to_datetime(self.price_data['date'], errors='raise')
        except Exception as e:
            raise ValueError(f"日付列の形式が不正です: {str(e)}")
        
        # Check slot values
        if self.price_data['slot'].min() < 1 or self.price_data['slot'].max() > 48:
            self.log_updated.emit("⚠️ スロット番号が1-48の範囲外の値を含んでいます")
        
        self.log_updated.emit("✅ データ検証完了")
    
    def _get_wheeling_data(self, area_name: str, voltage_type: str) -> Dict:
        """Get wheeling fee data for the specified area and voltage"""
        try:
            from config.area_config import get_area_wheeling_data
            wheeling_data = get_area_wheeling_data(area_name, voltage_type)
            self.log_updated.emit(f"📍 託送データ取得: {area_name}, {voltage_type}")
            return wheeling_data
        except ImportError:
            # Fallback values if config is not available
            self.log_updated.emit("⚠️ 託送データ設定が見つかりません。デフォルト値を使用します")
            return {
                "wheeling_base_charge": 500.0,
                "wheeling_usage_fee": 1.86,
                "loss_rate": 0.03
            }
        except Exception as e:
            self.log_updated.emit(f"⚠️ 託送データ取得エラー: {str(e)}。デフォルト値を使用します")
            return {
                "wheeling_base_charge": 500.0,
                "wheeling_usage_fee": 1.86,
                "loss_rate": 0.03
            }
    
    def _run_battery_optimization(self, params: Dict, df_all: pd.DataFrame, 
                                wheeling_data: Dict) -> List[Dict]:
        """Run the complete battery optimization across all days"""
        
        self.status_updated.emit("最適化計算を実行中...")
        
        # Sort by date and slot
        df_sorted = df_all.sort_values(['date', 'slot']).reset_index(drop=True)
        
        # Group by date
        unique_dates = df_sorted['date'].dt.date.unique()
        total_days = len(unique_dates)
        
        self.log_updated.emit(f"📅 最適化期間: {total_days}日間 ({unique_dates[0]} から {unique_dates[-1]})")
        
        all_results = []
        current_soc = params.get('initial_soc_kwh', params['battery_capacity_kWh'] * 0.5)
        
        for day_idx, target_date in enumerate(unique_dates):
            if self.is_cancelled:
                raise InterruptedException("最適化がキャンセルされました")
            
            # Get data for this day
            day_mask = df_sorted['date'].dt.date == target_date
            df_day = df_sorted[day_mask].copy().reset_index(drop=True)
            
            if df_day.empty:
                self.log_updated.emit(f"⚠️ Day {day_idx + 1}: データなし")
                continue
            
            try:
                # Solve optimization for this day
                day_results, final_soc = self._solve_daily_optimization(
                    df_day, params, wheeling_data, current_soc, day_idx
                )
                
                all_results.extend(day_results)
                current_soc = final_soc
                
                # Update progress
                progress = 20 + int((day_idx + 1) / total_days * 70)
                self.progress_updated.emit(progress)
                
                if day_idx % max(1, total_days // 10) == 0:  # Log every 10% of days
                    self.status_updated.emit(f"Day {day_idx + 1}/{total_days} 完了")
                
            except Exception as e:
                error_msg = f"Day {day_idx + 1} 最適化エラー: {str(e)}"
                self.log_updated.emit(f"❌ {error_msg}")
                # Continue with other days instead of failing completely
                continue
        
        if not all_results:
            raise ValueError("最適化結果が得られませんでした")
        
        self.log_updated.emit(f"✅ 最適化完了: {len(all_results)}スロットの結果を生成")
        return all_results
    
    def _solve_daily_optimization(self, df_day: pd.DataFrame, params: Dict, 
                                wheeling_data: Dict, initial_soc: float, 
                                day_idx: int) -> Tuple[List[Dict], float]:
        """Solve optimization for a single day with EPRX3 probability consideration"""
        
        day_slots = len(df_day)
        battery_power_kW = params['battery_power_kW']
        battery_capacity_kWh = params['battery_capacity_kWh']
        battery_loss_rate = params['battery_loss_rate']
        half_power_kWh = battery_power_kW * 0.5
        wheeling_loss_rate = wheeling_data.get("loss_rate", 0.0)
        
        # Add debugging mode - now fixed to 'full' for maximum accuracy
        DEBUG_MODE = 'full'  # Always use full mode for complete optimization
        
        # Create optimization problem
        prob = pulp.LpProblem(f"Battery_Optimization_Day{day_idx + 1}", pulp.LpMaximize)
        
        # Decision variables
        charge = pulp.LpVariable.dicts(
            f"charge_day{day_idx + 1}", range(day_slots),
            lowBound=0, upBound=1, cat=pulp.LpContinuous
        )
        discharge = pulp.LpVariable.dicts(
            f"discharge_day{day_idx + 1}", range(day_slots),
            lowBound=0, upBound=1, cat=pulp.LpContinuous
        )
        
        # Binary variables for action selection
        is_charge = {}
        is_discharge = {}
        is_eprx3 = {}
        is_idle = {}
        
        for i in range(day_slots):
            is_charge[i] = pulp.LpVariable(f"is_charge_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_discharge[i] = pulp.LpVariable(f"is_discharge_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_eprx3[i] = pulp.LpVariable(f"is_eprx3_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_idle[i] = pulp.LpVariable(f"is_idle_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            
            # Link continuous and binary variables
            prob += charge[i] <= is_charge[i]
            prob += discharge[i] <= is_discharge[i]
        
        # SOC variables
        battery_soc = pulp.LpVariable.dicts(
            f"soc_day{day_idx + 1}", range(day_slots + 1),
            lowBound=0, upBound=battery_capacity_kWh,
            cat=pulp.LpContinuous
        )
        
        # Initial SOC constraint
        prob += battery_soc[0] == initial_soc
        self.log_updated.emit(f"Day {day_idx + 1}: initial_soc = {initial_soc}, day_slots = {day_slots}, mode = FULL")
        
        # SOC transition constraints
        for i in range(day_slots):
            next_soc = (battery_soc[i] + 
                       charge[i] * half_power_kWh - 
                       discharge[i] * half_power_kWh - 
                       is_eprx3[i] * half_power_kWh)
            prob += battery_soc[i + 1] == next_soc
        
        # Apply daily cycle limit constraint
        daily_cycle_limit = params.get('daily_cycle_limit', 0)
        if daily_cycle_limit > 0:
            daily_charge_sum = pulp.lpSum(charge[i] for i in range(day_slots)) * half_power_kWh
            prob += daily_charge_sum <= daily_cycle_limit * battery_capacity_kWh
            if day_idx < 3:  # Only log first few days to reduce overhead
                self.log_updated.emit(f"Day {day_idx + 1}: 日次サイクル制限適用 - {daily_cycle_limit} cycles")
        
        # EPRX1 block functionality (Full mode implementation)
        self.log_updated.emit(f"Using FULL mode: all EPRX1 constraints and features")
        
        # EPRX1 block parameters
        M = params.get('eprx1_block_size', 4)  # Default 4 slots (2 hours)
        C = params.get('eprx1_block_cooldown', 4)  # Default 4 slots cooldown
        
        # EPRX1 block start variables
        block_start = pulp.LpVariable.dicts(
            f"block_start_day{day_idx + 1}", range(day_slots),
            cat=pulp.LpBinary
        )
        
        # EPRX1 block participation
        is_in_block = {}
        for i in range(day_slots):
            is_in_block[i] = pulp.LpVariable(f"in_block_{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            
            # Exclusive action constraint (with all 5 actions)
            prob += is_charge[i] + is_discharge[i] + is_in_block[i] + is_eprx3[i] + is_idle[i] == 1
        
        # EPRX1 block continuity constraints
        for i in range(day_slots):
            possible_starts = []
            for x in range(max(0, i - (M - 1)), i + 1):
                if x + M - 1 >= i:
                    possible_starts.append(block_start[x])
            prob += is_in_block[i] == pulp.lpSum(possible_starts)
        
        # EPRX1 block cooldown constraints
        for i in range(day_slots):
            end_j = min(day_slots, i + M + C)
            for j in range(i + 1, end_j):
                prob += block_start[i] + block_start[j] <= 1
            if i > day_slots - M:
                prob += block_start[i] == 0
        
        # EPRX1 prediction constraint: cannot start block if prediction is 0 or NaN
        for i in range(day_slots):
            for slot_in_block in range(i, min(i + M, day_slots)):
                row = df_day.iloc[slot_in_block]
                e1pred = row.get('EPRX1_prediction', 0)
                if pd.isna(e1pred) or e1pred == 0:
                    prob += block_start[i] <= 0
        
        # Daily EPRX1 block limit
        max_daily_eprx1_slots = params.get('max_daily_eprx1_slots', 0)
        if max_daily_eprx1_slots > 0:
            prob += pulp.lpSum(is_in_block[i] for i in range(day_slots)) <= max_daily_eprx1_slots
        
        # EPRX1 SoC constraints (40-60% range when EPRX1 is active)
        bigM = 999999
        for i in range(day_slots):
            # When EPRX1 is active, SoC must be between 40-60%
            prob += battery_soc[i] >= 0.4 * battery_capacity_kWh - (1 - is_in_block[i]) * bigM
            prob += battery_soc[i] <= 0.6 * battery_capacity_kWh + (1 - is_in_block[i]) * bigM
        
        # Prevent actions when prediction prices are invalid
        for i in range(day_slots):
            row = df_day.iloc[i]
            # EPRX3 constraint: cannot use if prediction is 0 or NaN
            e3pred = row.get('EPRX3_prediction', 0)
            if pd.isna(e3pred) or e3pred == 0:
                prob += is_eprx3[i] == 0
        
        # Objective function (complete with all markets)
        TAX = 1.1
        profit_terms = []
        
        for i in range(day_slots):
            row = df_day.iloc[i]
            
            # Get prediction prices (NaN defaults to 0)
            jpred = row.get('JEPX_prediction', 0.0)
            if pd.isna(jpred):
                jpred = 0.0
            e1pred = row.get('EPRX1_prediction', 0.0) 
            if pd.isna(e1pred):
                e1pred = 0.0
            e3pred = row.get('EPRX3_prediction', 0.0)
            if pd.isna(e3pred):
                e3pred = 0.0
            imb = row.get('imbalance', 0.0)
            if pd.isna(imb):
                imb = 0.0
            
            # Charging cost (NO TAX - exactly like Streamlit)
            cost_c = jpred * (charge[i] * half_power_kWh / (1 - wheeling_loss_rate))
            
            # Discharging revenue (NO TAX - exactly like Streamlit) 
            rev_d = jpred * (discharge[i] * half_power_kWh * (1 - battery_loss_rate))
            
            # EPRX1 revenue (NO TAX - exactly like Streamlit)
            rev_e1 = e1pred * battery_power_kW * is_in_block[i]
            
            # EPRX3 revenue with probability consideration
            # kW price: always received (100% certain)
            # kWh price: received only when activated (probability-weighted)
            eprx3_activation_rate = params.get('eprx3_activation_rate', 100.0) / 100.0  # Convert to ratio
            v1_price_ratio = params.get('v1_price_ratio', 100.0) / 100.0  # Convert to ratio
            v1_price = imb * v1_price_ratio  # V1 price for kWh component
            
            kw_revenue = TAX * battery_power_kW * e3pred  # Always received
            kwh_revenue = TAX * half_power_kWh * (1 - battery_loss_rate) * v1_price * eprx3_activation_rate  # Probability-weighted
            
            # Log optimization calculation for first few slots of first day
            if i < 3 and day_idx < 1:
                self.log_updated.emit(f"🔍 最適化 Slot {i}: EPRX3期待値計算")
                self.log_updated.emit(f"  kW価格(確実): {kw_revenue:.2f} = {TAX} × {battery_power_kW} × {e3pred:.2f}")
                self.log_updated.emit(f"  kWh価格(期待値): {kwh_revenue:.2f} = {TAX} × {half_power_kWh} × {v1_price:.2f} × {eprx3_activation_rate:.2f}")
                self.log_updated.emit(f"  EPRX3合計期待値: {kw_revenue + kwh_revenue:.2f}")
            
            rev_e3 = is_eprx3[i] * (kw_revenue + kwh_revenue)
            
            slot_profit = -cost_c + rev_d + rev_e1 + rev_e3
            profit_terms.append(slot_profit)
        
        prob += pulp.lpSum(profit_terms)
        
        # Solve the problem
        try:
            # Try COIN_CMD solver first (better compatibility on macOS) - NO TIME LIMIT like Streamlit
            start_time = time.time()
            try:
                prob.solve(pulp.COIN_CMD(msg=0))  # Remove time limit for better optimization
            except:
                # Fallback to HiGHS solver
                try:
                    prob.solve(pulp.HiGHS_CMD(msg=0))  # Remove time limit here too
                except:
                    # Final fallback to default solver
                    prob.solve()
            
            solve_time = time.time() - start_time
            self.log_updated.emit(f"Optimization status: {pulp.LpStatus[prob.status]} (solved in {solve_time:.2f}s)")
            
            if prob.status != pulp.LpStatusOptimal:
                raise RuntimeError(f"最適解が見つかりません。ステータス: {pulp.LpStatus[prob.status]}")
                
        except Exception as e:
            raise RuntimeError(f"ソルバーエラー: {str(e)}")
        
        # Extract results with EPRX3 probability consideration
        day_results = []
        
        # Initialize actual SOC tracking (different from optimization SOC due to EPRX3 activation)
        actual_soc = [initial_soc]  # Track actual SOC considering EPRX3 activation
        
        for i in range(day_slots):
            row = df_day.iloc[i]
            
            # Get solver values
            c_val = pulp.value(charge[i]) if pulp.value(charge[i]) is not None else 0
            d_val = pulp.value(discharge[i]) if pulp.value(discharge[i]) is not None else 0
            
            # Define thresholds for numerical precision
            THRESHOLD = 1e-6  # Very small threshold for numerical precision
            
            # Determine the selected action based on binary variables AND actual values
            action = "idle"  # Default action
            eprx3_activated = False  # Default EPRX3 activation status
            
            # Check EPRX1 first (if not in simple mode)
            if pulp.value(is_in_block[i]) > 0.5:
                action = "eprx1"
            # Check EPRX3 - apply probability but maintain action type
            elif pulp.value(is_eprx3[i]) > 0.5:
                action = "eprx3"
                # Store activation status for PnL calculation
                eprx3_activation_rate = params.get('eprx3_activation_rate', 100.0)
                eprx3_activated = random.random() * 100 <= eprx3_activation_rate
                if not eprx3_activated:
                    self.log_updated.emit(f"Slot {i}: EPRX3選択、kW価格のみ受領 ({eprx3_activation_rate:.1f}%発動率)")
            # Check charge (binary variable AND actual charge amount)
            elif pulp.value(is_charge[i]) > 0.5 and c_val > THRESHOLD:
                action = "charge"
            # Check discharge (binary variable AND actual discharge amount)  
            elif pulp.value(is_discharge[i]) > 0.5 and d_val > THRESHOLD:
                action = "discharge"
            # Default to idle if no significant action
            else:
                action = "idle"
            
            # Calculate energy flows according to action type
            j_a = row.get('JEPX_actual', 0.0) if not pd.isna(row.get('JEPX_actual', 0.0)) else 0.0
            e1_a = row.get('EPRX1_actual', 0.0) if not pd.isna(row.get('EPRX1_actual', 0.0)) else 0.0
            e3_a = row.get('EPRX3_actual', 0.0) if not pd.isna(row.get('EPRX3_actual', 0.0)) else 0.0
            imb_a = row.get('imbalance', 0.0) if not pd.isna(row.get('imbalance', 0.0)) else 0.0
            
            # Use exact same logic as original but with EPRX3 modifications
            if action == "charge":
                c_kwh = c_val * half_power_kWh
                effective_kwh = c_kwh
                loss_kwh = 0.0
            elif action == "discharge":
                d_kwh = d_val * half_power_kWh
                effective_kwh = d_kwh * (1 - battery_loss_rate)
                loss_kwh = d_kwh * battery_loss_rate
            elif action == "eprx1":
                c_kwh = 0.0  # No charging in EPRX1
                effective_kwh = 0.0
                loss_kwh = 0.0
            elif action == "eprx3":
                c_kwh = 0.0  # No charging in EPRX3
                # EPRX3: only discharge if actually activated
                if eprx3_activated:
                    effective_kwh = half_power_kWh * (1 - battery_loss_rate)
                    loss_kwh = half_power_kWh * battery_loss_rate
                else:
                    # Not activated: no actual discharge
                    effective_kwh = 0.0
                    loss_kwh = 0.0
            else:  # idle
                c_kwh = 0.0
                effective_kwh = 0.0
                loss_kwh = 0.0
            
            # Calculate actual SOC considering EPRX3 activation status
            previous_soc = actual_soc[i]
            
            if action == "charge":
                next_soc = previous_soc + c_kwh
            elif action == "discharge":
                next_soc = previous_soc - (effective_kwh + loss_kwh)
            elif action == "eprx1":
                next_soc = previous_soc  # No SOC change for EPRX1
            elif action == "eprx3":
                if eprx3_activated:
                    next_soc = previous_soc - (effective_kwh + loss_kwh)
                else:
                    next_soc = previous_soc  # No SOC change if not activated
            else:  # idle
                next_soc = previous_soc  # No SOC change
            
            # Ensure SOC stays within bounds
            next_soc = max(0, min(battery_capacity_kWh, next_soc))
            actual_soc.append(next_soc)
            current_soc = next_soc
            
            # Debug logging (reduce for performance)
            if i < 3 and day_idx < 2:  # Only log first few slots of first few days
                self.log_updated.emit(f"Slot {i}: action={action}, current_soc={current_soc:.1f}")
                self.log_updated.emit(f"  c_val={c_val:.6f} (binary={pulp.value(is_charge[i]):.1f}), d_val={d_val:.6f} (binary={pulp.value(is_discharge[i]):.1f})")
                self.log_updated.emit(f"  charge_kWh={c_kwh:.3f}, effective_kwh={effective_kwh:.3f}")
                if action == "eprx3":
                    activation_status = "発動" if eprx3_activated else "非発動"
                    self.log_updated.emit(f"  EPRX3 {activation_status}: 前SOC={previous_soc:.1f} → 後SOC={current_soc:.1f}")
            
            # Calculate PnL components with V2 logic (EPRX3 probability and V1 pricing)
            pnl_data = self._calculate_slot_pnl_v2(
                action, c_kwh if action == "charge" else 0,
                effective_kwh if action == "discharge" else 0,
                effective_kwh if action == "eprx3" else 0,
                row, battery_loss_rate, wheeling_loss_rate, battery_power_kW, params, eprx3_activated
            )
            
            result = {
                'date': row['date'],
                'slot': int(row['slot']) if not pd.isna(row['slot']) else 0,
                'action': action,
                'battery_level_kWh': round(current_soc, 2),
                'charge_kWh': round(c_kwh, 3) if action == "charge" else 0,
                'discharge_kWh': round(effective_kwh, 3) if action == "discharge" else 0,
                'EPRX3_kWh': round(effective_kwh, 3) if action == "eprx3" and eprx3_activated else 0,
                'loss_kWh': round(loss_kwh, 3),
                'JEPX_actual': round(j_a, 3) if not pd.isna(j_a) else 0.0,
                'EPRX1_actual': round(e1_a, 3) if not pd.isna(e1_a) else 0.0,
                'EPRX3_actual': round(e3_a, 3) if not pd.isna(e3_a) else 0.0,
                'imbalance': round(imb_a, 3) if not pd.isna(imb_a) else 0.0,
                'JEPX_PnL': pnl_data['JEPX_PnL'],
                'EPRX1_PnL': pnl_data['EPRX1_PnL'],
                'EPRX3_PnL': pnl_data['EPRX3_PnL'],
                'Total_Daily_PnL': pnl_data['Total_Daily_PnL'],
                'JEPX_prediction': row.get('JEPX_prediction', 0) if not pd.isna(row.get('JEPX_prediction', 0)) else 0.0,
                'EPRX1_prediction': row.get('EPRX1_prediction', 0) if not pd.isna(row.get('EPRX1_prediction', 0)) else 0.0,
                'EPRX3_prediction': row.get('EPRX3_prediction', 0) if not pd.isna(row.get('EPRX3_prediction', 0)) else 0.0
            }
            
            day_results.append(result)
        
        # Calculate actual cycle usage from optimization results
        total_charge_kWh = sum(r['charge_kWh'] for r in day_results)
        actual_cycles = total_charge_kWh / battery_capacity_kWh if battery_capacity_kWh > 0 else 0
        
        # Check against constraint (reduce logging for performance)
        daily_cycle_limit = params.get('daily_cycle_limit', 0)
        if daily_cycle_limit > 0 and day_idx < 3:  # Only log first few days
            if actual_cycles > daily_cycle_limit + 0.001:  # Small tolerance for floating point
                self.log_updated.emit(f"⚠️ Day {day_idx + 1}: 制約違反検知 - 実績サイクル {actual_cycles:.3f} > 制限 {daily_cycle_limit}")
        
        # Get final SOC for next day initialization (use actual SOC, not optimization SOC)
        final_soc = actual_soc[-1]  # Last element of actual SOC array
        optimization_final_soc = pulp.value(battery_soc[day_slots]) if battery_soc[day_slots].value() is not None else initial_soc
        
        if day_idx < 3:  # Only log first few days
            self.log_updated.emit(f"Day {day_idx + 1}: 最適化SOC = {optimization_final_soc:.1f}, 実際SOC = {final_soc:.1f}")
            if abs(final_soc - optimization_final_soc) > 0.1:  # Significant difference
                self.log_updated.emit(f"⚠️ SOC差異検出: EPRX3非発動による差 {final_soc - optimization_final_soc:.1f} kWh")
        
        return day_results, final_soc
    
    def _calculate_slot_pnl_v2(self, action: str, charge_kWh: float, discharge_kWh: float,
                          eprx3_kWh: float, row: pd.Series, battery_loss_rate: float,
                          wheeling_loss_rate: float, battery_power_kW: float, params: Dict, eprx3_activated: bool = True) -> Dict[str, float]:
        """Calculate PnL for a single slot with V2 enhancements (V1 pricing for EPRX3)"""
        
        TAX = 1.1
        
        # Get actual prices (not prediction!)
        j_a = row.get('JEPX_actual', 0.0) if not pd.isna(row.get('JEPX_actual', 0.0)) else 0.0
        e1_a = row.get('EPRX1_actual', 0.0) if not pd.isna(row.get('EPRX1_actual', 0.0)) else 0.0
        e3_a = row.get('EPRX3_actual', 0.0) if not pd.isna(row.get('EPRX3_actual', 0.0)) else 0.0
        imb_a = row.get('imbalance', 0.0) if not pd.isna(row.get('imbalance', 0.0)) else 0.0
        
        # Initialize PnL components
        slot_jepx_pnl = 0.0
        slot_eprx1_pnl = 0.0
        slot_eprx3_pnl = 0.0
        
        if action == "charge":
            c_kwh = charge_kWh
            cost = j_a * TAX * (c_kwh / (1 - wheeling_loss_rate))
            slot_jepx_pnl = -cost
        elif action == "discharge":
            d_kwh = discharge_kWh / (1 - battery_loss_rate)  # Reverse calculate original discharge
            effective_kwh = d_kwh * (1 - battery_loss_rate)
            slot_jepx_pnl = j_a * TAX * effective_kwh
        elif action == "eprx1":
            slot_eprx1_pnl = e1_a * TAX * battery_power_kW
        elif action == "eprx3":
            # Enhanced EPRX3 calculation with probability consideration
            v1_price_ratio = params.get('v1_price_ratio', 100.0) / 100.0  # Convert percentage to ratio
            
            # Calculate V1 price (V1価格 = インバランス価格 × V1価格比率)
            v1_price = imb_a * v1_price_ratio
            
            # EPRX3 PnL calculation:
            # - kW price: always received regardless of activation
            # - kWh price: only received when activated
            kW_value = battery_power_kW * e3_a  # Always received
            kWh_value = eprx3_kWh * v1_price if eprx3_activated else 0  # Only when activated
            slot_eprx3_pnl = TAX * (kW_value + kWh_value)
            
            # Log activation status for debugging (only for first few slots)
            if row.name is not None and row.name < 3:  # Only log first few slots
                activation_status = "発動" if eprx3_activated else "非発動"
                self.log_updated.emit(f"Slot {row.name}: EPRX3 {activation_status} - kW価格:{kW_value:.2f}, kWh価格:{kWh_value:.2f}, 合計:{slot_eprx3_pnl:.2f}")
        # idle: all PnL components remain 0
        
        slot_total_pnl = slot_jepx_pnl + slot_eprx1_pnl + slot_eprx3_pnl
        
        return {
            'JEPX_PnL': round(slot_jepx_pnl),
            'EPRX1_PnL': round(slot_eprx1_pnl),
            'EPRX3_PnL': round(slot_eprx3_pnl),
            'Total_Daily_PnL': round(slot_total_pnl)
        }
    
    def _generate_summary(self, results: List[Dict], params: Dict, 
                         wheeling_data: Dict) -> Dict:
        """Generate optimization summary"""
        
        if not results:
            return {}
        
        df_results = pd.DataFrame(results)
        
        # Calculate totals
        total_charge_kWh = df_results['charge_kWh'].sum()
        total_discharge_kWh = df_results['discharge_kWh'].sum()
        total_eprx3_kWh = df_results['EPRX3_kWh'].sum()
        total_loss_kWh = df_results['loss_kWh'].sum()
        
        # Calculate total PnL from results (PnL already calculated per slot)
        total_daily_pnl = df_results['Total_Daily_PnL'].sum()
        
        # Calculate monthly fees
        battery_power_kW = params['battery_power_kW']
        wheeling_base_charge = wheeling_data.get("wheeling_base_charge", 0) * battery_power_kW
        wheeling_usage_fee = wheeling_data.get("wheeling_usage_fee", 0) * total_loss_kWh
        
        # Use modified renewable energy surcharge if available
        if hasattr(self.parent(), 'get_current_surcharge'):
            renewable_energy_surcharge = self.parent().get_current_surcharge() * total_loss_kWh
        else:
            renewable_energy_surcharge = 3.49 * total_loss_kWh  # Fixed rate
        
        final_profit = total_daily_pnl - wheeling_base_charge - wheeling_usage_fee - renewable_energy_surcharge
        
        # Calculate EPRX3 activation statistics
        eprx3_planned_count = len(df_results[df_results['action'] == 'eprx3'])
        eprx3_activation_rate = params.get('eprx3_activation_rate', 100.0)
        v1_price_ratio = params.get('v1_price_ratio', 100.0)
        initial_soc_kwh = params.get('initial_soc_kwh', params['battery_capacity_kWh'] * 0.5)
        
        summary = {
            'Total_Charge_kWh': total_charge_kWh,
            'Total_Discharge_kWh': total_discharge_kWh,
            'Total_Loss_kWh': total_loss_kWh,
            'Total_EPRX3_kWh': total_eprx3_kWh,
            'Total_Daily_PnL': total_daily_pnl,
            'Wheeling_Basic_Fee': wheeling_base_charge,
            'Wheeling_Usage_Fee': wheeling_usage_fee,
            'Renewable_Energy_Surcharge': renewable_energy_surcharge,
            'Final_Profit': final_profit,
            'Total_Slots': len(results),
            'EPRX3_Planned_Count': eprx3_planned_count,
            'EPRX3_Activation_Rate': eprx3_activation_rate,
            'V1_Price_Ratio': v1_price_ratio,
            'Initial_SOC_kWh': initial_soc_kwh,
            'Optimization_Success': True
        }
        
        return summary

    def _generate_monthly_summary(self, results: List[Dict], params: Dict, 
                                 wheeling_data: Dict) -> pd.DataFrame:
        """Generate monthly summary with V2 enhancements"""
        
        if not results:
            return pd.DataFrame()
        
        # Import here to avoid circular imports
        try:
            from config.area_config import RENEWABLE_ENERGY_SURCHARGE
        except ImportError:
            RENEWABLE_ENERGY_SURCHARGE = 3.49
        
        df = pd.DataFrame(results)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["month"] = df["date"].dt.to_period("M").astype(str)
        summary_list = []

        battery_power_kW = params['battery_power_kW']
        target_area_name = params['target_area_name']
        voltage_type = params['voltage_type']
        eprx3_activation_rate = params.get('eprx3_activation_rate', 100.0)
        v1_price_ratio = params.get('v1_price_ratio', 100.0)
        
        for month, group in df.groupby("month"):
            monthly_charge = group[group["action"] == "charge"]["charge_kWh"].sum()
            effective_discharge = (
                group[group["action"] == "discharge"]["discharge_kWh"].sum() +
                group[group["action"] == "eprx3"]["EPRX3_kWh"].sum()
            )
            total_loss = group["loss_kWh"].sum()
            monthly_total_pnl = group["Total_Daily_PnL"].sum()

            wheeling_base_charge = wheeling_data.get("wheeling_base_charge", 0.0)
            wheeling_usage_fee = wheeling_data.get("wheeling_usage_fee", 0.0)
            monthly_wheeling_fee = wheeling_base_charge * battery_power_kW + wheeling_usage_fee * total_loss
            
            # Use modified renewable energy surcharge if available
            if hasattr(self.parent(), 'get_current_surcharge'):
                monthly_renewable_energy_surcharge = self.parent().get_current_surcharge() * total_loss
            else:
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
            if not eprx3_group.empty:
                avg_eprx3_price = eprx3_group["EPRX3_actual"].mean()
                monthly_eprx3_count = len(eprx3_group)
            else:
                avg_eprx3_price = None
                monthly_eprx3_count = 0

            eprx1_group = group[group["action"] == "eprx1"]
            if not eprx1_group.empty:
                avg_eprx1_price = eprx1_group["EPRX1_actual"].mean()
            else:
                avg_eprx1_price = None

            monthly_net_profit = monthly_total_pnl - monthly_wheeling_fee - monthly_renewable_energy_surcharge

            summary_list.append({
                "Month": month,
                "Total_Charge_kWh": round(monthly_charge),
                "Total_Discharge_kWh": round(effective_discharge),
                "Total_Loss_kWh": round(total_loss),
                "Total_EPRX3_kWh": round(eprx3_group["EPRX3_kWh"].sum()),
                "Total_JEPX_PnL": round(group["JEPX_PnL"].sum()),
                "Total_EPRX1_PnL": round(group["EPRX1_PnL"].sum()),
                "Total_EPRX3_PnL": round(group["EPRX3_PnL"].sum()),
                "Total_Monthly_PnL": round(monthly_total_pnl),
                "Monthly_Wheeling_Fee": round(monthly_wheeling_fee),
                "Monthly_Renewable_Energy_Surcharge": round(monthly_renewable_energy_surcharge),
                "Monthly_Net_Profit": round(monthly_net_profit),
                "Action_Counts": action_counts_str,
                "Average_Charge_Price": round(avg_charge_price, 2) if avg_charge_price is not None else None,
                "Average_Discharge_Price": round(avg_discharge_price, 2) if avg_discharge_price is not None else None,
                "Average_EPRX1_Price": round(avg_eprx1_price, 2) if avg_eprx1_price is not None else None,
                "Average_EPRX3_Price": round(avg_eprx3_price, 2) if avg_eprx3_price is not None else None,
                "EPRX3_Activation_Count": monthly_eprx3_count,
                "EPRX3_Activation_Rate": f"{eprx3_activation_rate:.1f}%",
                "V1_Price_Ratio": f"{v1_price_ratio:.1f}%"
            })

        return pd.DataFrame(summary_list)


class InterruptedException(Exception):
    """Exception raised when optimization is cancelled"""
    pass 