"""
Utility functions for the Mining Data Chatbot.

This module contains helper functions for data processing,
file operations, and common utilities.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent

def load_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Load a JSON file safely.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data or None if error
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}")
        return None

def save_json_file(data: Dict[str, Any], file_path: str) -> bool:
    """
    Save data to a JSON file safely.

    Args:
        data: Data to save
        file_path: Path to save the file

    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {e}")
        return False

def load_text_file(file_path: str) -> Optional[str]:
    """
    Load a text file safely.

    Args:
        file_path: Path to the text file

    Returns:
        File content or None if error
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error loading text file {file_path}: {e}")
        return None

def format_number(num: float, decimals: int = 2) -> str:
    """
    Format a number with specified decimal places.

    Args:
        num: Number to format
        decimals: Number of decimal places

    Returns:
        Formatted string
    """
    try:
        return f"{num:.{decimals}f}"
    except (ValueError, TypeError):
        return str(num)

def safe_get(data: Dict, key: str, default=None):
    """
    Safely get a value from a dictionary.

    Args:
        data: Dictionary to search
        key: Key to look for
        default: Default value if key not found

    Returns:
        Value or default
    """
    return data.get(key, default) if isinstance(data, dict) else default

def validate_file_exists(file_path: str) -> bool:
    """
    Check if a file exists.

    Args:
        file_path: Path to check

    Returns:
        True if file exists, False otherwise
    """
    return os.path.isfile(file_path)