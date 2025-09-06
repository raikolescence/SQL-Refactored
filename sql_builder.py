# sql_builder.py
"""
Core logic for generating the PL/SQL query string and the friendly preview.
This module is completely independent of the UI framework.
"""

import re
import datetime
import config  # Import the configuration data

class QueryGenerationError(Exception):
    """Custom exception for errors during query generation."""
    pass

def build_sql_query(params):
    """
    Main entry point to produce SQL and the friendly preview based on input parameters.
    
    Args:
        params (dict): A dictionary containing all user selections from the UI.
        
    Returns:
        tuple: (final_sql, friendly_preview_text) or (None, None) on error.
    """
    try:
        where_conditions = _build_where_clause(params['filters'])
        good_bins_list = _get_good_bins_list(params['good_bins_str'])

        select_clauses, group_by_clauses, has_aggregates = _build_select_and_group_by_clauses(
            params, good_bins_list
        )
        
        if not select_clauses:
            raise QueryGenerationError("No columns selected to display.")

        # Assemble the query
        join_condition = "v.lot_seq = w.lot_seq AND v.wafer_id = w.wafer_id"
        from_clause = f"\nFROM\n    vmerge_Bin_zone v\nINNER JOIN\n    wafer w ON {join_condition}"

        where_clause_str = ""
        if where_conditions:
            where_clause_str = "\nWHERE\n    " + "\n    AND ".join(where_conditions)

        distinct_prefix = "DISTINCT " if params.get('select_distinct') and not has_aggregates else ""
        formatted_selects = _format_clause_list(select_clauses, items_per_line=1, indent_str="    ")
        select_clause_str = f"SELECT {distinct_prefix}\n{formatted_selects}"

        group_by_clause_str = ""
        if has_aggregates and group_by_clauses:
            unique_group_by = sorted(list(set(group_by_clauses)))
            formatted_group_by = _format_clause_list(unique_group_by, items_per_line=4, indent_str="    ")
            group_by_clause_str = f"\nGROUP BY\n{formatted_group_by}"
        
        core_query_str = f"{select_clause_str}{from_clause}{where_clause_str}{group_by_clause_str}"

        order_by_clause_str = ""
        order_conditions = [f"{order['column']} {order['direction']}" for order in params.get('order_by', [])]
        if order_conditions:
            formatted_order_by = _format_clause_list(order_conditions, items_per_line=3, indent_str="    ")
            order_by_clause_str = f"\nORDER BY\n{formatted_order_by}"

        final_sql = core_query_str + order_by_clause_str
        final_sql = "\n".join([line.rstrip() for line in final_sql.strip().split('\n')]) + ";"

        # Build friendly preview
        friendly_preview = _build_friendly_preview(select_clauses, where_conditions, group_by_clauses, order_conditions)

        return final_sql, friendly_preview

    except (ValueError, QueryGenerationError) as e:
        # Propagate error message to the UI layer
        raise QueryGenerationError(str(e))


def _build_where_clause(filters_data):
    where_conditions = []
    for f in filters_data:
        if not f['value']:
            continue
        
        col = f['props']['sql_col']
        op = f['op']
        val = f['value']
        
        cond = ""
        try:
            if f['props']['type'] == 'date':
                time_str = f.get('time', '00:00:00')
                datetime.datetime.strptime(time_str, '%H:%M:%S')  # Validate time format
                oracle_date = datetime.datetime.strptime(val, '%Y-%m-%d').strftime('%d-%b-%Y').upper()
                full_datetime = f"{oracle_date} {time_str}"
                cond = f"{col} {op} TO_DATE('{full_datetime}','DD-MON-YYYY HH24:MI:SS')"
            elif op == 'IN':
                items = [i.strip().replace("'", "''") for i in val.split(',') if i.strip()]
                formatted_items = []
                for item in items:
                    is_numeric = item.replace('.', '', 1).isdigit() or (item.startswith('-') and item[1:].replace('.', '', 1).isdigit())
                    is_quoted = item.startswith("'") and item.endswith("'")
                    formatted_items.append(item if is_numeric or is_quoted else f"'{item}'")
                if formatted_items:
                    cond = f"{col} {op} ({', '.join(formatted_items)})"
            elif f['props']['type'] == 'numeric':
                float(val) # Validate
                cond = f"{col} {op} {val}"
            else: # Default text
                escaped_val = val.replace("'", "''")
                cond = f"{col} {op} '{escaped_val}'"

            if cond:
                where_conditions.append(cond)
        except ValueError:
            raise QueryGenerationError(f"Invalid value for filter '{f['name']}': {val}")
    return where_conditions


def _get_good_bins_list(good_bins_str):
    if not good_bins_str:
        return []
    try:
        return [str(int(b.strip())) for b in good_bins_str.split(',') if b.strip()]
    except ValueError:
        raise QueryGenerationError(f"Invalid 'Good Bins' list: '{good_bins_str}'. Must be comma-separated numbers.")


def _build_select_and_group_by_clauses(params, good_bins_list):
    select_clauses, group_by_clauses, has_aggregates = [], [], False
    good_bins_sql = ",".join(good_bins_list) if good_bins_list else "NULL"
    alias_to_expr = {}
    selected_cols = params.get('select_columns', [])

    for name in selected_cols:
        props = config.SELECT_OPTIONS[name]
        if props.get("agg"):
            has_aggregates = True
            template = props.get("sql_template", props.get("sql", ""))
            if not isinstance(template, str):
                raise QueryGenerationError(f"Invalid SQL template for column '{name}': expected a string, got {type(template).__name__}")
            expr = template.replace("{good_bins_placeholder}", good_bins_sql).replace("{BIN_col}", "v.bin").replace("{TOTAL_col}", "v.total").replace("{WAFER_ID_col}", "v.wafer_id")
            alias = props.get("alias")
            select_clauses.append(f"{expr} AS {alias}" if alias else expr)
            if alias: alias_to_expr[alias] = expr
        else:
            sql_expr = props["sql"]
            alias = props.get("alias")
            select_clauses.append(f"{sql_expr} AS {alias}" if alias else sql_expr)
            group_by_clauses.append(props.get("group", sql_expr))
            if alias: alias_to_expr[alias] = sql_expr

    # Handle custom and auto-range BINs
    bin_col_agg, total_col_agg = "v.bin", "v.total"
    if params.get('auto_range_enabled'):
        has_aggregates = True
        try:
            start, end = params['auto_range_start'], params['auto_range_end']
            if start > end: raise ValueError("Start BIN > End BIN")
            for bin_num in range(start, end + 1):
                if params['auto_range_count']:
                    alias = f"bin_{bin_num}count"
                    expr = f"SUM(CASE WHEN {bin_col_agg} = {bin_num} THEN {total_col_agg} ELSE 0 END)"
                    select_clauses.append(f"{expr} AS {alias}")
                    alias_to_expr[alias] = expr
                if params['auto_range_percent']:
                    alias = f"bin{bin_num}_pct"
                    expr = f"ROUND(SUM(CASE WHEN {bin_col_agg} = {bin_num} THEN {total_col_agg} ELSE 0 END) / NULLIF(SUM({total_col_agg}), 0) * 100, 2)"
                    select_clauses.append(f"{expr} AS {alias}")
                    alias_to_expr[alias] = expr
        except (ValueError, KeyError) as e:
            raise QueryGenerationError(f"Invalid Auto Range settings: {e}")

    for bin_row in params.get('custom_bins', []):
        try:
            bin_num = int(bin_row['bin'])
            has_aggregates = True
            if bin_row['count']:
                alias = f"bin_{bin_num}count"
                expr = f"SUM(CASE WHEN {bin_col_agg} = {bin_num} THEN {total_col_agg} ELSE 0 END)"
                select_clauses.append(f"{expr} AS {alias}")
                alias_to_expr[alias] = expr
            if bin_row['percent']:
                alias = f"bin{bin_num}_pct"
                expr = f"ROUND(SUM(CASE WHEN {bin_col_agg} = {bin_num} THEN {total_col_agg} ELSE 0 END) / NULLIF(SUM({total_col_agg}), 0) * 100, 2)"
                select_clauses.append(f"{expr} AS {alias}")
                alias_to_expr[alias] = expr
        except (ValueError, KeyError):
            pass # Ignore invalid custom bin rows silently

    # Handle custom aggregates
    for agg_row in params.get('custom_aggregates', []):
        func, col, alias = agg_row['func'], agg_row['col'], agg_row['alias']
        if not col: continue
        
        expr_to_agg = None
        if col in alias_to_expr:
            alias_expr = alias_to_expr[col]
            if _is_ratio_or_percentage_expr(alias_expr) or _contains_any_aggregate(alias_expr):
                 raise QueryGenerationError(f"Cannot aggregate '{col}' because it's a derived ratio or already an aggregate.")
            expr_to_agg = alias_expr
        else:
            expr_to_agg = col
        
        if expr_to_agg:
            safe_alias = alias or f"{func.lower()}_{re.sub(r'[^0-9a-zA-Z]+','_', col)}"
            select_clauses.append(f"{func}({expr_to_agg}) AS {safe_alias}")
            has_aggregates = True

    return select_clauses, group_by_clauses, has_aggregates

def _build_friendly_preview(selects, wheres, groups, orders):
    parts = []
    simple, aggs = [], []
    for s in selects:
        if re.search(r'\b(sum|avg|min|max|count)\b\s*\(', s.lower()):
            aggs.append(s)
        else:
            simple.append(s)

    if simple:
        cols = ", ".join([re.sub(r'\s+as\s+.*$', '', s, flags=re.IGNORECASE).strip() for s in simple])
        parts.append(f"Columns: {cols}.")
    if aggs:
        cleaned = [re.sub(r"\s+as\s+.*$", "", s, flags=re.IGNORECASE).strip() for s in aggs]
        parts.append(f"Aggregates: {', '.join(cleaned)}.")

    if wheres: parts.append("Filters: " + "; ".join(wheres))
    if groups: parts.append("Grouped by: " + ", ".join(sorted(list(set(groups)))))
    if orders: parts.append("Ordered by: " + ", ".join(orders))
    
    return "\n".join(parts) if parts else "No selections defined yet."


def _format_clause_list(items, indent_str="    ", items_per_line=4):
    if not items: return ""
    lines = []
    for i in range(0, len(items), items_per_line):
        chunk = items[i:i + items_per_line]
        lines.append(indent_str + ", ".join(chunk))
    return ",\n".join(lines)

def _is_ratio_or_percentage_expr(expr):
    return bool(re.search(r'NULLIF\(|/\s*NULLIF\(|ROUND\s*\(\s*SUM|SUM\s*\(.*\)\s*/\s*SUM\s*\(', expr, re.IGNORECASE))

def _contains_any_aggregate(expr):
    return bool(re.search(r'\b(SUM|AVG|MIN|MAX|COUNT)\s*\(', expr, re.IGNORECASE))