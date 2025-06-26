

RENEWABLE_ENERGY_SURCHARGE = 3.49

WHEELING_DATA = {
    "areas": {
        "Hokkaido": {
            "SHV": {"loss_rate": 0.02, "wheeling_base_charge": 503.80, "wheeling_usage_fee": 0.92},
            "HV" : {"loss_rate": 0.047, "wheeling_base_charge": 792.00, "wheeling_usage_fee": 2.17},
            "LV" : {"loss_rate": 0.079, "wheeling_base_charge": 618.20, "wheeling_usage_fee": 4.22}
        },
        "Tohoku": {
            "SHV": {"loss_rate": 0.019, "wheeling_base_charge": 630.30, "wheeling_usage_fee": 8.57},
            "HV" : {"loss_rate": 0.052, "wheeling_base_charge": 706.20, "wheeling_usage_fee": 2.08},
            "LV" : {"loss_rate": 0.085, "wheeling_base_charge": 456.50, "wheeling_usage_fee": 2.08}
        },
        "Tokyo": {
            "SHV": {"loss_rate": 0.013, "wheeling_base_charge": 423.39, "wheeling_usage_fee": 1.33},
            "HV" : {"loss_rate": 0.037, "wheeling_base_charge": 653.87, "wheeling_usage_fee": 2.37},
            "LV" : {"loss_rate": 0.069, "wheeling_base_charge": 461.14, "wheeling_usage_fee": 5.20}
        },
        "Chubu": {
            "SHV": {"loss_rate": 0.025, "wheeling_base_charge": 357.50, "wheeling_usage_fee": 0.88},
            "HV" : {"loss_rate": 0.038, "wheeling_base_charge": 467.50, "wheeling_usage_fee": 2.21},
            "LV" : {"loss_rate": 0.071, "wheeling_base_charge": 412.50, "wheeling_usage_fee": 6.07}
        },
        "Hokuriku": {
            "SHV": {"loss_rate": 0.013, "wheeling_base_charge": 572.00, "wheeling_usage_fee": 0.85},
            "HV" : {"loss_rate": 0.034, "wheeling_base_charge": 748.00, "wheeling_usage_fee": 1.76},
            "LV" : {"loss_rate": 0.078, "wheeling_base_charge": 396.00, "wheeling_usage_fee": 4.69}
        },
        "Kansai": {
            "SHV": {"loss_rate": 0.029, "wheeling_base_charge": 440.00, "wheeling_usage_fee": 0.84},
            "HV" : {"loss_rate": 0.078, "wheeling_base_charge": 663.30, "wheeling_usage_fee": 2.29},
            "LV" : {"loss_rate": 0.078, "wheeling_base_charge": 378.40, "wheeling_usage_fee": 4.69}
        },
        "Chugoku": {
            "SHV": {"loss_rate": 0.025, "wheeling_base_charge": 383.90, "wheeling_usage_fee": 0.70},
            "HV" : {"loss_rate": 0.044, "wheeling_base_charge": 658.90, "wheeling_usage_fee": 2.43},
            "LV" : {"loss_rate": 0.077, "wheeling_base_charge": 466.40, "wheeling_usage_fee": 6.07}
        },
        "Shikoku": {
            "SHV": {"loss_rate": 0.013, "wheeling_base_charge": 510.40, "wheeling_usage_fee": 0.77},
            "HV" : {"loss_rate": 0.041, "wheeling_base_charge": 712.80, "wheeling_usage_fee": 2.01},
            "LV" : {"loss_rate": 0.081, "wheeling_base_charge": 454.30, "wheeling_usage_fee": 5.97}
        },
        "Kyushu": {
            "SHV": {"loss_rate": 0.013, "wheeling_base_charge": 482.05, "wheeling_usage_fee": 1.27},
            "HV" : {"loss_rate": 0.032, "wheeling_base_charge": 553.28, "wheeling_usage_fee": 2.61},
            "LV" : {"loss_rate": 0.086, "wheeling_base_charge": 379.26, "wheeling_usage_fee": 5.58}
        }
    }
}

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