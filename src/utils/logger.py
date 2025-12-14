"""Simple logging utility for MVP"""

# Global log level (0=errors only, 1=info, 2=debug, 3=verbose)
_LOG_LEVEL = 1

def set_log_level(level):
    """Set global log level

    Args:
        level: 0 (errors only), 1 (info), 2 (debug), 3 (verbose)
    """
    global _LOG_LEVEL
    _LOG_LEVEL = level

def log_info(message):
    """Log info message"""
    if _LOG_LEVEL >= 1:
        print(f"[INFO] {message}")

def log_error(message):
    """Log error message"""
    if _LOG_LEVEL >= 0:
        print(f"[ERROR] {message}")

def log_debug(message):
    """Log debug message"""
    if _LOG_LEVEL >= 2:
        print(f"[DEBUG] {message}")

def log_warning(message):
    """Log warning message"""
    if _LOG_LEVEL >= 1:
        print(f"[WARNING] {message}")

def log_verbose(message):
    """Log verbose message (very detailed)"""
    if _LOG_LEVEL >= 3:
        print(f"[VERBOSE] {message}")
