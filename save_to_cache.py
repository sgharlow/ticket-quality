#!/usr/bin/env python3
"""
Save work items to local cache.
This script is called by Claude Code after each MCP batch fetch to immediately persist data.

Usage (from Claude Code):
1. Fetch batch via MCP with fields parameter
2. Call this script with the JSON data piped in or as a file

Can also be used to merge multiple JSON files into the cache.
"""
import json
import os
import sys
from datetime import datetime
from config import CACHE_FILE, REQUIRED_FIELDS

def load_cache():
    """Load existing cache or create empty one."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"metadata": {}, "work_items": []}

def save_cache(cache):
    """Save cache to file."""
    cache['metadata']['last_updated'] = datetime.now().isoformat()
    cache['metadata']['total_items'] = len(cache['work_items'])

    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2)

    print(f"Cache saved: {len(cache['work_items'])} items")
    print(f"File: {CACHE_FILE}")

def add_items_to_cache(new_items, cache):
    """Add or update items in cache, merging fields for completeness."""
    # Index existing items by ID
    existing = {}
    for item in cache.get('work_items', []):
        item_id = item.get('id') or item.get('fields', {}).get('System.Id')
        if item_id:
            existing[item_id] = item

    # Add/update with new items
    added = 0
    updated = 0
    for item in new_items:
        item_id = item.get('id') or item.get('fields', {}).get('System.Id')
        if not item_id:
            continue

        if item_id in existing:
            # Merge fields: keep the more complete data for each field
            old_fields = existing[item_id].get('fields', {})
            new_fields = item.get('fields', {})

            merged_fields = dict(old_fields)  # Start with old fields

            # For each new field, use it if old is missing/empty or new is longer
            for key, new_value in new_fields.items():
                old_value = merged_fields.get(key)
                # Use new value if old is missing, empty, or new is more substantial
                if old_value is None or old_value == '':
                    merged_fields[key] = new_value
                elif new_value and len(str(new_value)) > len(str(old_value)):
                    merged_fields[key] = new_value

            # Check if anything actually changed
            if merged_fields != old_fields:
                existing[item_id]['fields'] = merged_fields
                updated += 1
        else:
            existing[item_id] = item
            added += 1

    cache['work_items'] = list(existing.values())
    return added, updated

def main():
    # Check for input file argument
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        if os.path.exists(input_file):
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            print(f"File not found: {input_file}")
            sys.exit(1)
    else:
        # Read from stdin
        print("Reading JSON from stdin...")
        data = json.load(sys.stdin)

    # Handle different input formats
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and 'work_items' in data:
        items = data['work_items']
    elif isinstance(data, dict) and 'value' in data:
        items = data['value']
    else:
        items = [data] if isinstance(data, dict) else []

    if not items:
        print("No items found in input")
        sys.exit(1)

    print(f"Processing {len(items)} items...")

    # Load and update cache
    cache = load_cache()
    added, updated = add_items_to_cache(items, cache)

    print(f"Added: {added}, Updated: {updated}")

    # Save
    save_cache(cache)

if __name__ == "__main__":
    main()
