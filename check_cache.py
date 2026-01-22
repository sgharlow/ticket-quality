#!/usr/bin/env python3
"""
Check cache status - shows what's cached, what's missing, and field completeness.
Run this FIRST to determine if MCP fetches are needed.

Usage: python check_cache.py
"""
import json
import os
from config import EXPECTED_IDS, REQUIRED_FIELDS, CACHE_FILE

def check_item_completeness(item):
    """Check if item has all required fields with actual content."""
    fields = item.get('fields', {})

    # Critical fields that MUST have content for quality assessment
    desc = fields.get('System.Description', '')
    ac = fields.get('Microsoft.VSTS.Common.AcceptanceCriteria', '')

    # Item is "complete" if it has Description OR AcceptanceCriteria
    # (some legitimate items may only have one)
    has_content = bool(desc) or bool(ac)

    return {
        'has_description': bool(desc),
        'has_ac': bool(ac),
        'has_content': has_content,
        'desc_length': len(str(desc)) if desc else 0,
        'ac_length': len(str(ac)) if ac else 0
    }

def main():
    print("=" * 70)
    print("ADO TICKET QUALITY - CACHE STATUS CHECK")
    print("=" * 70)

    expected_set = set(EXPECTED_IDS)
    print(f"\nExpected items: {len(expected_set)}")

    # Load cache
    if not os.path.exists(CACHE_FILE):
        print(f"\n❌ Cache file not found: {CACHE_FILE}")
        print("\nTo populate cache, use Claude Code with MCP to fetch work items.")
        print(f"Project: A TDC Master Project")
        print(f"Required fields: {REQUIRED_FIELDS}")
        print(f"\nMissing IDs ({len(expected_set)} total):")
        for i in range(0, len(EXPECTED_IDS), 50):
            batch = EXPECTED_IDS[i:i+50]
            print(f"  Batch {i//50 + 1}: {batch}")
        return

    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        cache = json.load(f)

    items = cache.get('work_items', [])
    cached_ids = {item.get('id') or item.get('fields', {}).get('System.Id') for item in items}

    print(f"Cached items: {len(cached_ids)}")

    # Check for missing IDs
    missing_ids = sorted(expected_set - cached_ids)
    extra_ids = sorted(cached_ids - expected_set)

    print(f"Missing items: {len(missing_ids)}")
    if extra_ids:
        print(f"Extra items (not in expected list): {len(extra_ids)}")

    # Check field completeness
    complete_items = 0
    incomplete_items = []

    for item in items:
        item_id = item.get('id') or item.get('fields', {}).get('System.Id')
        if item_id not in expected_set:
            continue

        status = check_item_completeness(item)
        if status['has_content']:
            complete_items += 1
        else:
            incomplete_items.append(item_id)

    print(f"\nField completeness (Description or AC present):")
    print(f"  Complete: {complete_items}")
    print(f"  Incomplete: {len(incomplete_items)}")

    # Summary
    print("\n" + "=" * 70)
    if not missing_ids and not incomplete_items:
        print("✅ CACHE IS COMPLETE - Ready for quality assessment!")
        print("   Run: python extract_and_assess.py")
    else:
        print("⚠️  CACHE NEEDS UPDATES")

        if missing_ids:
            print(f"\n📋 MISSING IDs - Need to fetch {len(missing_ids)} items via MCP:")
            print("-" * 50)
            for i in range(0, len(missing_ids), 50):
                batch = missing_ids[i:i+50]
                print(f"\nBatch {i//50 + 1} ({len(batch)} items): {batch}")

            print("\n" + "-" * 50)
            print("MCP FETCH INSTRUCTIONS:")
            print("-" * 50)
            print(f"Project: A TDC Master Project")
            print(f"Fields to request: {REQUIRED_FIELDS}")
            print("\nUse: mcp__ado__wit_get_work_items_batch_by_ids")
            print("  project: 'A TDC Master Project'")
            print("  ids: [batch of up to 200 IDs]")
            print(f"  fields: {REQUIRED_FIELDS}")

        if incomplete_items:
            print(f"\n📋 INCOMPLETE ITEMS - {len(incomplete_items)} items missing Description/AC:")
            print(f"   IDs: {incomplete_items[:20]}{'...' if len(incomplete_items) > 20 else ''}")
            print("   These need to be re-fetched with full fields.")

if __name__ == "__main__":
    main()
