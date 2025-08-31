# main.py
import tkinter as tk
from app import SQLFormatterApp

if __name__ == '__main__':
    """
    Main entry point for the SQL Formatter Application.
    Initializes the Tkinter root window and starts the main application loop.
    """
    root = tk.Tk()
    app = SQLFormatterApp(root)
    root.mainloop()