"""
Area Configuration and Wheeling Data

This module contains all the regional configuration data including
wheeling rates, loss rates, and area mappings for the Japanese electricity market.
"""

# Renewable energy surcharge (yen/kWh)
RENEWABLE_ENERGY_SURCHARGE = 3.49

# Wheeling data for all areas and voltage classes
WHEELING_DATA = {
    "areas": {
        "Hokkaido": {
            "SHV": {"loss_rate": 0.02, "wheeling_base_charge": 503.80, "wheeling_usage_fee": 0.92},
            "HV": {"loss_rate": 0.047, "wheeling_base_charge": 792.00, "wheeling_usage_fee": 2.17},
            "LV": {"loss_rate": 0.079, "wheeling_base_charge": 618.20, "wheeling_usage_fee": 4.22}
        },
        "Tohoku": {
            "SHV": {"loss_rate": 0.019, "wheeling_base_charge": 630.30, "wheeling_usage_fee": 8.57},
            "HV": {"loss_rate": 0.052, "wheeling_base_charge": 706.20, "wheeling_usage_fee": 2.08},
            "LV": {"loss_rate": 0.085, "wheeling_base_charge": 456.50, "wheeling_usage_fee": 2.08}
        },
        "Tokyo": {
            "SHV": {"loss_rate": 0.013, "wheeling_base_charge": 423.39, "wheeling_usage_fee": 1.33},
            "HV": {"loss_rate": 0.037, "wheeling_base_charge": 653.87, "wheeling_usage_fee": 2.37},
            "LV": {"loss_rate": 0.069, "wheeling_base_charge": 461.14, "wheeling_usage_fee": 5.20}
        },
        "Chubu": {
            "SHV": {"loss_rate": 0.025, "wheeling_base_charge": 357.50, "wheeling_usage_fee": 0.88},
            "HV": {"loss_rate": 0.038, "wheeling_base_charge": 467.50, "wheeling_usage_fee": 2.21},
            "LV": {"loss_rate": 0.071, "wheeling_base_charge": 412.50, "wheeling_usage_fee": 6.07}
        },
        "Hokuriku": {
            "SHV": {"loss_rate": 0.013, "wheeling_base_charge": 572.00, "wheeling_usage_fee": 0.85},
            "HV": {"loss_rate": 0.034, "wheeling_base_charge": 748.00, "wheeling_usage_fee": 1.76},
            "LV": {"loss_rate": 0.078, "wheeling_base_charge": 396.00, "wheeling_usage_fee": 4.69}
        },
        "Kansai": {
            "SHV": {"loss_rate": 0.029, "wheeling_base_charge": 440.00, "wheeling_usage_fee": 0.84},
            "HV": {"loss_rate": 0.078, "wheeling_base_charge": 663.30, "wheeling_usage_fee": 2.29},
            "LV": {"loss_rate": 0.078, "wheeling_base_charge": 378.40, "wheeling_usage_fee": 4.69}
        },
        "Chugoku": {
            "SHV": {"loss_rate": 0.025, "wheeling_base_charge": 383.90, "wheeling_usage_fee": 0.70},
            "HV": {"loss_rate": 0.044, "wheeling_base_charge": 658.90, "wheeling_usage_fee": 2.43},
            "LV": {"loss_rate": 0.077, "wheeling_base_charge": 466.40, "wheeling_usage_fee": 6.07}
        },
        "Shikoku": {
            "SHV": {"loss_rate": 0.013, "wheeling_base_charge": 510.40, "wheeling_usage_fee": 0.77},
            "HV": {"loss_rate": 0.041, "wheeling_base_charge": 712.80, "wheeling_usage_fee": 2.01},
            "LV": {"loss_rate": 0.081, "wheeling_base_charge": 454.30, "wheeling_usage_fee": 5.97}
        },
        "Kyushu": {
            "SHV": {"loss_rate": 0.013, "wheeling_base_charge": 482.05, "wheeling_usage_fee": 1.27},
            "HV": {"loss_rate": 0.032, "wheeling_base_charge": 553.28, "wheeling_usage_fee": 2.61},
            "LV": {"loss_rate": 0.086, "wheeling_base_charge": 379.26, "wheeling_usage_fee": 5.58}
        }
    }
}

# Area number to name mapping
AREA_NUMBER_TO_NAME = {
    1: "Hokkaido",
    2: "Tohoku", 
    3: "Tokyo",
    4: "Chubu",
    5: "Hokuriku",
    6: "Kansai",
    7: "Chugoku",
    8: "Shikoku",
    9: "Kyushu"
}

# Reverse mapping: name to number
AREA_NAME_TO_NUMBER = {v: k for k, v in AREA_NUMBER_TO_NAME.items()}

# Voltage type descriptions
VOLTAGE_TYPES = {
    "SHV": "特高圧 (Special High Voltage)",
    "HV": "高圧 (High Voltage)", 
    "LV": "低圧 (Low Voltage)"
}

# Default optimization parameters
DEFAULT_OPTIMIZATION_PARAMS = {
    "battery_power_kW": 1000,
    "battery_capacity_kWh": 4000,
    "battery_loss_rate": 0.05,
    "daily_cycle_limit": 1,
    "yearly_cycle_limit": 365,
    "annual_degradation_rate": 0.03,
    "forecast_period": 48,
    "eprx1_block_size": 3,
    "eprx1_block_cooldown": 2,
    "max_daily_eprx1_slots": 6
}

def get_area_list():
    """Get list of areas for UI display"""
    return [f"{num}: {name}" for num, name in AREA_NUMBER_TO_NAME.items()]

def get_voltage_list():
    """Get list of voltage types for UI display"""
    return list(VOLTAGE_TYPES.keys())

def parse_area_selection(area_string: str) -> tuple:
    """Parse area selection string to get area number and name"""
    try:
        parts = area_string.split(": ", 1)
        area_number = int(parts[0])
        area_name = parts[1]
        return area_number, area_name
    except (ValueError, IndexError):
        raise ValueError(f"Invalid area selection: {area_string}")

def get_wheeling_info(area_name: str, voltage_type: str) -> dict:
    """Get wheeling information for specified area and voltage type"""
    try:
        return WHEELING_DATA["areas"][area_name][voltage_type]
    except KeyError:
        raise ValueError(f"Wheeling data not found for {area_name} - {voltage_type}")

def validate_optimization_params(params: dict) -> dict:
    """Validate and fill missing optimization parameters with defaults"""
    validated_params = DEFAULT_OPTIMIZATION_PARAMS.copy()
    validated_params.update(params)
    
    # Validate ranges
    if validated_params["battery_power_kW"] <= 0:
        raise ValueError("バッテリー出力は正の値である必要があります")
    if validated_params["battery_capacity_kWh"] <= 0:
        raise ValueError("バッテリー容量は正の値である必要があります") 
    if not 0 <= validated_params["battery_loss_rate"] <= 1:
        raise ValueError("バッテリー損失率は0-1の範囲である必要があります")
    
    return validated_params 