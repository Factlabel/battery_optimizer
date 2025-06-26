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
            self.progress_updated.emit(100)
            
            # Emit results
            self.status_updated.emit("最適化が完了しました！")
            self.optimization_completed.emit({
                'results': results,
                'summary': summary,
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
        
        all_transactions = []
        carry_over_soc = 0.0
        total_cycles_used = 0.0
        
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
            
            # Solve optimization for this day
            day_results, carry_over_soc = self._solve_daily_optimization(
                df_day, params, wheeling_data, carry_over_soc, day_idx
            )
            
            all_transactions.extend(day_results)
            
            self.log_updated.emit(f"Day {day_idx + 1} 完了: {len(day_results)} transactions")
        
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
        is_eprx1 = {}
        is_eprx3 = {}
        is_idle = {}
        
        for i in range(day_slots):
            is_charge[i] = pulp.LpVariable(f"is_charge_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_discharge[i] = pulp.LpVariable(f"is_discharge_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_eprx1[i] = pulp.LpVariable(f"is_eprx1_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_eprx3[i] = pulp.LpVariable(f"is_eprx3_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            is_idle[i] = pulp.LpVariable(f"is_idle_day{day_idx + 1}_slot{i}", cat=pulp.LpBinary)
            
            # Exclusive action constraint
            prob += is_charge[i] + is_discharge[i] + is_eprx1[i] + is_eprx3[i] + is_idle[i] == 1
            
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
        
        # SOC transition constraints
        for i in range(day_slots):
            next_soc = (battery_soc[i] + 
                       charge[i] * half_power_kWh - 
                       discharge[i] * half_power_kWh - 
                       is_eprx3[i] * half_power_kWh)
            prob += battery_soc[i + 1] == next_soc
        
        # Objective function: maximize profit
        total_profit = 0
        TAX = 1.1
        
        for i in range(day_slots):
            row = df_day.iloc[i]
            
            # Charging cost
            if not pd.isna(row['JEPX_prediction']):
                procurement_kWh = charge[i] * half_power_kWh / (1 - wheeling_loss_rate)
                charge_cost = procurement_kWh * row['JEPX_prediction'] * TAX
                total_profit -= charge_cost
            
            # Discharging revenue
            if not pd.isna(row['JEPX_actual']):
                sales_kWh = discharge[i] * half_power_kWh * (1 - battery_loss_rate)
                discharge_revenue = sales_kWh * row['JEPX_actual'] * TAX
                total_profit += discharge_revenue
            
            # EPRX1 revenue
            if not pd.isna(row['EPRX1_actual']):
                eprx1_revenue = is_eprx1[i] * battery_power_kW * row['EPRX1_actual'] * TAX
                total_profit += eprx1_revenue
            
            # EPRX3 revenue
            if not pd.isna(row['EPRX3_actual']) and not pd.isna(row['imbalance']):
                kw_value = battery_power_kW * row['EPRX3_actual']
                kwh_value = half_power_kWh * (1 - battery_loss_rate) * row['imbalance']
                eprx3_revenue = is_eprx3[i] * (kw_value + kwh_value) * TAX
                total_profit += eprx3_revenue
        
        prob += total_profit
        
        # Additional constraints (daily cycle limit, EPRX1 constraints, etc.)
        daily_cycle_limit = params.get('daily_cycle_limit', 0)
        if daily_cycle_limit > 0:
            daily_charge_sum = pulp.lpSum(charge[i] for i in range(day_slots)) * half_power_kWh
            prob += daily_charge_sum <= daily_cycle_limit * battery_capacity_kWh
        
        # Solve the problem
        try:
            # Try COIN_CMD solver first (better compatibility on macOS)
            try:
                prob.solve(pulp.COIN_CMD(msg=0))
            except:
                # Fallback to HiGHS solver
                try:
                    prob.solve(pulp.HiGHS_CMD(msg=0))
                except:
                    # Final fallback to default solver
                    prob.solve()
            
            if prob.status != pulp.LpStatusOptimal:
                raise RuntimeError(f"最適解が見つかりません。ステータス: {pulp.LpStatus[prob.status]}")
                
        except Exception as e:
            raise RuntimeError(f"ソルバーエラー: {str(e)}")
        
        # Extract results
        day_results = []
        final_soc = initial_soc
        
        for i in range(day_slots):
            row = df_day.iloc[i]
            
            # Determine the selected action
            action = "idle"
            if is_charge[i].value() and is_charge[i].value() > 0.5:
                action = "charge"
            elif is_discharge[i].value() and is_discharge[i].value() > 0.5:
                action = "discharge"
            elif is_eprx1[i].value() and is_eprx1[i].value() > 0.5:
                action = "eprx1"
            elif is_eprx3[i].value() and is_eprx3[i].value() > 0.5:
                action = "eprx3"
            
            # Calculate energy flows
            charge_kWh = charge[i].value() * half_power_kWh if charge[i].value() else 0
            discharge_kWh = discharge[i].value() * half_power_kWh if discharge[i].value() else 0
            eprx3_kWh = half_power_kWh if action == "eprx3" else 0
            
            # Update SOC
            final_soc = final_soc + charge_kWh - discharge_kWh - eprx3_kWh
            
            # Calculate PnL for this slot
            slot_pnl = self._calculate_slot_pnl(
                action, charge_kWh, discharge_kWh, eprx3_kWh,
                row, battery_loss_rate, wheeling_loss_rate, battery_power_kW
            )
            
            result = {
                'date': row['date'],
                'slot': row['slot'],
                'action': action,
                'charge_kWh': charge_kWh,
                'discharge_kWh': discharge_kWh,
                'eprx3_kWh': eprx3_kWh,
                'battery_level_kWh': final_soc,
                'slot_pnl': slot_pnl,
                'JEPX_prediction': row.get('JEPX_prediction', 0),
                'JEPX_actual': row.get('JEPX_actual', 0),
                'EPRX1_actual': row.get('EPRX1_actual', 0),
                'EPRX3_actual': row.get('EPRX3_actual', 0),
                'imbalance': row.get('imbalance', 0)
            }
            
            day_results.append(result)
        
        return day_results, final_soc
    
    def _calculate_slot_pnl(self, action: str, charge_kWh: float, discharge_kWh: float,
                          eprx3_kWh: float, row: pd.Series, battery_loss_rate: float,
                          wheeling_loss_rate: float, battery_power_kW: float) -> float:
        """Calculate PnL for a single slot"""
        
        TAX = 1.1
        pnl = 0.0
        
        # Charging cost
        if action == "charge" and charge_kWh > 0:
            procurement_kWh = charge_kWh / (1 - wheeling_loss_rate)
            cost = procurement_kWh * row.get('JEPX_prediction', 0) * TAX
            pnl -= cost
        
        # Discharging revenue
        if action == "discharge" and discharge_kWh > 0:
            sales_kWh = discharge_kWh * (1 - battery_loss_rate)
            revenue = sales_kWh * row.get('JEPX_actual', 0) * TAX
            pnl += revenue
        
        # EPRX1 revenue
        if action == "eprx1":
            revenue = battery_power_kW * row.get('EPRX1_actual', 0) * TAX
            pnl += revenue
        
        # EPRX3 revenue
        if action == "eprx3" and eprx3_kWh > 0:
            kw_value = battery_power_kW * row.get('EPRX3_actual', 0)
            kwh_value = eprx3_kWh * (1 - battery_loss_rate) * row.get('imbalance', 0)
            revenue = (kw_value + kwh_value) * TAX
            pnl += revenue
        
        return pnl
    
    def _generate_summary(self, results: List[Dict], params: Dict, 
                         wheeling_data: Dict) -> Dict:
        """Generate optimization summary"""
        
        if not results:
            return {}
        
        df_results = pd.DataFrame(results)
        
        # Calculate totals
        total_charge_kWh = df_results['charge_kWh'].sum()
        total_discharge_kWh = df_results['discharge_kWh'].sum()
        total_eprx3_kWh = df_results['eprx3_kWh'].sum()
        total_loss_kWh = total_discharge_kWh * params['battery_loss_rate']
        total_daily_pnl = df_results['slot_pnl'].sum()
        
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


class InterruptedException(Exception):
    """Exception raised when optimization is cancelled"""
    pass 