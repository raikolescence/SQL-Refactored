# history_manager.py
"""
Handles loading and saving of query history and saved (favorite) queries.
All functions are self-contained and interact directly with the filesystem.
"""

import json
import os

def load_history(filepath):
    """Loads query history from a JSON file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading query history from {filepath}: {e}")
    return []

def save_history(history_list, filepath):
    """Saves the current query history to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump(history_list, f, indent=2)
    except Exception as e:
        print(f"Error saving query history to {filepath}: {e}")

def load_saved_queries(filepath):
    """Loads saved queries from a JSON file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading saved queries from {filepath}: {e}")
    return []

def save_saved_queries(queries_list, filepath):
    """Saves the current list of saved queries to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump(queries_list, f, indent=2)
    except Exception as e:
        print(f"Error saving saved queries to {filepath}: {e}")