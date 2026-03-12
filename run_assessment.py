#!/usr/bin/env python3
"""
Self-updating ADO Ticket Quality Assessment Runner.

This script orchestrates the full workflow:
1. Queries ADO for current work item IDs (requires Claude Code MCP)
2. Compares with local cache
3. Identifies new/removed items
4. Runs quality assessment

For fully automated runs (when cache is current):
    python run_assessment.py

To sync with ADO first (outputs MCP commands if needed):
    python run_assessment.py --sync

Usage in Claude Code:
    "Run the ticket quality assessment and sync with ADO if needed"
"""
import json
import os
import sys
import subprocess
from datetime import datetime
from config import CACHE_FILE, ADO_QUERIES, ADO_PROJECT, REQUIRED_FIELDS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_cache():
    """Load existing cache."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"metadata": {}, "work_items": []}

def get_cached_ids(cache):
    """Get set of IDs currently in cache."""
    ids = set()
    for item in cache.get('work_items', []):
        item_id = item.get('id') or item.get('fields', {}).get('System.Id')
        if item_id:
            ids.add(int(item_id))
    return ids

def run_assessment():
    """Run the quality assessment."""
    result = subprocess.run(
        [sys.executable, os.path.join(BASE_DIR, 'extract_and_assess.py')],
        capture_output=False
    )
    return result.returncode == 0

def print_sync_instructions(query_ids, cache):
    """Print instructions for syncing via Claude Code MCP."""
    cached_ids = get_cached_ids(cache)
    query_id_set = set(query_ids)

    missing_ids = query_id_set - cached_ids
    removed_ids = cached_ids - query_id_set

    print("\n" + "=" * 60)
    print("SYNC REQUIRED - MCP Commands for Claude Code")
    print("=" * 60)

    if removed_ids:
        print(f"\nItems removed from queries: {len(removed_ids)}")
        print("Run: python sync_cache.py --clean current_query_ids.json")

    if missing_ids:
        print(f"\nNew items to fetch: {len(missing_ids)}")
        print(f"IDs: {sorted(missing_ids)}")
        print(f"\nFetch command for Claude Code:")
        print(f'  Fetch work items {sorted(missing_ids)} from project "{ADO_PROJECT}"')
        print(f'  with fields: {REQUIRED_FIELDS}')
        print(f"\nThen save to cache:")
        print(f"  python save_to_cache.py <response.json>")

    if not missing_ids and not removed_ids:
        print("\nCache is in sync with ADO queries!")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Run ADO ticket quality assessment')
    parser.add_argument('--sync', action='store_true',
                       help='Check if sync is needed and print MCP commands')
    parser.add_argument('--query-ids', metavar='FILE',
                       help='JSON file with current query IDs (from ADO)')
    args = parser.parse_args()

    print("=" * 60)
    print("ADO Ticket Quality Assessment - Self-Updating Runner")
    print("=" * 60)

    cache = load_cache()
    metadata = cache.get('metadata', {})

    # Check if we have expected IDs in cache
    if 'expected_ids' not in metadata:
        print("\nNo expected IDs in cache metadata.")
        print("Run sync_cache.py --check with query results first.")
        print("\nOr provide query IDs file: python run_assessment.py --query-ids <file>")

        if args.query_ids and os.path.exists(args.query_ids):
            with open(args.query_ids, 'r') as f:
                query_ids = json.load(f)
            if isinstance(query_ids, dict):
                query_ids = query_ids.get('ids', [])
            print_sync_instructions(query_ids, cache)
        return

    expected_ids = metadata['expected_ids']
    cached_ids = get_cached_ids(cache)
    expected_set = set(expected_ids)

    print(f"\nExpected: {len(expected_ids)} items")
    print(f"Cached: {len(cached_ids)} items")
    print(f"Last sync: {metadata.get('last_query_sync', 'Unknown')}")

    # Check sync status
    missing = expected_set - cached_ids
    extra = cached_ids - expected_set

    if missing:
        print(f"\nMissing from cache: {len(missing)} items")
        if args.sync:
            print(f"IDs: {sorted(missing)}")

    if extra:
        print(f"Extra in cache (not in queries): {len(extra)} items")

    if args.sync and (missing or extra):
        print_sync_instructions(expected_ids, cache)
        return

    # Run assessment
    print("\nRunning quality assessment...")
    print("-" * 60)
    success = run_assessment()

    if success:
        print("\nAssessment complete!")
    else:
        print("\nAssessment failed. Check errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
