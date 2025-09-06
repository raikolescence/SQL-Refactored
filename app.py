from __future__ import annotations
"""
Main application class for the SQL Formatter.
- Manages the Tkinter UI, widgets, and application state.
- Orchestrates calls to the sql_builder and history_manager modules.
- Integrated: run_sql_and_download utility and UI to generate + download Excel file.
- ADDED: In-memory DataFrame storage and Pivot Table UI.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog, filedialog, Listbox, MULTIPLE
from collections import OrderedDict
import datetime
import re
import os
# Local module imports
import config
import sql_builder
import history_manager
from ui.tooltip import ToolTip
from ui.scrollable_frame import ScrollableFrame
try:
    from tkcalendar import DateEntry
    TKCALENDAR_AVAILABLE = True
except ImportError:
    TKCALENDAR_AVAILABLE = False
    from tkinter import ttk
    DateEntry = ttk.Entry  # Fallback to Entry if tkcalendar is not available
    print("WARNING: tkcalendar library not found. Date inputs will be text fields. "
          "Please install tkcalendar for a better experience (pip install tkcalendar).")
# -----------------------------
# DB download helper (integrated)
# -----------------------------
from typing import Optional
import oracledb
import pandas as pd
DB_USERNAME = 'testware'
DB_PASSWORD = 'testware'
DB_HOST     = 'clprrptw.dal.make.ti.com'
DB_PORT     = 1521
DB_SID      = 'clprrptw'

def run_sql_and_download(
    sql_text: str,
    excel_name: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    Run a SQL query against the TI CLPR report DB and save results to Excel.
    If `excel_name` is a full path, the file will be written there. If it's just a filename
    it will be created in the current working directory. If None, a timestamped filename
    is generated in the current working directory.
    Returns the DataFrame if successful, else None.
    """
    # Auto-generate filename if not provided
    if excel_name is None:
        excel_name = f"query_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    if not excel_name.lower().endswith(".xlsx"):
        excel_name += ".xlsx"
    # Remove trailing semicolon (Oracle driver doesn’t like it)
    sql_text = sql_text.strip().rstrip(";")
    try:
        print("Connecting (thin mode)…")
        with oracledb.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            sid=DB_SID
        ) as conn, conn.cursor() as cur:
            print("Executing query…")
            cur.execute(sql_text)
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
        if not rows:
            print("No rows returned.")
            return None
        # Convert to DataFrame
        df = pd.DataFrame(rows, columns=cols)
        # Ensure output directory exists when a path is provided
        out_dir = os.path.dirname(os.path.abspath(excel_name))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        # Save to Excel
        if excel_name:  # Only save if a name is provided
            df.to_excel(excel_name, index=False, engine="openpyxl")
            print(f"✅ Saved {len(df):,} rows → {os.path.abspath(excel_name)}")
        return df
    except oracledb.Error as e:
        print("❌ DB error:", e)
    except Exception as e:
        print("❌ Unexpected error:", e)
    return None

class SQLFormatterApp:
    def __init__(self, master):
        self.master = master
        master.title("PL/SQL Query Formatter")
        master.geometry("1300x950")
        master.minsize(800, 600)
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)
        # Style setup
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except tk.TclError:
            try: self.style.theme_use('default')
            except tk.TclError: pass
        default_font = ("Segoe UI", 10)
        self.style.configure(".", font=default_font)
        self.style.configure("TButton", padding=6)
        self.style.configure("TEntry", padding=4)
        self.style.configure("TLabel", padding=4)
        self.style.configure("Hint.TLabel", foreground="gray")
        self.style.configure("TLabelframe.Label", font=('TkDefaultFont', 10, 'bold'))
        # --- Member Variables (Application State) ---
        self.select_vars = {}
        self.filter_widgets = {}
        self.custom_bin_rows = []
        self.order_by_rows = []
        self.orderable_columns_map = OrderedDict()
        self.orderable_column_display_names_for_combo = []
        self.custom_aggregate_rows = []
        self.dynamic_select_aliases = []
        # NEW: Store the current DataFrame
        self.current_df = None
        # Tkinter variables
        self.good_bins_var = tk.StringVar(value="1,2,3,4,5")
        self.max_rows_var = tk.StringVar(value="") # Note: max_rows logic not in original, but var is here
        self.select_distinct_var = tk.BooleanVar(value=False)
        self.deduplicate_wafer_entries_var = tk.BooleanVar(value=False) # Note: Deduplication logic not fully implemented in original SQL builder
        self.quick_add_bins_entry_var = tk.StringVar()
        # New output path controls - use defaults from active config if available
        try:
            default_folder = config.DEFAULT_SAVE_FOLDER
        except Exception:
            default_folder = ""
        # We intentionally avoid a default filename so users must supply or accept timestamped names
        self.output_folder_var = tk.StringVar(value=default_folder)
        self.output_file_name_var = tk.StringVar(value="")
        # History and saved queries
        self.history_file = "query_history.json"
        self.saved_file = "saved_queries.json"
        self.query_history = history_manager.load_history(self.history_file)
        self.saved_queries = history_manager.load_saved_queries(self.saved_file)
        # --- UI Construction ---
        self.status_bar = ttk.Label(master, text="Ready", anchor=tk.W, relief=tk.SUNKEN, padding=(5, 2))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        button_frame = ttk.Frame(master, padding="5")
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0), padx=10)
        main_paned_window = ttk.PanedWindow(master, orient=tk.VERTICAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_notebook = ttk.Notebook(main_paned_window)
        main_paned_window.add(main_notebook, weight=2)
        output_frame = ttk.LabelFrame(main_paned_window, text="Generated SQL Query", padding="10")
        main_paned_window.add(output_frame, weight=1)
        self.friendly_preview = tk.Text(output_frame, height=4, wrap=tk.WORD, font=("Segoe UI", 10), state="disabled", background="#fafafa")
        self.friendly_preview.pack(fill="x", padx=3, pady=(0, 6))
        self.sql_output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.sql_output_text.pack(fill="both", expand=True)
        generate_button = ttk.Button(button_frame, text="Generate SQL", command=self.generate_sql)
        generate_button.pack(side=tk.LEFT, padx=5)
        ToolTip(generate_button, "Generate the SQL query according to the current selections.")
        # New button: generate + download
        # Download button: uses the SQL currently shown in the Generated SQL area
        download_button = ttk.Button(button_frame, text="Download", command=self.download_current_query)
        download_button.pack(side=tk.LEFT, padx=5)
        ToolTip(download_button, "Run the SQL currently shown and save results to Excel.")
        # NEW BUTTON: Store in Memory
        store_button = ttk.Button(button_frame, text="Store in Memory", command=self.store_query_in_memory)
        store_button.pack(side=tk.LEFT, padx=5)
        ToolTip(store_button, "Run the SQL and store results in memory for Pivot Table analysis.")
        copy_button = ttk.Button(button_frame, text="Copy to Clipboard", command=self.copy_to_clipboard)
        copy_button.pack(side=tk.LEFT, padx=5)
        ToolTip(copy_button, "Copy the generated SQL to the clipboard.")
        copy_close_button = ttk.Button(button_frame, text="Copy & Close", command=self.copy_and_close)
        copy_close_button.pack(side=tk.LEFT, padx=5)
        ToolTip(copy_close_button, "Copy the SQL and close the application.")
        reset_button = ttk.Button(button_frame, text="Reset Form", command=self.reset_form)
        reset_button.pack(side=tk.RIGHT, padx=5)
        ToolTip(reset_button, "Reset everything to defaults.")
        self._create_tabs(main_notebook)
        self._update_saved_queries_dropdown()
        self._update_orderable_columns_list_ui_callback()

    # -----------------------------
    # Main Query Generation Orchestrator
    # -----------------------------
    def generate_sql(self):
        self.sql_output_text.delete('1.0', tk.END)
        self.status_bar.config(text="Generating...")
        self.master.update_idletasks()
        params = self._gather_ui_state()
        try:
            final_sql, friendly_preview = sql_builder.build_sql_query(params)
            self.sql_output_text.insert(tk.END, final_sql)
            self.status_bar.config(text=f"Query Generated Successfully ({datetime.datetime.now():%H:%M:%S})")
            self.add_to_query_history(final_sql)
            self._set_friendly_preview_text(friendly_preview)
        except sql_builder.QueryGenerationError as e:
            messagebox.showerror("Query Error", str(e), parent=self.master)
            self.status_bar.config(text="Error in query generation.")

    def download_current_query(self):
        """Run the SQL currently present in the Generated SQL box and save results to Excel.
        This will NOT auto-generate SQL if the box is empty — the user must generate or paste it first.
        """
        sql = self.sql_output_text.get('1.0', tk.END).strip()
        if not sql:
            messagebox.showwarning("No SQL", "No SQL query available to execute. Generate or paste a query first.", parent=self.master)
            return
        # Determine output path
        folder = self.output_folder_var.get().strip()
        file_name = self.output_file_name_var.get().strip()
        if folder and not os.path.isdir(folder):
            messagebox.showerror("Invalid Folder", f"The selected folder does not exist:\n{folder}", parent=self.master)
            return
        # If user did not supply a filename, create a timestamped one (so we can show the exact saved path)
        if file_name:
            if not file_name.lower().endswith('.xlsx'):
                file_name += '.xlsx'
            excel_path = os.path.join(folder, file_name) if folder else file_name
        else:
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_path = os.path.join(folder, f"query_results_{ts}.xlsx") if folder else os.path.join(os.getcwd(), f"query_results_{ts}.xlsx")
        self.status_bar.config(text="Running query and saving results...")
        self.master.update_idletasks()
        try:
            df = run_sql_and_download(sql, excel_path)
            if df is None:
                messagebox.showinfo("No Results", "Query executed but returned no rows.", parent=self.master)
                self.status_bar.config(text="Query returned no rows.")
                return
            saved_path = os.path.abspath(excel_path)
            messagebox.showinfo("Saved", f"Query results saved to:\n{saved_path}", parent=self.master)
            self.status_bar.config(text=f"Saved results → {os.path.basename(saved_path)}")
        except Exception as e:
            messagebox.showerror("Execution Error", f"An error occurred while running the query:\n{e}", parent=self.master)
            self.status_bar.config(text="Error during query execution.")

    # NEW METHOD: Store Query in Memory
    def store_query_in_memory(self):
        """Run the SQL currently present and store the results in `self.current_df` for pivot table analysis."""
        sql = self.sql_output_text.get('1.0', tk.END).strip()
        if not sql:
            messagebox.showwarning("No SQL", "No SQL query available to execute. Generate or paste a query first.", parent=self.master)
            return
        self.status_bar.config(text="Running query and storing in memory...")
        self.master.update_idletasks()
        try:
            # Pass None for excel_name to avoid saving a file
            df = run_sql_and_download(sql, excel_name=None)
            if df is None:
                messagebox.showinfo("No Results", "Query executed but returned no rows.", parent=self.master)
                self.status_bar.config(text="Query returned no rows.")
                self.current_df = None
                return
            self.current_df = df
            # Switch to the Pivot Table tab
            #self.main_notebook.select(self.pivot_table_tab)
            self.status_bar.config(text=f"Stored {len(df):,} rows in memory. Switched to 'Pivot Table' tab.")
            # Update the pivot table UI with new column names
            self._populate_pivot_table_column_lists()
        except Exception as e:
            messagebox.showerror("Execution Error", f"An error occurred while running the query:\n{e}", parent=self.master)
            self.status_bar.config(text="Error during query execution.")

    def generate_and_download(self):
        """Generate SQL (if needed) and run it, saving results to Excel according to output controls."""
        # Ensure SQL exists in the output box; if not, generate it
        sql = self.sql_output_text.get('1.0', tk.END).strip()
        if not sql:
            self.generate_sql()
            sql = self.sql_output_text.get('1.0', tk.END).strip()
        if not sql:
            messagebox.showwarning("No SQL", "No SQL query available to execute. Generate or paste a query first.", parent=self.master)
            return
        # Determine output path
        folder = self.output_folder_var.get().strip()
        file_name = self.output_file_name_var.get().strip()
        if folder and not os.path.isdir(folder):
            messagebox.showerror("Invalid Folder", f"The selected folder does not exist:\n{folder}", parent=self.master)
            return
        if file_name:
            if not file_name.lower().endswith('.xlsx'):
                file_name += '.xlsx'
            if folder:
                excel_path = os.path.join(folder, file_name)
            else:
                excel_path = file_name
        else:
            # No filename given — let helper create a timestamped name but place it in folder if provided
            if folder:
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                excel_path = os.path.join(folder, f"query_results_{ts}.xlsx")
            else:
                excel_path = None  # helper will generate name in cwd
        self.status_bar.config(text="Running query and saving results...")
        self.master.update_idletasks()
        try:
            df = run_sql_and_download(sql, excel_path)
            if df is None:
                messagebox.showinfo("No Results", "Query executed but returned no rows.", parent=self.master)
                self.status_bar.config(text="Query returned no rows.")
                return
            saved_path = os.path.abspath(excel_path) if excel_path else os.path.abspath(f"query_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            messagebox.showinfo("Saved", f"Query results saved to:\n{saved_path}", parent=self.master)
            self.status_bar.config(text=f"Saved results → {os.path.basename(saved_path)}")
        except Exception as e:
            messagebox.showerror("Execution Error", f"An error occurred while running the query:\n{e}", parent=self.master)
            self.status_bar.config(text="Error during query execution.")

    def _gather_ui_state(self):
        """Collects all selections from the UI widgets into a single dictionary."""
        params = {
            'select_distinct': self.select_distinct_var.get(),
            'good_bins_str': self.good_bins_var.get().strip(),
            'select_columns': [name for name, var in self.select_vars.items() if var.get()],
            'filters': [
                {
                    'name': name,
                    'op': data['op_var'].get(),
                    'value': data['val_var'].get().strip(),
                    'time': data['time_var'].get().strip() if data['time_var'] else None,
                    'props': data['props']
                }
                for name, data in self.filter_widgets.items()
            ],
            'custom_bins': [
                {'bin': row['bin_var'].get(), 'count': row['count_var'].get(), 'percent': row['percent_var'].get()}
                for row in self.custom_bin_rows if row['bin_var'].get().strip()
            ],
            'order_by': [
                {'column': self.orderable_columns_map.get(row['column_var'].get(), row['column_var'].get()), 'direction': row['direction_var'].get()}
                for row in self.order_by_rows if row['column_var'].get()
            ],
            'custom_aggregates': [
                {'func': row['func_var'].get().upper(), 'col': row['col_var'].get(), 'alias': row['alias_var'].get()}
                for row in self.custom_aggregate_rows if row['col_var'].get()
            ],
            'auto_range_enabled': self.auto_range_enabled_var.get(),
        }
        if params['auto_range_enabled']:
            try:
                params['auto_range_start'] = int(self.auto_range_start_bin_var.get())
                params['auto_range_end'] = int(self.auto_range_end_bin_var.get())
                params['auto_range_count'] = self.auto_range_include_count_var.get()
                params['auto_range_percent'] = self.auto_range_include_percentage_var.get()
            except (ValueError, TypeError):
                params['auto_range_enabled'] = False # Let builder handle error message
        return params

    # -----------------------------
    # Tabs and UI creation
    # -----------------------------
    def _create_tabs(self, main_notebook):
        # Store reference to notebook for later use
        self.main_notebook = main_notebook

        tabs_config = {
            'Query Config': self._create_config_tab,
            'SELECT Columns': self._create_select_tab,
            'Custom BINs (SELECT)': self._create_custom_bins_tab,
            'WHERE Filters': self._create_filters_tab,
            'ORDER BY': self._create_order_by_tab,
            'Custom Aggregates': self._create_aggregate_tab,
            'Query History': self._create_history_tab,
            'Saved Queries': self._create_saved_tab,
            # NEW TAB: Pivot Table
            'Pivot Table': self._create_pivot_table_tab
        }
        for text, creation_method in tabs_config.items():
            tab_frame = ttk.Frame(main_notebook, padding="10")
            main_notebook.add(tab_frame, text=text)
            # Store reference to pivot table tab
            if text == 'Pivot Table':
                self.pivot_table_tab = tab_frame
            creation_method(tab_frame)

    def switch_config(self, *args):
        import importlib
        import config as config_module
        selected = self.config_name_var.get()
        # Reload config module and set the default config
        importlib.reload(config_module)
        if selected in config_module.discovered_configs:
            config_module.default_config = config_module.discovered_configs[selected]
            config_module.SELECT_OPTIONS = OrderedDict(config_module.default_config["SELECT_OPTIONS"])
            config_module.FILTER_OPTIONS = OrderedDict(config_module.default_config["FILTER_OPTIONS"])
            config_module.TEXT_OPERATORS = config_module.default_config["TEXT_OPERATORS"]
            config_module.NUMERIC_OPERATORS = config_module.default_config["NUMERIC_OPERATORS"]
            config_module.DATE_OPERATORS = config_module.default_config["DATE_OPERATORS"]
        # Rebuild all tabs
        for widget in self.master.winfo_children():
            widget.destroy()
        self.__init__(self.master)

    def _create_config_tab(self, tab):
        config_frame = ttk.LabelFrame(tab, text="General Settings", padding="10")
        config_frame.pack(fill=tk.X, expand=False, padx=5, pady=5)
        config_frame.columnconfigure(1, weight=1)
        # Config switcher
        ttk.Label(config_frame, text="Config Preset:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.config_name_var = tk.StringVar(value=next(iter(config.discovered_configs.keys()), ""))
        config_combo = ttk.Combobox(config_frame, textvariable=self.config_name_var, values=list(config.discovered_configs.keys()), state="readonly")
        config_combo.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        config_combo.bind("<<ComboboxSelected>>", self.switch_config)
        ttk.Label(config_frame, text="Load Saved Query:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.saved_queries_combo_var = tk.StringVar()
        self.saved_queries_combo = ttk.Combobox(config_frame, textvariable=self.saved_queries_combo_var, state="readonly")
        self.saved_queries_combo.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        load_button = ttk.Button(config_frame, text="Load", command=self.load_query_from_config_tab)
        load_button.grid(row=1, column=2, padx=5, pady=2)
        ttk.Label(config_frame, text="Good Bins for Yield:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.good_bins_entry = ttk.Entry(config_frame, textvariable=self.good_bins_var)
        self.good_bins_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
        ToolTip(self.good_bins_entry, "Comma-separated list of BIN numbers considered 'good' for yield (e.g., 1,2,3).")
        ttk.Label(config_frame, text="e.g., 1,2,3,5", style="Hint.TLabel").grid(row=2, column=2, sticky=tk.W, padx=5, pady=2)
        ttk.Label(config_frame, text="Max Rows (ROWNUM):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(config_frame, textvariable=self.max_rows_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Checkbutton(config_frame, text="Use SELECT DISTINCT", variable=self.select_distinct_var).grid(row=4, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        dedup_check = ttk.Checkbutton(config_frame, text="Deduplicate Wafer Entries (keeps latest by end_time)",
                                      variable=self.deduplicate_wafer_entries_var)
        dedup_check.grid(row=5, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        ToolTip(dedup_check, "Note: This feature is a placeholder and not fully implemented in the SQL generation logic.")
        # --- Output path controls (new)
        ttk.Label(config_frame, text="Output Folder:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=2)
        output_folder_entry = ttk.Entry(config_frame, textvariable=self.output_folder_var)
        output_folder_entry.grid(row=6, column=1, sticky=tk.EW, padx=5, pady=2)
        browse_folder_btn = ttk.Button(config_frame, text="Browse...", command=self.browse_output_folder)
        browse_folder_btn.grid(row=6, column=2, sticky=tk.W, padx=5, pady=2)
        ToolTip(browse_folder_btn, "Choose a folder where exported Excel files will be saved.")
        ttk.Label(config_frame, text="Output File Name (optional):").grid(row=7, column=0, sticky=tk.W, padx=5, pady=2)
        output_file_entry = ttk.Entry(config_frame, textvariable=self.output_file_name_var)
        output_file_entry.grid(row=7, column=1, sticky=tk.EW, padx=5, pady=2)
        browse_file_btn = ttk.Button(config_frame, text="Browse (Save-As)...", command=self.browse_output_file)
        browse_file_btn.grid(row=7, column=2, sticky=tk.W, padx=5, pady=2)
        ToolTip(browse_file_btn, "Open a Save-As dialog to choose filename + location. This will populate the folder and filename fields.")

    def browse_output_folder(self):
        folder = filedialog.askdirectory(parent=self.master, title="Select output folder")
        if folder:
            self.output_folder_var.set(folder)

    def browse_output_file(self):
        f = filedialog.asksaveasfilename(parent=self.master, defaultextension='.xlsx', filetypes=[('Excel files', '*.xlsx')], title='Save query results as...')
        if f:
            self.output_file_name_var.set(os.path.basename(f))
            self.output_folder_var.set(os.path.dirname(f))

    # -----------------------------
    # (rest of file continues unchanged)
    # -----------------------------
    def _create_select_tab(self, tab):
        tab.columnconfigure(0, weight=1); tab.rowconfigure(0, weight=1)
        select_scroll_frame = ScrollableFrame(tab, fit_width=True)
        select_scroll_frame.grid(row=0, column=0, sticky="nsew")
        content_frame = select_scroll_frame.scrollable_frame
        content_frame.columnconfigure((0, 1, 2), weight=1)
        row, col, max_cols = 0, 0, 3
        for name, props in config.SELECT_OPTIONS.items():
            var = tk.BooleanVar(value=bool(props.get("default", False)))
            sql_val = props.get("sql", "")
            prefix = ""
            if isinstance(sql_val, str):
                if sql_val.startswith("v."):
                    prefix = "[V] "
                elif sql_val.startswith("w."):
                    prefix = "[W] "
            chk = ttk.Checkbutton(content_frame, text=f"{prefix}{name}", variable=var, command=self._update_orderable_columns_list_ui_callback)
            chk.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.select_vars[name] = var
            col = (col + 1) % max_cols
            if col == 0: row += 1

    def _create_custom_bins_tab(self, tab):
        tab.columnconfigure(0, weight=1); tab.rowconfigure(0, weight=1)
        self.custom_bins_scroll_frame = ScrollableFrame(tab, fit_width=True)
        self.custom_bins_scroll_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        controls_container = ttk.Frame(tab)
        controls_container.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.add_bin_button = ttk.Button(controls_container, text="Add Single Custom BIN Row", command=self.add_custom_bin_row)
        self.add_bin_button.pack(pady=5, anchor=tk.W, padx=5)
        quick_add_frame = ttk.LabelFrame(controls_container, text="Quick Add Multiple BINs", padding="10")
        quick_add_frame.pack(fill=tk.X, pady=5, anchor=tk.W, padx=5)
        quick_add_frame.columnconfigure(1, weight=1)
        ttk.Label(quick_add_frame, text="BINs (e.g., 6,7,8):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        quick_add_entry = ttk.Entry(quick_add_frame, textvariable=self.quick_add_bins_entry_var)
        quick_add_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 5))
        quick_add_button = ttk.Button(quick_add_frame, text="Add These BINs", command=self.process_quick_add_bins)
        quick_add_button.grid(row=0, column=2, sticky=tk.W)
        auto_range_frame = ttk.LabelFrame(controls_container, text="Auto Range BINs", padding="10")
        auto_range_frame.pack(fill=tk.X, pady=5, anchor=tk.W, padx=5)
        self.auto_range_enabled_var = tk.BooleanVar(value=False)
        self.auto_range_start_bin_var = tk.StringVar(value="6")
        self.auto_range_end_bin_var = tk.StringVar(value="100")
        self.auto_range_include_count_var = tk.BooleanVar(value=True)
        self.auto_range_include_percentage_var = tk.BooleanVar(value=True)
        auto_range_check = ttk.Checkbutton(auto_range_frame, text="Enable Auto Range (e.g., for BINs 6-100)",
                                           variable=self.auto_range_enabled_var, command=self._toggle_auto_range_controls_state)
        auto_range_check.grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 10))
        ttk.Label(auto_range_frame, text="Start BIN:").grid(row=1, column=0, sticky=tk.W, padx=(5, 2))
        self.auto_range_start_entry = ttk.Entry(auto_range_frame, textvariable=self.auto_range_start_bin_var, width=8)
        self.auto_range_start_entry.grid(row=1, column=1, sticky=tk.W, padx=(0, 10))
        ttk.Label(auto_range_frame, text="End BIN:").grid(row=1, column=2, sticky=tk.W, padx=(5, 2))
        self.auto_range_end_entry = ttk.Entry(auto_range_frame, textvariable=self.auto_range_end_bin_var, width=8)
        self.auto_range_end_entry.grid(row=1, column=3, sticky=tk.W, padx=(0, 5))
        self.auto_range_count_check = ttk.Checkbutton(auto_range_frame, text="Include Count", variable=self.auto_range_include_count_var)
        self.auto_range_count_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 2), padx=5)
        self.auto_range_percentage_check = ttk.Checkbutton(auto_range_frame, text="Include Percentage", variable=self.auto_range_include_percentage_var)
        self.auto_range_percentage_check.grid(row=2, column=2, columnspan=2, sticky=tk.W, pady=(5, 2), padx=5)
        self._toggle_auto_range_controls_state()

    # -----------------------------
    # NEW: Pivot Table Tab Creation
    # -----------------------------
    def _create_pivot_table_tab(self, tab):
        """Creates the UI for the Pivot Table analysis tab."""
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        # Control Frame (Top)
        control_frame = ttk.Frame(tab, padding="10")
        control_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        control_frame.columnconfigure((1, 3, 5), weight=1)

        # ROWS Section
        ttk.Label(control_frame, text="Rows:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
        self.rows_listbox = Listbox(control_frame, selectmode=MULTIPLE, height=6, exportselection=False)
        self.rows_listbox.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=2)
        rows_scrollbar = ttk.Scrollbar(control_frame, orient="vertical", command=self.rows_listbox.yview)
        rows_scrollbar.grid(row=0, column=2, sticky="ns", pady=2)
        self.rows_listbox.configure(yscrollcommand=rows_scrollbar.set)

        # COLUMNS Section
        ttk.Label(control_frame, text="Columns:").grid(row=0, column=3, sticky="w", padx=(0, 5), pady=2)
        self.cols_listbox = Listbox(control_frame, selectmode=MULTIPLE, height=6, exportselection=False)
        self.cols_listbox.grid(row=0, column=4, sticky="ew", padx=(0, 10), pady=2)
        cols_scrollbar = ttk.Scrollbar(control_frame, orient="vertical", command=self.cols_listbox.yview)
        cols_scrollbar.grid(row=0, column=5, sticky="ns", pady=2)
        self.cols_listbox.configure(yscrollcommand=cols_scrollbar.set)

        # VALUES Section
        ttk.Label(control_frame, text="Values:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=2)
        self.vals_listbox = Listbox(control_frame, selectmode=MULTIPLE, height=6, exportselection=False)
        self.vals_listbox.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=2)
        vals_scrollbar = ttk.Scrollbar(control_frame, orient="vertical", command=self.vals_listbox.yview)
        vals_scrollbar.grid(row=1, column=2, sticky="ns", pady=2)
        self.vals_listbox.configure(yscrollcommand=vals_scrollbar.set)

        # AGGREGATION Function
        ttk.Label(control_frame, text="Aggregation:").grid(row=1, column=3, sticky="w", padx=(0, 5), pady=2)
        self.agg_func_var = tk.StringVar(value="sum")
        agg_combo = ttk.Combobox(control_frame, textvariable=self.agg_func_var, values=["sum", "mean", "count", "min", "max"], state="readonly", width=10)
        agg_combo.grid(row=1, column=4, sticky="w", padx=(0, 10), pady=2)

        # Generate Button
        generate_pivot_btn = ttk.Button(control_frame, text="Generate Pivot Table", command=self.generate_pivot_table)
        generate_pivot_btn.grid(row=1, column=5, sticky="e", padx=(0, 5), pady=2)

        # Result Frame (Bottom)
        result_frame = ttk.LabelFrame(tab, text="Pivot Table Result", padding="10")
        result_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)

        # Treeview for displaying the pivot table
        self.pivot_tree = ttk.Treeview(result_frame, show="headings")
        self.pivot_tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbars for Treeview
        pivot_yscroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.pivot_tree.yview)
        pivot_yscroll.grid(row=0, column=1, sticky="ns")
        pivot_xscroll = ttk.Scrollbar(result_frame, orient="horizontal", command=self.pivot_tree.xview)
        pivot_xscroll.grid(row=1, column=0, sticky="ew")
        self.pivot_tree.configure(yscrollcommand=pivot_yscroll.set, xscrollcommand=pivot_xscroll.set)

        # Initialize column lists
        self._populate_pivot_table_column_lists()

    def _populate_pivot_table_column_lists(self):
        """Populates the Listbox widgets with column names from `self.current_df`."""
        # Clear existing items
        self.rows_listbox.delete(0, tk.END)
        self.cols_listbox.delete(0, tk.END)
        self.vals_listbox.delete(0, tk.END)

        if self.current_df is not None:
            for col in self.current_df.columns:
                self.rows_listbox.insert(tk.END, col)
                self.cols_listbox.insert(tk.END, col)
                self.vals_listbox.insert(tk.END, col)

    def generate_pivot_table(self):
        """Generates a pivot table based on user selections and displays it in the Treeview."""
        if self.current_df is None:
            messagebox.showwarning("No Data", "No data in memory. Run a query using 'Store in Memory' first.", parent=self.master)
            return

        # Get selected indices
        row_indices = self.rows_listbox.curselection()
        col_indices = self.cols_listbox.curselection()
        val_indices = self.vals_listbox.curselection()

        # Get selected column names
        index_cols = [self.rows_listbox.get(i) for i in row_indices] if row_indices else None
        columns = [self.cols_listbox.get(i) for i in col_indices] if col_indices else None
        values = [self.vals_listbox.get(i) for i in val_indices] if val_indices else None
        agg_func = self.agg_func_var.get()

        if not values:
            messagebox.showwarning("No Values", "Please select at least one column for 'Values'.", parent=self.master)
            return

        try:
            # Create pivot table
            pivot_df = self.current_df.pivot_table(
                index=index_cols,
                columns=columns,
                values=values,
                aggfunc=agg_func,
                fill_value=0, # or NaN, depending on preference
                margins=False
            )

            # Clear existing treeview
            self.pivot_tree.delete(*self.pivot_tree.get_children())
            self.pivot_tree['columns'] = []

            # Handle MultiIndex for columns (from 'columns' and 'values')
            if isinstance(pivot_df.columns, pd.MultiIndex):
                # Flatten column names for display
                col_headers = [' | '.join([str(x) for x in col]).strip() for col in pivot_df.columns]
            else:
                col_headers = list(pivot_df.columns)

            # Handle MultiIndex for index
            if isinstance(pivot_df.index, pd.MultiIndex):
                index_names = list(pivot_df.index.names)
            else:
                index_names = [pivot_df.index.name] if pivot_df.index.name else ['Index']

            # Set up Treeview columns
            tree_columns = index_names + col_headers
            self.pivot_tree['columns'] = tree_columns

            # Configure column headings
            for col in tree_columns:
                col_id = str(col)  # ensure a concrete `str` (or use int(...) / typing.cast if you know it's an int)
                self.pivot_tree.heading(col_id, text=col_id)
                self.pivot_tree.column(col_id, anchor=tk.W, width=100)

            # Insert data
            for idx_tuple, row in pivot_df.iterrows():
                if isinstance(idx_tuple, tuple):
                    tree_row = list(idx_tuple)
                else:
                    tree_row = [idx_tuple]

                # Convert row values to list
                if isinstance(row, pd.Series):
                    row_values = row.tolist()
                else:
                    row_values = [row]

                # Combine index and value parts
                tree_row.extend(row_values)
                # Convert all items to string for display
                tree_row = [str(item) for item in tree_row]
                self.pivot_tree.insert("", tk.END, values=tree_row)

            self.status_bar.config(text=f"Pivot table generated with {len(pivot_df)} rows.")

        except Exception as e:
            messagebox.showerror("Pivot Error", f"Failed to create pivot table:\n{str(e)}", parent=self.master)
            self.status_bar.config(text="Error generating pivot table.")

    # -----------------------------
    # (Filters, Order By, Aggregate, History, Saved Tabs - Unchanged)
    # -----------------------------
    def _create_filters_tab(self, tab):
        tab.columnconfigure(0, weight=1); tab.rowconfigure(0, weight=1)
        filters_scroll_frame = ScrollableFrame(tab, fit_width=True)
        filters_scroll_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        filters_scroll_frame.scrollable_frame.columnconfigure(0, weight=1)
        for i, (name, props) in enumerate(config.FILTER_OPTIONS.items()):
            row_frame = ttk.Frame(filters_scroll_frame.scrollable_frame)
            row_frame.grid(row=i, column=0, sticky=tk.EW, pady=3)
            row_frame.columnconfigure(2, weight=1)
            ttk.Label(row_frame, text=f"{name}:").pack(side=tk.LEFT, padx=5)
            op_default = props.get("default_op", "")
            if isinstance(op_default, list):
                op_default = op_default[0] if op_default else ""
            op_var = tk.StringVar(value=op_default)
            op_values = props.get("operators", [])
            if isinstance(op_values, str):
                op_values = [op_values]
            op_combo = ttk.Combobox(row_frame, textvariable=op_var, values=op_values, width=8, state="readonly")
            op_combo.pack(side=tk.LEFT, padx=5)
            val_default = props.get("default_val", "")
            if isinstance(val_default, list):
                val_default = val_default[0] if val_default else ""
            val_var = tk.StringVar(value=val_default)
            time_var = None
            if props["type"] == "date" and TKCALENDAR_AVAILABLE:
                date_entry = DateEntry(row_frame, textvariable=val_var, width=12, state="readonly")
                date_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                default_time = "23:59:59" if "To" in name and props["default_op"] == "<=" else "00:00:00"
                time_var = tk.StringVar(value=default_time)
                time_entry = ttk.Entry(row_frame, textvariable=time_var, width=10)
                time_entry.pack(side=tk.LEFT, padx=2)
                ttk.Label(row_frame, text="(HH:MM:SS)", style="Hint.TLabel").pack(side=tk.LEFT, padx=0)
            else:
                entry = ttk.Entry(row_frame, textvariable=val_var)
                entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            if props.get("hint"):
                ttk.Label(row_frame, text=f"({props['hint']})", style="Hint.TLabel").pack(side=tk.LEFT, padx=5)
            self.filter_widgets[name] = {'op_var': op_var, 'val_var': val_var, 'time_var': time_var, 'props': props}

    def _create_order_by_tab(self, tab):
        tab.columnconfigure(0, weight=1); tab.rowconfigure(0, weight=1)
        self.order_by_scroll_frame = ScrollableFrame(tab, fit_width=True)
        self.order_by_scroll_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Button(tab, text="Add ORDER BY Condition", command=self.add_order_by_row).grid(row=1, column=0, pady=5, sticky=tk.N, padx=5)

    def _create_aggregate_tab(self, tab):
        tab.columnconfigure(0, weight=1); tab.rowconfigure(0, weight=1)
        self.aggregate_scroll_frame = ScrollableFrame(tab, fit_width=True)
        self.aggregate_scroll_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ttk.Button(tab, text="Add Custom Aggregate", command=self.add_custom_aggregate_row).grid(row=1, column=0, pady=5, sticky=tk.N, padx=5)

    def _create_history_tab(self, tab):
        tab.columnconfigure(0, weight=1); tab.rowconfigure(0, weight=1)
        history_frame = ttk.Frame(tab); history_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)
        history_frame.columnconfigure(0, weight=1); history_frame.rowconfigure(0, weight=1)
        self.history_tree = ttk.Treeview(history_frame, columns=("timestamp", "snippet"), show="headings")
        self.history_tree.heading("timestamp", text="Timestamp"); self.history_tree.heading("snippet", text="Query Snippet")
        self.history_tree.column("timestamp", width=150, stretch=False); self.history_tree.column("snippet", width=800)
        yscroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_tree.yview)
        xscroll = ttk.Scrollbar(history_frame, orient="horizontal", command=self.history_tree.xview)
        self.history_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.history_tree.grid(row=0, column=0, sticky=tk.NSEW); yscroll.grid(row=0, column=1, sticky=tk.NS); xscroll.grid(row=1, column=0, sticky=tk.EW)
        btn_frame = ttk.Frame(tab); btn_frame.grid(row=1, column=0, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(btn_frame, text="Load Selected Query", command=self.load_selected_query_from_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_selected_query_from_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear History", command=self.clear_query_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Save Selected to Favorites", command=self.save_selected_history_to_saved).pack(side=tk.LEFT, padx=5)
        self.populate_query_history_treeview()

    def _create_saved_tab(self, tab):
        tab.columnconfigure(0, weight=1); tab.rowconfigure(0, weight=1)
        saved_frame = ttk.Frame(tab); saved_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)
        saved_frame.columnconfigure(0, weight=1); saved_frame.rowconfigure(0, weight=1)
        self.saved_tree = ttk.Treeview(saved_frame, columns=("name", "snippet"), show="headings")
        self.saved_tree.heading("name", text="Name"); self.saved_tree.heading("snippet", text="Query Snippet")
        self.saved_tree.column("name", width=200, stretch=False); self.saved_tree.column("snippet", width=800)
        yscroll = ttk.Scrollbar(saved_frame, orient="vertical", command=self.saved_tree.yview)
        xscroll = ttk.Scrollbar(saved_frame, orient="horizontal", command=self.saved_tree.xview)
        self.saved_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.saved_tree.grid(row=0, column=0, sticky=tk.NSEW); yscroll.grid(row=0, column=1, sticky=tk.NS); xscroll.grid(row=1, column=0, sticky=tk.EW)
        btn_frame = ttk.Frame(tab); btn_frame.grid(row=1, column=0, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(btn_frame, text="Load Selected Saved Query", command=self.load_selected_saved_query).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_selected_saved_query).pack(side=tk.LEFT, padx=5)
        self.populate_saved_treeview()

    # -----------------------------
    # Dynamic UI Handlers (Add/Remove Rows)
    # -----------------------------
    def add_custom_bin_row(self, bin_val="", count_checked=False, percent_checked=False):
        row_frame = ttk.Frame(self.custom_bins_scroll_frame.scrollable_frame)
        row_frame.pack(fill=tk.X, pady=2, padx=5)
        bin_var, count_var, percent_var = tk.StringVar(value=str(bin_val)), tk.BooleanVar(value=count_checked), tk.BooleanVar(value=percent_checked)
        ttk.Label(row_frame, text="BIN:").pack(side=tk.LEFT)
        entry = ttk.Entry(row_frame, textvariable=bin_var, width=6)
        entry.pack(side=tk.LEFT, padx=(2, 5))
        ttk.Checkbutton(row_frame, text="Count", variable=count_var, command=self._refresh_dynamic_selects).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row_frame, text="Percentage", variable=percent_var, command=self._refresh_dynamic_selects).pack(side=tk.LEFT, padx=5)
        ttk.Button(row_frame, text="Remove", command=lambda r=row_frame: self.remove_custom_bin_row(r)).pack(side=tk.LEFT)
        entry.bind("<FocusOut>", lambda e: self._refresh_dynamic_selects())
        self.custom_bin_rows.append({'frame': row_frame, 'bin_var': bin_var, 'count_var': count_var, 'percent_var': percent_var})
        self.master.after(100, self.custom_bins_scroll_frame.on_configure, None)
        self._refresh_dynamic_selects()

    def remove_custom_bin_row(self, row_frame_to_remove):
        row_to_remove = next((r for r in self.custom_bin_rows if r['frame'] == row_frame_to_remove), None)
        if row_to_remove:
            row_to_remove['frame'].destroy()
            self.custom_bin_rows.remove(row_to_remove)
            self.master.after(100, self.custom_bins_scroll_frame.on_configure, None)
            self._refresh_dynamic_selects()

    def process_quick_add_bins(self):
        bins_str = self.quick_add_bins_entry_var.get().strip()
        if not bins_str: return
        added_count, skipped = 0, []
        for b in bins_str.split(','):
            b_str = b.strip()
            if b_str:
                try:
                    int(b_str)
                    self.add_custom_bin_row(bin_val=b_str, count_checked=True, percent_checked=True)
                    added_count += 1
                except ValueError:
                    skipped.append(b_str)
        self.quick_add_bins_entry_var.set("")
        if skipped: messagebox.showwarning("Quick Add Warning", f"Added {added_count} BINs.\nSkipped non-numeric: {', '.join(skipped)}", parent=self.master)
        self._refresh_dynamic_selects()

    def add_order_by_row(self):
        row_frame = ttk.Frame(self.order_by_scroll_frame.scrollable_frame)
        row_frame.pack(fill=tk.X, pady=2, padx=5)
        column_var, direction_var = tk.StringVar(), tk.StringVar(value="ASC")
        ttk.Label(row_frame, text="Column:").pack(side=tk.LEFT)
        col_combo = ttk.Combobox(row_frame, textvariable=column_var, values=self.orderable_column_display_names_for_combo, state="readonly")
        col_combo.pack(side=tk.LEFT, padx=(2, 10), fill=tk.X, expand=True)
        ttk.Label(row_frame, text="Sort:").pack(side=tk.LEFT)
        ttk.Combobox(row_frame, textvariable=direction_var, values=["ASC", "DESC"], width=8, state="readonly").pack(side=tk.LEFT, padx=(2, 10))
        ttk.Button(row_frame, text="Remove", command=lambda r=row_frame: self.remove_order_by_row(r)).pack(side=tk.LEFT)
        self.order_by_rows.append({'frame': row_frame, 'column_var': column_var, 'direction_var': direction_var, 'col_combo_widget': col_combo})
        if self.orderable_column_display_names_for_combo: column_var.set(self.orderable_column_display_names_for_combo[0])
        self.master.after(100, self.order_by_scroll_frame.on_configure, None)

    def remove_order_by_row(self, row_frame_to_remove):
        row = next((r for r in self.order_by_rows if r['frame'] == row_frame_to_remove), None)
        if row:
            row['frame'].destroy()
            self.order_by_rows.remove(row)
            self.master.after(100, self.order_by_scroll_frame.on_configure, None)

    def add_custom_aggregate_row(self):
        row_frame = ttk.Frame(self.aggregate_scroll_frame.scrollable_frame)
        row_frame.pack(fill=tk.X, pady=2, padx=5)
        func_var, col_var, alias_var = tk.StringVar(value="SUM"), tk.StringVar(), tk.StringVar()
        ttk.Label(row_frame, text="Function:").pack(side=tk.LEFT)
        ttk.Combobox(row_frame, textvariable=func_var, values=["SUM", "AVG", "MAX", "MIN", "COUNT"], width=8, state="readonly").pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(row_frame, text="Column:").pack(side=tk.LEFT)
        col_combo = ttk.Combobox(row_frame, textvariable=col_var, values=list(self.orderable_columns_map.values()) + self.dynamic_select_aliases, width=25)
        col_combo.pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(row_frame, text="Alias:").pack(side=tk.LEFT)
        ttk.Entry(row_frame, textvariable=alias_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 10))
        ttk.Button(row_frame, text="Remove", command=lambda r=row_frame: self.remove_custom_aggregate_row(r)).pack(side=tk.LEFT)
        self.custom_aggregate_rows.append({'frame': row_frame, 'func_var': func_var, 'col_var': col_var, 'alias_var': alias_var, 'col_combo_widget': col_combo})
        self.master.after(100, self.aggregate_scroll_frame.on_configure, None)

    def remove_custom_aggregate_row(self, row_frame_to_remove):
        row = next((r for r in self.custom_aggregate_rows if r['frame'] == row_frame_to_remove), None)
        if row:
            row['frame'].destroy()
            self.custom_aggregate_rows.remove(row)
            self.master.after(100, self.aggregate_scroll_frame.on_configure, None)

    # -----------------------------
    # UI Callbacks & State Updaters
    # -----------------------------
    def _update_orderable_columns_list_ui_callback(self, *args):
        self.orderable_columns_map.clear()
        for name, props in config.SELECT_OPTIONS.items():
            if self.select_vars.get(name) and self.select_vars[name].get() and not props.get("agg"):
                self.orderable_columns_map[name] = props.get('alias', props.get('sql'))
        self.orderable_column_display_names_for_combo = list(self.orderable_columns_map.keys())
        for row_data in self.order_by_rows:
            if row_data.get('col_combo_widget'):
                current = row_data['column_var'].get()
                row_data['col_combo_widget']['values'] = self.orderable_column_display_names_for_combo
                if current not in self.orderable_column_display_names_for_combo:
                    row_data['column_var'].set("")

        # Update the Pivot Table UI if it's open
        if self.current_df is not None:
            self._populate_pivot_table_column_lists()

        self._refresh_dynamic_selects()

    def _refresh_dynamic_selects(self):
        aliases = [p['alias'] for n, p in config.SELECT_OPTIONS.items() if p.get("agg") and self.select_vars.get(n) and self.select_vars[n].get() and p.get("alias")]
        if self.auto_range_enabled_var.get():
            try:
                start, end = int(self.auto_range_start_bin_var.get()), int(self.auto_range_end_bin_var.get())
                if start <= end:
                    for i in range(start, end + 1):
                        if self.auto_range_include_count_var.get(): aliases.append(f"bin_{i}count")
                        if self.auto_range_include_percentage_var.get(): aliases.append(f"bin{i}_pct")
            except ValueError: pass
        for row in self.custom_bin_rows:
            try:
                if row['bin_var'].get().strip():
                    num = int(row['bin_var'].get())
                    if row['count_var'].get(): aliases.append(f"bin_{num}count")
                    if row['percent_var'].get(): aliases.append(f"bin{num}_pct")
            except ValueError: pass
        # Only keep string aliases for sorting
        self.dynamic_select_aliases = sorted([a for a in set(aliases) if isinstance(a, str)])
        available_for_agg = list(self.orderable_columns_map.values()) + self.dynamic_select_aliases
        for row in self.custom_aggregate_rows:
            if row.get('col_combo_widget'):
                current = row['col_var'].get()
                row['col_combo_widget']['values'] = available_for_agg
                if current and current not in available_for_agg:
                    row['col_var'].set("")

    def _toggle_auto_range_controls_state(self):
        state = tk.NORMAL if self.auto_range_enabled_var.get() else tk.DISABLED
        self.auto_range_start_entry.config(state=state)
        self.auto_range_end_entry.config(state=state)
        self.auto_range_count_check.config(state=state)
        self.auto_range_percentage_check.config(state=state)
        self._refresh_dynamic_selects()

    # -----------------------------
    # Query history & saved queries UI
    # -----------------------------
    def add_to_query_history(self, sql_query):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snippet = ' '.join(sql_query.strip().split())[:120] + "..."
        self.query_history.append({'timestamp': timestamp, 'sql': sql_query, 'snippet': snippet})
        if len(self.query_history) > 50: self.query_history.pop(0)
        history_manager.save_history(self.query_history, self.history_file)
        self.populate_query_history_treeview()

    def populate_query_history_treeview(self):
        self.history_tree.delete(*self.history_tree.get_children())
        for record in reversed(self.query_history):
            self.history_tree.insert("", tk.END, values=(record['timestamp'], record['snippet']))

    def load_selected_query_from_history(self):
        selected = self.history_tree.selection()
        if selected:
            timestamp = self.history_tree.item(selected[0])['values'][0]
            record = next((r for r in self.query_history if r['timestamp'] == timestamp), None)
            if record:
                self.sql_output_text.delete('1.0', tk.END)
                self.sql_output_text.insert(tk.END, record['sql'])
                self.status_bar.config(text=f"Loaded query from history ({timestamp})")
                self._update_friendly_preview_from_sql(record['sql'])

    def delete_selected_query_from_history(self):
        selected = self.history_tree.selection()
        if selected:
            timestamp = self.history_tree.item(selected[0])['values'][0]
            self.query_history = [r for r in self.query_history if r['timestamp'] != timestamp]
            history_manager.save_history(self.query_history, self.history_file)
            self.populate_query_history_treeview()

    def clear_query_history(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear the entire query history?", parent=self.master):
            self.query_history.clear()
            history_manager.save_history(self.query_history, self.history_file)
            self.populate_query_history_treeview()

    def populate_saved_treeview(self):
        self.saved_tree.delete(*self.saved_tree.get_children())
        for record in reversed(self.saved_queries):
            snippet = ' '.join(record.get('sql', '').split())[:120] + "..."
            self.saved_tree.insert("", tk.END, values=(record.get('name', ''), snippet))

    def save_selected_history_to_saved(self):
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "No history item selected.", parent=self.master)
            return
        timestamp = self.history_tree.item(selected[0])['values'][0]
        record = next((r for r in self.query_history if r['timestamp'] == timestamp), None)
        if record:
            name = simpledialog.askstring("Save Query", "Enter a name for this query:", parent=self.master)
            if name:
                self.saved_queries.append({'name': name, 'sql': record['sql'], 'timestamp': datetime.datetime.now().isoformat()})
                history_manager.save_saved_queries(self.saved_queries, self.saved_file)
                self.populate_saved_treeview()
                self._update_saved_queries_dropdown()

    def load_selected_saved_query(self):
        selected = self.saved_tree.selection()
        if selected:
            name = self.saved_tree.item(selected[0])['values'][0]
            record = next((r for r in self.saved_queries if r.get('name') == name), None)
            if record:
                self.sql_output_text.delete('1.0', tk.END)
                self.sql_output_text.insert(tk.END, record['sql'])
                self.status_bar.config(text=f"Loaded saved query '{name}'")
                self._update_friendly_preview_from_sql(record['sql'])

    def delete_selected_saved_query(self):
        selected = self.saved_tree.selection()
        if selected:
            name = self.saved_tree.item(selected[0])['values'][0]
            self.saved_queries = [r for r in self.saved_queries if r.get('name') != name]
            history_manager.save_saved_queries(self.saved_queries, self.saved_file)
            self.populate_saved_treeview()
            self._update_saved_queries_dropdown()

    def _update_saved_queries_dropdown(self):
        names = [q.get('name', 'Unnamed') for q in self.saved_queries]
        self.saved_queries_combo['values'] = names
        if self.saved_queries_combo_var.get() not in names:
            self.saved_queries_combo_var.set("")

    def load_query_from_config_tab(self):
        name = self.saved_queries_combo_var.get()
        if not name: return
        record = next((r for r in self.saved_queries if r.get('name') == name), None)
        if record:
            self.sql_output_text.delete('1.0', tk.END)
            self.sql_output_text.insert(tk.END, record['sql'])
            self.status_bar.config(text=f"Loaded saved query '{name}'")
            self._update_friendly_preview_from_sql(record['sql'])

    # -----------------------------
    # General Actions & Helpers
    # -----------------------------
    def _set_friendly_preview_text(self, text):
        self.friendly_preview.config(state='normal')
        self.friendly_preview.delete('1.0', tk.END)
        self.friendly_preview.insert(tk.END, text)
        self.friendly_preview.config(state='disabled')

    def _update_friendly_preview_from_sql(self, sql):
        preview_text = "Loaded SQL from saved/history. Use 'Generate SQL' to refresh preview for current UI selections."
        self._set_friendly_preview_text(preview_text)

    def copy_to_clipboard(self):
        sql = self.sql_output_text.get('1.0', tk.END).strip()
        if sql and sql != ";":
            self.master.clipboard_clear(); self.master.clipboard_append(sql)
            self.status_bar.config(text="SQL copied to clipboard!")
        else:
            self.status_bar.config(text="Nothing to copy.")

    def copy_and_close(self):
        self.copy_to_clipboard()
        if self.sql_output_text.get('1.0', tk.END).strip():
            self.master.destroy()

    def reset_form(self):
        if not messagebox.askyesno("Confirm Reset", "Reset the form to defaults?", parent=self.master):
            return
        self.good_bins_var.set("1,2,3,4,5")
        self.select_distinct_var.set(False)
        self.deduplicate_wafer_entries_var.set(False)
        for name, var in self.select_vars.items():
            var.set(config.SELECT_OPTIONS[name]["default"])
        for row in self.custom_bin_rows[:]: self.remove_custom_bin_row(row['frame'])
        self.quick_add_bins_entry_var.set("")
        self.auto_range_enabled_var.set(False)
        self._toggle_auto_range_controls_state()
        for row in self.order_by_rows[:]: self.remove_order_by_row(row['frame'])
        for data in self.filter_widgets.values():
            props = data['props']
            data['op_var'].set(props["default_op"])
            data['val_var'].set(props.get("default_val", ""))
            if props['type'] == 'date' and data['time_var']:
                default_time = "23:59:59" if "To" in props.get("sql_col", "") else "00:00:00"
                data['time_var'].set(default_time)
        for row in self.custom_aggregate_rows[:]: self.remove_custom_aggregate_row(row['frame'])
        self.sql_output_text.delete('1.0', tk.END)
        self._update_orderable_columns_list_ui_callback()
        # Reset the current DataFrame
        self.current_df = None
        # Update the pivot table UI
        self._populate_pivot_table_column_lists()
        self.status_bar.config(text="Form has been reset.")
