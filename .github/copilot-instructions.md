# SQL Refactor Project - AI Assistant Guide

This is a Python-based SQL query builder and analyzer tool with a Tkinter GUI. Here's what you need to know to help develop it effectively:

## Architecture Overview

- **Main Components**:
  - `app.py`: Core GUI application (SQLFormatterApp class)
  - `sql_builder.py`: SQL generation logic (independent of UI)
  - `history_manager.py`: Query history persistence
  - `config.py`: Configuration settings
  - `main.py`: Application entry point

## Key Patterns

### UI Structure
- Uses tabbed interface with distinct functional areas:
  - Query configuration
  - Column selection
  - Custom BINs
  - WHERE filters
  - ORDER BY
  - Aggregates
  - History/Saved queries
  - Pivot table analysis

### Data Flow
1. User configures query parameters through UI
2. Parameters passed to sql_builder.py
3. Generated SQL displayed in output panel
4. Query can be:
   - Executed against DB
   - Saved to history
   - Exported to Excel
   - Used for pivot table analysis

### GUI Patterns
- Consistent use of ttk widgets with 'clam' theme
- Scrollable frames for dynamic content
- Tooltips for user guidance
- Grid/pack layout managers used appropriately
- Canvas-based scrolling for lists

### State Management
- Application state centralized in SQLFormatterApp
- Query history persisted to JSON files
- Config settings in separate module
- In-memory DataFrame for pivot tables

## Common Tasks

### Adding a New Feature
1. Add UI elements to appropriate tab in app.py
2. Implement handlers in SQLFormatterApp class
3. Update sql_builder.py if query generation affected
4. Add any new config options to config.py

### Debugging Tips
- Check self.status_bar for error messages
- Use print() statements in sql_builder.py
- Examine query history JSON for state issues
- Watch for ttk widget configuration errors

## Dependencies
Required packages:
```
tkinter
tkcalendar (optional, enhances date inputs)
pandas (for pivot tables)
oracledb (for database connections)
```

## Project-Specific Conventions
- Class methods prefixed with '_' are internal
- UI handlers grouped by functionality
- Error handling via custom QueryGenerationError
- Tab creation methods follow _create_X_tab pattern
- DB credentials stored in constants (not ideal)
