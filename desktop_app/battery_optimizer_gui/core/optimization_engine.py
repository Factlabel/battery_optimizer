"""
Battery Optimization Engine for PyQt6 Application

This module contains the core optimization logic adapted from the Streamlit version
with PyQt6 signals/slots integration for real-time progress updates.
"""

import pandas as pd
import numpy as np
import pulp
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from typing import Dict, List, Optional, Tuple
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptimizationEngine(QThread):
    """
    Battery optimization engine running in a separate thread
    with real-time progress updates via Qt signals.
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
        """Validate input data and parameters"""
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
            raise ValueError(f"必須列が不足しています: {missing_cols}")
            
        self.log_updated.emit("入力データの検証が完了しました")
    
    def _get_wheeling_data(self, area_name: str, voltage_type: str) -> Dict:
        """Get wheeling data for the specified area and voltage type"""
        # Import the config data (should be moved to a separate config module)
        from config.area_config import WHEELING_DATA
        
        wheeling_data = WHEELING_DATA["areas"].get(area_name, {}).get(voltage_type, {})
        if not wheeling_data:
            raise ValueError(f"エリア '{area_name}' の電圧区分 '{voltage_type}' のデータが見つかりません")
            
        return wheeling_data
    
    def _run_battery_optimization(self, params: Dict, df_all: pd.DataFrame, 
                                wheeling_data: Dict) -> List[Dict]:
        """Run the main battery optimization logic"""
        
        self.status_updated.emit("最適化問題を構築中...")
        
        # Sort data by date and slot
        df_all = df_all.sort_values(by=["date", "slot"]).reset_index(drop=True)
        total_slots = len(df_all)
        
        # Calculate daily slots
        forecast_period = params.get('forecast_period', 48)
        num_days = (total_slots + forecast_period - 1) // forecast_period
        
        # Show optimization scope
        if not df_all.empty:
            start_date = df_all['date'].min()
            end_date = df_all['date'].max() 
            self.log_updated.emit(f"📊 最適化対象: {start_date} から {end_date} ({num_days}日間, {total_slots}スロット)")
        
        all_transactions = []
        carry_over_soc = 0.0
        total_cycles_used = 0.0
        total_profit = 0.0
        
        # Battery parameters
        battery_power_kW = params['battery_power_kW']
        battery_capacity_kWh = params['battery_capacity_kWh']
        battery_loss_rate = params['battery_loss_rate']
        half_power_kWh = battery_power_kW * 0.5
        
        # Daily optimization loop
        for day_idx in range(num_days):
            if self.is_cancelled:
                raise InterruptedException("最適化がキャンセルされました")
                
            self.status_updated.emit(f"Day {day_idx + 1}/{num_days} を最適化中...")
            progress = 20 + int(60 * (day_idx + 1) / num_days)
            self.progress_updated.emit(progress)
            
            start_i = day_idx * forecast_period
            end_i = min(start_i + forecast_period, total_slots)
            
            if start_i >= total_slots:
                break
                
            df_day = df_all.iloc[start_i:end_i].copy().reset_index(drop=True)
            day_slots = len(df_day)
            
            if day_slots == 0:
                break
            
            # Debug: Check price data (reduce logging for performance)
            if day_idx < 3:  # Only log first 3 days to reduce overhead
                jepx_pred_sum = df_day['JEPX_prediction'].sum()
                jepx_actual_sum = df_day['JEPX_actual'].sum()
                self.log_updated.emit(f"Day {day_idx + 1}: JEPX_pred_sum={jepx_pred_sum:.1f}, JEPX_actual_sum={jepx_actual_sum:.1f}")
            
            # Check first few rows (reduce logging for performance)
            if day_idx < 2:  # Only check first 2 days to reduce overhead
                for idx in range(min(2, len(df_day))):  # Check only first 2 rows
                    row_data = df_day.iloc[idx]
                    self.log_updated.emit(f"  Row {idx}: JEPX_pred={row_data.get('JEPX_prediction'):.1f}, EPRX1_pred={row_data.get('EPRX1_prediction'):.1f}")
            
            # Solve optimization for this day
            day_results, carry_over_soc = self._solve_daily_optimization(
                df_day, params, wheeling_data, carry_over_soc, day_idx
            )
            
            all_transactions.extend(day_results)
            
            # Calculate daily profit and cycle usage (like Streamlit)
            day_profit = sum(r['Total_Daily_PnL'] for r in day_results)
            total_profit += day_profit
            
            # Calculate daily cycle usage
            day_charge_kWh = sum(r['charge_kWh'] for r in day_results)
            day_cycle_count = day_charge_kWh / battery_capacity_kWh if battery_capacity_kWh > 0 else 0
            total_cycles_used += day_cycle_count
            
            # Enhanced logging with cycle limit information
            daily_cycle_limit = params.get('daily_cycle_limit', 0)
            if daily_cycle_limit > 0:
                limit_status = f"制限内" if day_cycle_count <= daily_cycle_limit else f"制限超過"
                if day_idx < 5:  # Reduce logging frequency for performance
                    self.log_updated.emit(f"Day {day_idx + 1} 完了: profit={day_profit:.0f}, cycles={day_cycle_count:.3f}/{daily_cycle_limit} ({limit_status})")
            else:
                if day_idx < 5:  # Reduce logging frequency for performance
                    self.log_updated.emit(f"Day {day_idx + 1} 完了: profit={day_profit:.0f}, cycles={day_cycle_count:.3f} (制限なし)")
            
            # Check yearly cycle limit (exactly like Streamlit)
            yearly_cycle_limit = params.get('yearly_cycle_limit', 0)
            if (yearly_cycle_limit > 0) and (total_cycles_used > yearly_cycle_limit):
                self.log_updated.emit(f"Yearly cycle limit ({yearly_cycle_limit}) reached at {total_cycles_used:.3f} cycles. Stopping optimization.")
                break
        
        return all_transactions
    
    def _solve_daily_optimization(self, df_day: pd.DataFrame, params: Dict, 
                                wheeling_data: Dict, initial_soc: float, 
                                day_idx: int) -> Tuple[List[Dict], float]:
        """Solve optimization for a single day"""
        
        day_slots = len(df_day)
        battery_power_kW = params['battery_power_kW']
        battery_capacity_kWh = params['battery_capacity_kWh']
        battery_loss_rate = params['battery_loss_rate']
        half_power_kWh = battery_power_kW * 0.5
        wheeling_loss_rate = wheeling_data.get("loss_rate", 0.0)
        
        # Add debugging mode for gradual constraint addition
        DEBUG_MODE = params.get('debug_mode', 'simple')  # Default to 'simple' for best performance
        
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
        self.log_updated.emit(f"Day {day_idx + 1}: initial_soc = {initial_soc}, day_slots = {day_slots}, debug_mode = {DEBUG_MODE}")
        
        # SOC transition constraints
        for i in range(day_slots):
            next_soc = (battery_soc[i] + 
                       charge[i] * half_power_kWh - 
                       discharge[i] * half_power_kWh - 
                       is_eprx3[i] * half_power_kWh)
            prob += battery_soc[i + 1] == next_soc
        
        # Apply daily cycle limit constraint for ALL modes
        daily_cycle_limit = params.get('daily_cycle_limit', 0)
        if daily_cycle_limit > 0:
            daily_charge_sum = pulp.lpSum(charge[i] for i in range(day_slots)) * half_power_kWh
            prob += daily_charge_sum <= daily_cycle_limit * battery_capacity_kWh
            if day_idx < 3:  # Only log first few days to reduce overhead
                self.log_updated.emit(f"Day {day_idx + 1}: 日次サイクル制限適用 - {daily_cycle_limit} cycles")
        
        # EPRX1 variables and constraints (only if not simple mode)
        if DEBUG_MODE == 'simple':
            # Simple mode: only charge, discharge, eprx3, idle (no EPRX1 complexity)
            self.log_updated.emit("Using SIMPLE mode: no EPRX1 blocks")
            
            # Exclusive action constraint (without EPRX1)
            for i in range(day_slots):
                prob += is_charge[i] + is_discharge[i] + is_eprx3[i] + is_idle[i] == 1
                
            # Prevent actions when prediction prices are invalid
            for i in range(day_slots):
                row = df_day.iloc[i]
                # EPRX3 constraint: cannot use if prediction is 0 or NaN
                e3pred = row.get('EPRX3_prediction', 0)
                if pd.isna(e3pred) or e3pred == 0:
                    prob += is_eprx3[i] == 0
                    
            # Objective function (simplified - no EPRX1)
            TAX = 1.1
            profit_terms = []
            
            for i in range(day_slots):
                row = df_day.iloc[i]
                
                # Get prediction prices (NaN defaults to 0)
                jpred = row.get('JEPX_prediction', 0.0)
                if pd.isna(jpred):
                    jpred = 0.0
                e3pred = row.get('EPRX3_prediction', 0.0)
                if pd.isna(e3pred):
                    e3pred = 0.0
                imb = row.get('imbalance', 0.0)
                if pd.isna(imb):
                    imb = 0.0
                
                # Charging cost
                cost_c = jpred * (charge[i] * half_power_kWh / (1 - wheeling_loss_rate))
                
                # Discharging revenue
                rev_d = jpred * (discharge[i] * half_power_kWh * (1 - battery_loss_rate))
                
                # EPRX3 revenue
                rev_e3 = TAX * is_eprx3[i] * (battery_power_kW * e3pred + half_power_kWh * (1 - battery_loss_rate) * imb)
                
                slot_profit = -cost_c + rev_d + rev_e3
                profit_terms.append(slot_profit)
                
        else:
            # Advanced modes: include EPRX1 block functionality
            self.log_updated.emit(f"Using {DEBUG_MODE} mode: including EPRX1 blocks")
            
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
                
                # Exclusive action constraint (with EPRX1)
                prob += is_charge[i] + is_discharge[i] + is_in_block[i] + is_eprx3[i] + is_idle[i] == 1
            
            # (A) is_in_block definition (EPRX1 block continuity)
            for i in range(day_slots):
                possible_starts = []
                for x in range(max(0, i - (M - 1)), i + 1):
                    if x + M - 1 >= i:
                        possible_starts.append(block_start[x])
                prob += is_in_block[i] == pulp.lpSum(possible_starts)
            
            # Prevent actions when prediction prices are invalid
            for i in range(day_slots):
                row = df_day.iloc[i]
                
                # EPRX3 constraint: cannot use if prediction is 0 or NaN
                e3pred = row.get('EPRX3_prediction', 0)
                if pd.isna(e3pred) or e3pred == 0:
                    prob += is_eprx3[i] == 0
            
            if DEBUG_MODE == 'basic':
                self.log_updated.emit("Using BASIC mode: simplified EPRX1 constraints")
                
                # Basic EPRX1 constraints only
                # (G) EPRX1 prediction constraint: cannot start block if prediction is 0 or NaN
                for i in range(day_slots):
                    for slot_in_block in range(i, min(i + M, day_slots)):
                        row = df_day.iloc[slot_in_block]
                        e1pred = row.get('EPRX1_prediction', 0)
                        if pd.isna(e1pred) or e1pred == 0:
                            prob += block_start[i] <= 0
                
            elif DEBUG_MODE == 'full':
                self.log_updated.emit("Using FULL mode: all EPRX1 constraints")
                
                # (E) EPRX1 block constraints (cooldown)
                for i in range(day_slots):
                    end_j = min(day_slots, i + M + C)
                    for j in range(i + 1, end_j):
                        prob += block_start[i] + block_start[j] <= 1
                    if i > day_slots - M:
                        prob += block_start[i] == 0
                
                # (G) EPRX1 prediction constraint: cannot start block if prediction is 0 or NaN
                for i in range(day_slots):
                    for slot_in_block in range(i, min(i + M, day_slots)):
                        row = df_day.iloc[slot_in_block]
                        e1pred = row.get('EPRX1_prediction', 0)
                        if pd.isna(e1pred) or e1pred == 0:
                            prob += block_start[i] <= 0
                
                # (I) Daily EPRX1 block limit
                max_daily_eprx1_slots = params.get('max_daily_eprx1_slots', 0)
                if max_daily_eprx1_slots > 0:
                    prob += pulp.lpSum(is_in_block[i] for i in range(day_slots)) <= max_daily_eprx1_slots
                
                # EPRX1 SoC constraints (40-60% range when EPRX1 is active)
                bigM = 999999
                for i in range(day_slots):
                    # When EPRX1 is active, SoC must be between 40-60%
                    prob += battery_soc[i] >= 0.4 * battery_capacity_kWh - (1 - is_in_block[i]) * bigM
                    prob += battery_soc[i] <= 0.6 * battery_capacity_kWh + (1 - is_in_block[i]) * bigM
            
            # Objective function (with EPRX1)
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
                
                # EPRX3 revenue (ONLY TAX applied here - exactly like Streamlit)
                rev_e3 = TAX * is_eprx3[i] * (battery_power_kW * e3pred + half_power_kWh * (1 - battery_loss_rate) * imb)
                
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
        
        # Extract results
        day_results = []
        
        for i in range(day_slots):
            row = df_day.iloc[i]
            
            # Get solver values
            c_val = pulp.value(charge[i]) if pulp.value(charge[i]) is not None else 0
            d_val = pulp.value(discharge[i]) if pulp.value(discharge[i]) is not None else 0
            
            # Define thresholds for numerical precision
            THRESHOLD = 1e-6  # Very small threshold for numerical precision
            
            # Determine the selected action based on binary variables AND actual values
            action = "idle"  # Default action
            
            # Check EPRX1 first (if not in simple mode)
            if DEBUG_MODE != 'simple' and pulp.value(is_in_block[i]) > 0.5:
                action = "eprx1"
            # Check EPRX3
            elif pulp.value(is_eprx3[i]) > 0.5:
                action = "eprx3"
            # Check charge (binary variable AND actual charge amount)
            elif pulp.value(is_charge[i]) > 0.5 and c_val > THRESHOLD:
                action = "charge"
            # Check discharge (binary variable AND actual discharge amount)  
            elif pulp.value(is_discharge[i]) > 0.5 and d_val > THRESHOLD:
                action = "discharge"
            # Default to idle if no significant action
            else:
                action = "idle"
            
            # Calculate energy flows according to action type (exactly like Streamlit)
            j_a = row.get('JEPX_actual', 0.0) if not pd.isna(row.get('JEPX_actual', 0.0)) else 0.0
            e1_a = row.get('EPRX1_actual', 0.0) if not pd.isna(row.get('EPRX1_actual', 0.0)) else 0.0
            e3_a = row.get('EPRX3_actual', 0.0) if not pd.isna(row.get('EPRX3_actual', 0.0)) else 0.0
            imb_a = row.get('imbalance', 0.0) if not pd.isna(row.get('imbalance', 0.0)) else 0.0
            
            # Use exact same logic as Streamlit
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
                # EPRX3は数量調整せず、常に最大放電量からロス分を引いた値を使用
                effective_kwh = half_power_kWh * (1 - battery_loss_rate)
                loss_kwh = half_power_kWh * battery_loss_rate
            else:  # idle
                c_kwh = 0.0
                effective_kwh = 0.0
                loss_kwh = 0.0
            
            # Get SOC from optimization solver (this is the correct value)
            soc_value = battery_soc[i + 1].value()
            current_soc = pulp.value(battery_soc[i + 1]) if soc_value is not None else 0
            
            # Debug logging (reduce for performance)
            if i < 3 and day_idx < 2:  # Only log first few slots of first few days
                self.log_updated.emit(f"Slot {i}: action={action}, current_soc={current_soc:.1f}")
                self.log_updated.emit(f"  c_val={c_val:.6f} (binary={pulp.value(is_charge[i]):.1f}), d_val={d_val:.6f} (binary={pulp.value(is_discharge[i]):.1f})")
                self.log_updated.emit(f"  charge_kWh={c_kwh:.3f}, effective_kwh={effective_kwh:.3f}")
            
            # Calculate PnL components (exactly like Streamlit)
            pnl_data = self._calculate_slot_pnl(
                action, c_kwh if action == "charge" else 0,
                effective_kwh if action == "discharge" else 0,
                effective_kwh if action == "eprx3" else 0,
                row, battery_loss_rate, wheeling_loss_rate, battery_power_kW
            )
            
            result = {
                'date': row['date'],
                'slot': int(row['slot']),
                'action': action,
                'battery_level_kWh': round(current_soc, 2),
                'charge_kWh': round(c_kwh, 3) if action == "charge" else 0,
                'discharge_kWh': round(effective_kwh, 3) if action == "discharge" else 0,
                'EPRX3_kWh': round(effective_kwh, 3) if action == "eprx3" else 0,
                'loss_kWh': round(loss_kwh, 3),
                'JEPX_actual': round(j_a, 3),
                'EPRX1_actual': round(e1_a, 3),
                'EPRX3_actual': round(e3_a, 3),
                'imbalance': round(imb_a, 3),
                'JEPX_PnL': pnl_data['JEPX_PnL'],
                'EPRX1_PnL': pnl_data['EPRX1_PnL'],
                'EPRX3_PnL': pnl_data['EPRX3_PnL'],
                'Total_Daily_PnL': pnl_data['Total_Daily_PnL'],
                'JEPX_prediction': row.get('JEPX_prediction', 0),
                'EPRX1_prediction': row.get('EPRX1_prediction', 0),
                'EPRX3_prediction': row.get('EPRX3_prediction', 0)
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
        
        # Get final SOC for next day initialization
        final_soc = pulp.value(battery_soc[day_slots]) if battery_soc[day_slots].value() is not None else initial_soc
        if day_idx < 3:  # Only log first few days
            self.log_updated.emit(f"Day {day_idx + 1}: final_soc = {final_soc:.1f}")
        
        return day_results, final_soc
    
    def _calculate_slot_pnl(self, action: str, charge_kWh: float, discharge_kWh: float,
                          eprx3_kWh: float, row: pd.Series, battery_loss_rate: float,
                          wheeling_loss_rate: float, battery_power_kW: float) -> Dict[str, float]:
        """Calculate PnL for a single slot - exactly like Streamlit"""
        
        TAX = 1.1
        
        # Get actual prices (not prediction!)
        j_a = row.get('JEPX_actual', 0.0) if not pd.isna(row.get('JEPX_actual', 0.0)) else 0.0
        e1_a = row.get('EPRX1_actual', 0.0) if not pd.isna(row.get('EPRX1_actual', 0.0)) else 0.0
        e3_a = row.get('EPRX3_actual', 0.0) if not pd.isna(row.get('EPRX3_actual', 0.0)) else 0.0
        imb_a = row.get('imbalance', 0.0) if not pd.isna(row.get('imbalance', 0.0)) else 0.0
        
        # Initialize PnL components (exactly like Streamlit)
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
            # EPRX3は数量調整せず、常に最大放電量からロス分を引いた値を使用
            kW_value = battery_power_kW * e3_a
            kWh_value = eprx3_kWh * imb_a  # eprx3_kWh is already effective (loss removed)
            slot_eprx3_pnl = TAX * (kW_value + kWh_value)
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
        total_eprx3_kWh = df_results['EPRX3_kWh'].sum()  # Fixed column name
        total_loss_kWh = df_results['loss_kWh'].sum()  # Use actual loss column
        # total_daily_pnl = df_results['slot_pnl'].sum()  # This column doesn't exist anymore
        
        # Calculate total PnL from results (PnL already calculated per slot)
        total_daily_pnl = df_results['Total_Daily_PnL'].sum()
        
        # Calculate monthly fees
        battery_power_kW = params['battery_power_kW']
        wheeling_basic_fee = wheeling_data.get("wheeling_base_charge", 0) * battery_power_kW
        wheeling_usage_fee = wheeling_data.get("wheeling_usage_fee", 0) * total_loss_kWh
        renewable_energy_surcharge = 3.49 * total_loss_kWh  # Fixed rate
        
        final_profit = total_daily_pnl - wheeling_basic_fee - wheeling_usage_fee - renewable_energy_surcharge
        
        summary = {
            'Total_Charge_kWh': total_charge_kWh,
            'Total_Discharge_kWh': total_discharge_kWh,
            'Total_Loss_kWh': total_loss_kWh,
            'Total_EPRX3_kWh': total_eprx3_kWh,
            'Total_Daily_PnL': total_daily_pnl,
            'Wheeling_Basic_Fee': wheeling_basic_fee,
            'Wheeling_Usage_Fee': wheeling_usage_fee,
            'Renewable_Energy_Surcharge': renewable_energy_surcharge,
            'Final_Profit': final_profit,
            'Total_Slots': len(results),
            'Optimization_Success': True
        }
        
        return summary

    def _generate_monthly_summary(self, results: List[Dict], params: Dict, 
                                 wheeling_data: Dict) -> pd.DataFrame:
        """Generate monthly summary like Streamlit app"""
        
        if not results:
            return pd.DataFrame()
        
        # Import here to avoid circular imports
        from config.area_config import RENEWABLE_ENERGY_SURCHARGE
        
        df = pd.DataFrame(results)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["month"] = df["date"].dt.to_period("M").astype(str)
        summary_list = []

        battery_power_kW = params['battery_power_kW']
        target_area_name = params['target_area_name']
        voltage_type = params['voltage_type']
        
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
            else:
                avg_eprx3_price = None

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
            })

        return pd.DataFrame(summary_list)


class InterruptedException(Exception):
    """Exception raised when optimization is cancelled"""
    pass 