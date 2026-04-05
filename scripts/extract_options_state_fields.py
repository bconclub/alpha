#!/usr/bin/env python3
"""
Extract all field names from options_state dict in options_scalp.py
for database schema verification.

Usage: python scripts/extract_options_state_fields.py
"""

import re
import ast
from pathlib import Path


def extract_state_fields(filepath: str) -> set[str]:
    """Extract field names from state dict assignments in Python file."""
    content = Path(filepath).read_text()
    
    # Find all state = { ... } blocks
    pattern = r'state\s*=\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
    matches = re.findall(pattern, content, re.DOTALL)
    
    fields = set()
    for block in matches:
        # Extract quoted keys
        keys = re.findall(r'"(\w+)"\s*:', block)
        fields.update(keys)
    
    return fields


def main():
    filepath = "engine/alpha/strategies/options_scalp.py"
    fields = extract_state_fields(filepath)
    
    print("═" * 60)
    print("Extracted options_state fields from code:")
    print("═" * 60)
    for field in sorted(fields):
        print(f'  "{field}"')
    print("═" * 60)
    print(f"Total: {len(fields)} fields")
    print()
    print("SQL to verify all columns exist:")
    print("-" * 60)
    print("SELECT column_name, data_type ")
    print("FROM information_schema.columns ")
    print("WHERE table_name = 'options_state' ")
    print("ORDER BY ordinal_position;")


if __name__ == "__main__":
    main()
