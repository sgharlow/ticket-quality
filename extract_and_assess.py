#!/usr/bin/env python3
"""
Extract ADO ticket data from local cache and run quality assessment.
This script operates ENTIRELY on local cached data - NO MCP calls needed.

Prerequisites:
1. Run sync_cache.py --check to sync with ADO queries
2. If items need fetching, use Claude Code MCP to fetch them
3. Then run this script

Usage: python extract_and_assess.py
"""
import json
import os
import re
import csv
from datetime import datetime, timedelta
from config import CACHE_FILE, EXPECTED_IDS

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_expected_ids(cache):
    """Get expected IDs from cache metadata, fall back to config if not available."""
    metadata = cache.get('metadata', {})
    if 'expected_ids' in metadata:
        return set(metadata['expected_ids'])
    # Fall back to hardcoded list
    return set(EXPECTED_IDS)

def strip_html(text):
    """Remove HTML tags from text."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', str(text))
    clean = re.sub(r'\\s+', ' ', clean)
    return clean.strip()

def count_words(text):
    """Count words in text."""
    if not text:
        return 0
    words = text.split()
    return len(words)

def parse_date(date_str):
    """Parse ISO date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except:
        return None

def extract_fields(item):
    """Extract relevant fields from a work item."""
    fields = item.get('fields', {})
    return {
        'id': fields.get('System.Id', item.get('id', '')),
        'type': fields.get('System.WorkItemType', ''),
        'title': fields.get('System.Title', ''),
        'description': strip_html(fields.get('System.Description', '')),
        'acceptance_criteria': strip_html(fields.get('Microsoft.VSTS.Common.AcceptanceCriteria', '')),
        'created_by': fields.get('System.CreatedBy', ''),
        'state': fields.get('System.State', ''),
        'area_path': fields.get('System.AreaPath', ''),
        'start_date': fields.get('Microsoft.VSTS.Scheduling.StartDate', ''),
        'target_date': fields.get('Microsoft.VSTS.Scheduling.TargetDate', '')
    }

def assess_ticket(ticket):
    """Assess a single ticket and return grade, score, rationale."""
    desc = ticket['description']
    ac = ticket['acceptance_criteria']
    title = ticket['title']

    desc_words = count_words(desc)
    ac_words = count_words(ac)

    # Check for critical caps
    cap_grade = None
    cap_reason = ""

    if ac_words < 15 and desc_words < 10:
        cap_grade = 'F'
        cap_reason = "Both empty"
    elif desc_words < 10:
        cap_grade = 'D'
        cap_reason = "Empty Desc"
    elif ac_words < 15:
        cap_grade = 'C'
        cap_reason = "Empty AC"

    # Qualitative scoring (75 points)
    qual_score = 0

    # WHAT - Actions (15 pts)
    action_words = ['create', 'update', 'delete', 'validate', 'display', 'send', 'receive',
                    'process', 'generate', 'implement', 'add', 'remove', 'modify', 'enable',
                    'configure', 'support', 'allow', 'provide', 'ensure', 'verify']
    combined = (desc + " " + ac + " " + title).lower()
    action_count = sum(1 for w in action_words if w in combined)
    if action_count >= 4:
        qual_score += 13
    elif action_count >= 2:
        qual_score += 9
    elif action_count >= 1:
        qual_score += 5

    # WHO - Actor (10 pts)
    if 'as a ' in combined or 'as an ' in combined:
        qual_score += 9
    elif any(x in combined for x in ['user', 'admin', 'staff', 'inspector', 'customer', 'agent']):
        qual_score += 6
    else:
        qual_score += 2

    # WHY - Business Context (10 pts)
    if 'so that' in combined or 'in order to' in combined:
        qual_score += 9
    elif 'to ' in combined and any(x in combined for x in ['improve', 'enable', 'allow', 'support', 'ensure']):
        qual_score += 6
    else:
        qual_score += 2

    # HOW - Implementation Clarity (20 pts)
    detail_indicators = ['field', 'button', 'screen', 'page', 'api', 'database', 'table',
                        'column', 'report', 'email', 'notification', 'validation', 'rule']
    detail_count = sum(1 for w in detail_indicators if w in combined)
    if detail_count >= 4:
        qual_score += 17
    elif detail_count >= 2:
        qual_score += 12
    elif detail_count >= 1:
        qual_score += 7
    else:
        qual_score += 3

    # DONE - Testable Criteria (15 pts)
    if ac_words == 0:
        qual_score += 0
    elif 'given' in ac.lower() or 'when' in ac.lower() or 'then' in ac.lower():
        qual_score += 13
    elif any(x in ac.lower() for x in ['should', 'must', 'verify', 'confirm', 'ensure']):
        qual_score += 9
    elif ac_words >= 15:
        qual_score += 5
    else:
        qual_score += 2

    # EDGE - Exception Handling (5 pts)
    if any(x in combined for x in ['error', 'exception', 'invalid', 'boundary', 'edge case', 'fail']):
        qual_score += 4
    else:
        qual_score += 1

    # Quantitative scoring (25 points)
    quant_score = 0

    # Description substance (12 pts)
    if desc_words >= 75:
        quant_score += 12
    elif desc_words >= 50:
        quant_score += 10
    elif desc_words >= 25:
        quant_score += 7
    elif desc_words >= 10:
        quant_score += 4

    # AC substance (13 pts)
    if ac_words >= 75:
        quant_score += 13
    elif ac_words >= 40:
        quant_score += 10
    elif ac_words >= 20:
        quant_score += 7
    elif ac_words >= 15:
        quant_score += 4

    # Total score
    total_score = qual_score + quant_score

    # Determine grade
    if total_score >= 75:
        grade = 'A'
    elif total_score >= 55:
        grade = 'B'
    elif total_score >= 35:
        grade = 'C'
    elif total_score >= 20:
        grade = 'D'
    else:
        grade = 'F'

    # Apply cap
    grade_order = {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}
    if cap_grade and grade_order.get(grade, 0) > grade_order.get(cap_grade, 0):
        grade = cap_grade

    # Check for prelim
    start_date = parse_date(ticket['start_date'])
    today = datetime.now(start_date.tzinfo if start_date and start_date.tzinfo else None) if start_date else datetime.now()
    if start_date and (start_date.replace(tzinfo=None) - datetime.now()).days > 7:
        grade = f"Prelim: {grade}"

    # Build rationale
    rationale_parts = []
    if desc_words < 10:
        rationale_parts.append("Missing description")
    elif desc_words < 25:
        rationale_parts.append("Brief description")

    if ac_words < 15:
        rationale_parts.append("Missing AC")
    elif ac_words < 40:
        rationale_parts.append("Limited AC")

    if action_count < 2:
        rationale_parts.append("Unclear actions")

    if not rationale_parts:
        if total_score >= 75:
            rationale_parts.append("Well-defined with clear requirements")
        elif total_score >= 55:
            rationale_parts.append("Good detail with minor gaps")
        else:
            rationale_parts.append("Needs more detail")

    rationale = "; ".join(rationale_parts) + f" (Score: {total_score}/100)"

    return grade, total_score, rationale

def main():
    print("=" * 60)
    print("ADO Ticket Quality Assessment (Local Cache)")
    print("=" * 60)

    # Check cache exists
    if not os.path.exists(CACHE_FILE):
        print(f"\n*** ERROR: Cache file not found ***")
        print(f"File: {CACHE_FILE}")
        print("\nRun check_cache.py to see what data is needed.")
        return

    # Load cache
    print("\nLoading from local cache...")
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        cache = json.load(f)

    items = cache.get('work_items', [])
    metadata = cache.get('metadata', {})

    print(f"  Last updated: {metadata.get('last_updated', 'Unknown')}")
    print(f"  Total items in cache: {len(items)}")

    # Get expected IDs (from cache metadata or fallback to config)
    expected_set = get_expected_ids(cache)
    source = "cache metadata" if 'expected_ids' in metadata else "config.py (static)"
    print(f"  Expected IDs source: {source}")
    print(f"  Expected IDs count: {len(expected_set)}")

    # Filter to expected IDs only
    items = [item for item in items if (item.get('id') or item.get('fields', {}).get('System.Id')) in expected_set]
    print(f"  Items matching expected IDs: {len(items)}")

    if len(items) < len(expected_set):
        missing = len(expected_set) - len(items)
        print(f"\n*** WARNING: {missing} expected items not in cache ***")
        print("Run check_cache.py to see missing IDs.")

    # Extract fields and assess
    print("\nAssessing tickets...")
    tickets = [extract_fields(item) for item in items]

    results = []
    grade_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    prelim_count = 0

    for ticket in tickets:
        grade, score, rationale = assess_ticket(ticket)

        # Parse creator name
        created_by = str(ticket['created_by'])
        if isinstance(ticket['created_by'], dict):
            created_by = ticket['created_by'].get('displayName', str(ticket['created_by']))
        if '<' in created_by:
            created_by = created_by.split('<')[0].strip()

        # Format dates
        start_date = ticket['start_date'][:10] if ticket['start_date'] else ''
        target_date = ticket['target_date'][:10] if ticket['target_date'] else ''

        results.append({
            'ID': ticket['id'],
            'Work Item Type': ticket['type'],
            'Title': ticket['title'][:100] + '...' if len(ticket['title']) > 100 else ticket['title'],
            'State': ticket['state'],
            'Created By': created_by,
            'Start Date': start_date,
            'Target Date': target_date,
            'Grade': grade,
            'Score': score,
            'Rationale': rationale
        })

        # Count grades
        base_grade = grade.replace('Prelim: ', '')
        grade_counts[base_grade] = grade_counts.get(base_grade, 0) + 1
        if 'Prelim' in grade:
            prelim_count += 1

    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Write CSV report
    csv_file = os.path.join(OUTPUT_DIR, f"Q12026_Features_quality_report_{timestamp}.csv")
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['ID', 'Work Item Type', 'Title', 'State', 'Created By',
                                                'Start Date', 'Target Date', 'Grade', 'Score', 'Rationale'])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nCSV report saved: {csv_file}")

    # Generate summary
    total = len(results)
    summary = []
    summary.append("=" * 80)
    summary.append("TICKET QUALITY ASSESSMENT REPORT")
    summary.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary.append(f"Input: Q1 2026 Committed Features & User Stories (Local Cache)")
    summary.append(f"Total Tickets Assessed: {total}")
    summary.append("=" * 80)
    summary.append("")
    summary.append("GRADE DISTRIBUTION")
    summary.append("-" * 40)
    summary.append("Overall:")
    for g in ['A', 'B', 'C', 'D', 'F']:
        count = grade_counts.get(g, 0)
        pct = (count / total * 100) if total > 0 else 0
        summary.append(f"  {g}: {count} ({pct:.1f}%)")

    summary.append("")
    summary.append("Prelim vs Imminent:")
    summary.append(f"  Prelim (>7 days): {prelim_count} tickets")
    summary.append(f"  Imminent (<=7 days): {total - prelim_count} tickets")

    # Risk assessment
    summary.append("")
    summary.append("RISK ASSESSMENT")
    summary.append("-" * 40)

    f_imminent = [r for r in results if r['Grade'] == 'F']
    d_imminent = [r for r in results if r['Grade'] == 'D']

    summary.append(f"F-grade imminent (IMMEDIATE RISK): {len(f_imminent)}")
    for r in f_imminent[:10]:
        summary.append(f"  {r['ID']}: {r['Title'][:60]}...")

    summary.append("")
    summary.append(f"D-grade imminent (HIGH RISK): {len(d_imminent)}")
    for r in d_imminent[:10]:
        summary.append(f"  {r['ID']}: {r['Title'][:60]}...")

    # Action by creator
    summary.append("")
    summary.append("ACTION REQUIRED BY CREATOR")
    summary.append("-" * 40)

    creator_issues = {}
    for r in results:
        if r['Grade'] in ['F', 'D'] or r['Grade'].endswith('F') or r['Grade'].endswith('D'):
            creator = r['Created By']
            if not creator:
                creator = "(Unknown)"
            if creator not in creator_issues:
                creator_issues[creator] = {'F': [], 'D': []}
            base_grade = r['Grade'].replace('Prelim: ', '')
            if base_grade in creator_issues[creator]:
                creator_issues[creator][base_grade].append(str(r['ID']))

    for creator, issues in sorted(creator_issues.items()):
        if issues['F'] or issues['D']:
            summary.append(f"\n{creator}:")
            if issues['F']:
                summary.append(f"  F-Grade: {', '.join(issues['F'][:20])}")
                if len(issues['F']) > 20:
                    summary.append(f"    ... and {len(issues['F'])-20} more")
            if issues['D']:
                summary.append(f"  D-Grade: {', '.join(issues['D'][:20])}")
                if len(issues['D']) > 20:
                    summary.append(f"    ... and {len(issues['D'])-20} more")

    # Write summary
    summary_text = '\n'.join(summary)
    summary_file = os.path.join(OUTPUT_DIR, f"Q12026_Features_summary_{timestamp}.txt")
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary_text)

    print(f"Summary report saved: {summary_file}")
    print("\n" + summary_text)

if __name__ == "__main__":
    main()
