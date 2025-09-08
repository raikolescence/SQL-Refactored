# config.py
"""
Contains all static configuration data for the SQL Formatter application.
This includes options for SELECT columns, WHERE filters, and default operators.
"""

import os
import json
from collections import OrderedDict
import datetime
import calendar

CONFIG_DIR = os.path.join(os.path.dirname(__file__), 'config')

# Helper to replace special tokens in JSON (like {{TODAY}})
def _replace_tokens(val):
    # Support token {{TODAY}} and {{TODAY_MINUS_MONTHS:n}}
    if isinstance(val, str):
        if val == "{{TODAY}}":
            return datetime.datetime.now().strftime("%Y-%m-%d")
        # Match token like {{TODAY_MINUS_MONTHS:1}}
        if val.startswith("{{TODAY_MINUS_MONTHS:") and val.endswith("}}"):
            try:
                inner = val[len("{{TODAY_MINUS_MONTHS:"): -2]
                months = int(inner)
                today = datetime.datetime.now()
                # Precise month subtraction without external deps: adjust year/month and clamp day to the
                # last day of the target month (so e.g., Mar 31 - 1 month -> Feb 28/29)
                year = today.year
                month = today.month - months
                while month <= 0:
                    month += 12
                    year -= 1
                last_day = calendar.monthrange(year, month)[1]
                day = min(today.day, last_day)
                dt = datetime.datetime(year, month, day)
                print(dt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                print("AHH")
                return datetime.datetime.now().strftime("%Y-%m-%d")
    if isinstance(val, list):
        return [_replace_tokens(v) for v in val]
    if isinstance(val, dict):
        return {k: _replace_tokens(v) for k, v in val.items()}
    return val

def load_configs():
    configs = {}
    if not os.path.isdir(CONFIG_DIR):
        return configs
    for fname in os.listdir(CONFIG_DIR):
        if fname.endswith('.json'):
            with open(os.path.join(CONFIG_DIR, fname), 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Replace tokens like {{TODAY}}
                for k, v in data.items():
                    data[k] = _replace_tokens(v)
                configs[fname[:-5]] = data
    return configs

# Load all configs at import
discovered_configs = load_configs()

# Use the first config as default (or None)
default_config = next(iter(discovered_configs.values()), None)

# Expose SELECT_OPTIONS, FILTER_OPTIONS, etc. from the default config
if default_config:
    SELECT_OPTIONS = OrderedDict(default_config["SELECT_OPTIONS"])
    FILTER_OPTIONS = OrderedDict(default_config["FILTER_OPTIONS"])
    TEXT_OPERATORS = default_config["TEXT_OPERATORS"]
    NUMERIC_OPERATORS = default_config["NUMERIC_OPERATORS"]
    DATE_OPERATORS = default_config["DATE_OPERATORS"]
    SAVE_LOCATION = default_config.get("SAVE_LOCATION", {"default_folder": "", "description": "Default folder to save Excel spreadsheets"})
    # Expose convenient constant for default save folder
    DEFAULT_SAVE_FOLDER = SAVE_LOCATION.get("default_folder", "")
else:
    SELECT_OPTIONS = FILTER_OPTIONS = OrderedDict()
    TEXT_OPERATORS = NUMERIC_OPERATORS = DATE_OPERATORS = []
    SAVE_LOCATION = {"default_folder": "", "description": "Default folder to save Excel spreadsheets"}
    DEFAULT_SAVE_FOLDER = ""