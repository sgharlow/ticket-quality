#!/usr/bin/env python3
"""
Sync cache helper for ADO ticket quality assessment.
This script compares query results with cache and outputs what needs to be fetched.

Usage:
    python sync_cache.py --check <ids_file>     # Check what's missing from cache
    python sync_cache.py --update-ids <ids>     # Update expected IDs in cache metadata
    python sync_cache.py --status               # Show current sync status

The <ids_file> should contain JSON array of work item IDs from ADO queries.
"""
import json
import os
import sys
import argparse
from datetime import datetime
from config import CACHE_FILE, REQUIRED_FIELDS, ADO_PROJECT

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

def get_cached_ids(cache):
    """Get set of IDs currently in cache."""
    ids = set()
    for item in cache.get('work_items', []):
        item_id = item.get('id') or item.get('fields', {}).get('System.Id')
        if item_id:
            ids.add(int(item_id))
    return ids

def check_completeness(item):
    """Check if item has Description or AcceptanceCriteria."""
    fields = item.get('fields', {})
    desc = fields.get('System.Description', '')
    ac = fields.get('Microsoft.VSTS.Common.AcceptanceCriteria', '')
    return bool(desc) or bool(ac)

def check_sync_status(query_ids):
    """Compare query IDs with cache and return sync status."""
    cache = load_cache()
    cached_ids = get_cached_ids(cache)
    query_id_set = set(query_ids)

    # Find differences
    missing_ids = query_id_set - cached_ids  # In query but not in cache
    removed_ids = cached_ids - query_id_set  # In cache but not in query
    common_ids = query_id_set & cached_ids   # In both

    # Check completeness of cached items
    incomplete_ids = []
    for item in cache.get('work_items', []):
        item_id = item.get('id') or item.get('fields', {}).get('System.Id')
        if item_id and int(item_id) in common_ids and not check_completeness(item):
            incomplete_ids.append(int(item_id))

    return {
        'query_count': len(query_ids),
        'cache_count': len(cached_ids),
        'missing_ids': sorted(missing_ids),
        'removed_ids': sorted(removed_ids),
        'incomplete_ids': sorted(incomplete_ids),
        'needs_fetch': sorted(missing_ids | set(incomplete_ids))
    }

def print_status(status):
    """Print sync status in readable format."""
    print("=" * 60)
    print("ADO TICKET QUALITY - SYNC STATUS")
    print("=" * 60)
    print(f"\nQuery results: {status['query_count']} items")
    print(f"Cache contains: {status['cache_count']} items")
    print()

    if status['missing_ids']:
        print(f"NEW items to fetch: {len(status['missing_ids'])}")
        if len(status['missing_ids']) <= 20:
            print(f"  IDs: {status['missing_ids']}")
        else:
            print(f"  First 20: {status['missing_ids'][:20]}")
            print(f"  ... and {len(status['missing_ids']) - 20} more")
    else:
        print("NEW items to fetch: 0")

    print()

    if status['removed_ids']:
        print(f"REMOVED from queries: {len(status['removed_ids'])}")
        if len(status['removed_ids']) <= 20:
            print(f"  IDs: {status['removed_ids']}")
        else:
            print(f"  First 20: {status['removed_ids'][:20]}")
    else:
        print("REMOVED from queries: 0")

    print()

    if status['incomplete_ids']:
        print(f"INCOMPLETE in cache: {len(status['incomplete_ids'])}")
    else:
        print("INCOMPLETE in cache: 0")

    print()
    print("=" * 60)

    if status['needs_fetch']:
        print(f"TOTAL IDs needing fetch: {len(status['needs_fetch'])}")
        print()
        # Output in batches of 50 for MCP
        ids = status['needs_fetch']
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i+batch_size]
            print(f"Batch {i//batch_size + 1}: {batch}")
    else:
        print("Cache is fully synced - no fetch needed!")

def update_expected_ids(query_ids):
    """Update the expected_ids in cache metadata."""
    cache = load_cache()
    cache['metadata']['expected_ids'] = sorted(query_ids)
    cache['metadata']['expected_count'] = len(query_ids)
    cache['metadata']['last_query_sync'] = datetime.now().isoformat()
    save_cache(cache)
    print(f"Updated expected IDs: {len(query_ids)} items")

def remove_stale_items(query_ids):
    """Remove items from cache that are no longer in queries."""
    cache = load_cache()
    query_id_set = set(query_ids)

    original_count = len(cache.get('work_items', []))
    cache['work_items'] = [
        item for item in cache.get('work_items', [])
        if (item.get('id') or item.get('fields', {}).get('System.Id')) in query_id_set
    ]
    new_count = len(cache['work_items'])

    removed = original_count - new_count
    if removed > 0:
        save_cache(cache)
        print(f"Removed {removed} stale items from cache")
    else:
        print("No stale items to remove")

def main():
    parser = argparse.ArgumentParser(description='Sync cache with ADO query results')
    parser.add_argument('--check', metavar='IDS_FILE', help='Check what needs to be fetched')
    parser.add_argument('--update-ids', metavar='IDS_FILE', help='Update expected IDs from file')
    parser.add_argument('--clean', metavar='IDS_FILE', help='Remove items not in query results')
    parser.add_argument('--status', action='store_true', help='Show current cache status')
    parser.add_argument('--json', action='store_true', help='Output in JSON format')

    args = parser.parse_args()

    if args.status:
        cache = load_cache()
        expected = cache.get('metadata', {}).get('expected_ids', [])
        if expected:
            status = check_sync_status(expected)
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                print_status(status)
        else:
            print("No expected IDs in cache metadata. Run --check with query results first.")
        return

    if args.check:
        with open(args.check, 'r', encoding='utf-8') as f:
            data = json.load(f)
        query_ids = data if isinstance(data, list) else data.get('ids', [])

        status = check_sync_status(query_ids)

        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print_status(status)

        # Also update expected IDs
        update_expected_ids(query_ids)
        return

    if args.update_ids:
        with open(args.update_ids, 'r', encoding='utf-8') as f:
            data = json.load(f)
        query_ids = data if isinstance(data, list) else data.get('ids', [])
        update_expected_ids(query_ids)
        return

    if args.clean:
        with open(args.clean, 'r', encoding='utf-8') as f:
            data = json.load(f)
        query_ids = data if isinstance(data, list) else data.get('ids', [])
        remove_stale_items(query_ids)
        return

    parser.print_help()

if __name__ == "__main__":
    main()
