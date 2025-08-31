# config.py
"""
Contains all static configuration data for the SQL Formatter application.
This includes options for SELECT columns, WHERE filters, and default operators.
"""

from collections import OrderedDict
import datetime

SELECT_OPTIONS = OrderedDict([
    ("Test Area", {"sql": "test_area", "default": True, "agg": False, "group": "test_area", "dedup_group": "test_area",
                   "requires_columns": ["test_area"]}),
    ("SMS Device", {"sql": "sms_device", "default": True, "agg": False, "group": "sms_device", "dedup_group": "sms_device",
                    "requires_columns": ["sms_device"]}),
    ("Source Fab", {"sql": "srcfab", "default": True, "agg": False, "group": "srcfab", "dedup_group": "srcfab",
                    "requires_columns": ["srcfab"]}),
    ("Test Program (Wafer)", {"sql": "w.test_program", "default": True, "agg": False, "group": "w.test_program",
                              "dedup_group": "w_test_program", "requires_columns": ["w.test_program"]}),
    ("Program (Vmerge)", {"sql": "v.program", "default": True, "agg": False, "group": "v.program", "dedup_group": "v_program",
                          "requires_columns": ["v.program"]}),
    ("Lot", {"sql": "v.lot", "default": True, "agg": False, "group": "v.lot", "dedup_group": "v_lot",
             "requires_columns": ["v.lot"]}),
    ("Fablot", {"sql": "v.fablot", "default": True, "agg": False, "group": "v.fablot", "dedup_group": "v_fablot",
                "requires_columns": ["v.fablot"]}),
    ("Tester", {"sql": "w.tester", "default": True, "agg": False, "group": "w.tester", "dedup_group": "w_tester",
                "requires_columns": ["w.tester"]}),
    ("Prober", {"sql": "w.prober", "default": True, "agg": False, "group": "w.prober", "dedup_group": "w_prober",
                "requires_columns": ["w.prober"]}),
    ("Probe Card", {"sql": "w.probe_card", "default": True, "agg": False, "group": "w.probe_card", "dedup_group": "w_probe_card",
                    "requires_columns": ["w.probe_card"]}),
    ("Loadboard (PIB)", {"sql": "w.loadbd", "alias": "PIB", "default": True, "agg": False, "group": "w.loadbd", "dedup_group": "w_loadbd",
                         "requires_columns": ["w.loadbd"]}),
    ("Wafer ID", {"sql": "v.wafer_id", "default": True, "agg": False, "group": "v.wafer_id", "dedup_group": "v_wafer_id",
                  "requires_columns": ["v.wafer_id"]}),
    ("End Time (Date Char)", {"sql": "to_char(w.end_time,'MON/DD/YYYY')", "alias": "date_1", "default": True, "agg": False,
                              "group": "to_char(w.end_time,'MON/DD/YYYY')", "dedup_group": "date_1", "requires_columns": ["w.end_time"]}),
    ("End Time (Timestamp)", {"sql": "w.end_time", "default": True, "agg": False, "group": "w.end_time", "dedup_group": "w_end_time",
                              "requires_columns": ["w.end_time"]}),
    ("Yield (%)", {
        "sql_template": "ROUND(SUM(CASE WHEN {BIN_col} IN ({good_bins_placeholder}) THEN {TOTAL_col} ELSE 0 END) / NULLIF(SUM({TOTAL_col}), 0) * 100, 2)",
        "alias": "YIELD", "default": True, "agg": True, "group": None, "requires_columns": ["v.bin", "v.total"]}),
    ("Yield (Good Bin Count)", {"sql_template": "SUM(CASE WHEN {BIN_col} IN ({good_bins_placeholder}) THEN {TOTAL_col} ELSE 0 END)",
                                "alias": "GOOD_BIN_COUNT", "default": True, "agg": True, "group": None, "requires_columns": ["v.bin", "v.total"]}),
    ("Bin Record Count", {"sql": "COUNT(*)", "alias": "Bin_Record_Count", "default": True, "agg": True, "group": None,
                          "requires_columns": []}),
    ("Affected Wafer Count per Lot (Distinct)", {"sql": "COUNT(DISTINCT {WAFER_ID_col})", "alias": "affected_wafer_count_per_lot", "default": False, "agg": True,
                                                "group": None, "requires_columns": ["v.wafer_id", "w.wafer_id"]}),
])

TEXT_OPERATORS = ['=', 'LIKE', 'IN', '!=']
NUMERIC_OPERATORS = ['=', '!=', '>', '<', '>=', '<=']
DATE_OPERATORS = ['>=', '<=', '=', '>', '<']

FILTER_OPTIONS = OrderedDict([
    ("Program (v.program)", {"sql_col": "v.program", "default_op": "LIKE", "default_val": "", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., %ABC123%"}),
    ("AC Flags (ac_flags)", {"sql_col": "ac_flags", "default_op": "IN", "default_val": "", "type": "text", "operators": ["IN"], "hint": "e.g., '17','145' or 17,145"}),
    ("Probe Card (w.probe_card)", {"sql_col": "w.probe_card", "default_op": "LIKE", "default_val": "", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., KY8P%"}),
    ("Test Program (w.test_program)", {"sql_col": "w.test_program", "default_op": "LIKE", "default_val": "", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., %PP2830%"}),
    ("Tester (w.tester)", {"sql_col": "w.tester", "default_op": "LIKE", "default_val": "TT5003%", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., TT2852% or TT5200,TT2500 for IN"}),
    ("Loadboard (w.loadbd)", {"sql_col": "w.loadbd", "default_op": "LIKE", "default_val": "", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., %"}),
    ("Prober (w.prober)", {"sql_col": "w.prober", "default_op": "=", "default_val": "", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., PP3105"}),
    ("SMS Device (sms_device)", {"sql_col": "sms_device", "default_op": "LIKE", "default_val": "", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., %XA$4H%"}),
    ("Probe Count (probe_cnt)", {"sql_col": "probe_cnt", "default_op": "=", "default_val": "", "type": "numeric", "operators": NUMERIC_OPERATORS, "hint": "e.g., 0"}),
    ("Wafer ID (w.wafer_id)", {"sql_col": "w.wafer_id", "default_op": "LIKE", "default_val": "", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., %WAFER01%"}),
    ("Lot (v.lot)", {"sql_col": "v.lot", "default_op": "=", "default_val": "", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., 5014844"}),
    ("Fablot (v.fablot)", {"sql_col": "v.fablot", "default_op": "IN", "default_val": "", "type": "text", "operators": ["IN", "=", "LIKE"], "hint": "e.g., 'FB01','FB02' or FB01,FB02 for IN"}),
    ("Test Area (test_area)", {"sql_col": "test_area", "default_op": "LIKE", "default_val": "", "type": "text", "operators": TEXT_OPERATORS, "hint": "e.g., MP1"}),
    ("End Time From", {"sql_col": "w.end_time", "default_op": ">=", "default_val": datetime.datetime.now().strftime("%Y-%m-%d"), "type": "date", "operators": DATE_OPERATORS, "hint": "YYYY-MM-DD"}),
    ("End Time To", {"sql_col": "w.end_time", "default_op": "<=", "default_val": datetime.datetime.now().strftime("%Y-%m-%d"), "type": "date", "operators": DATE_OPERATORS, "hint": "YYYY-MM-DD"}),
])