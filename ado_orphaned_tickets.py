#!/usr/bin/env python3
"""
ADO Orphaned Ticket Finder
==========================
Finds tickets with comments but no meaningful follow-up action.
These are tickets getting ignored or forgotten after someone commented.

Scope: All open work items created in the last year with at least 1 comment.

Setup:
  1. pip install requests
  2. Make sure you're logged in: az login
  3. python ado_orphaned_tickets.py

Authentication (tried in order):
  1. Azure CLI (az login) -- matches your existing ADO MCP setup
  2. ADO_PAT environment variable (fallback)

Options:
  --days N     Stale threshold in days (default: 30)
  --output DIR Directory for output files (default: script directory)

Output:
  - Console summary
  - orphaned_tickets_YYYYMMDD.csv  (for Excel / Power BI)
  - orphaned_tickets_YYYYMMDD.json (for programmatic use)
"""

import argparse
import requests
import base64
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

from config import ADO_PROJECT

# ── Config ────────────────────────────────────────────────────────────────────
ORG = "opusinspection"
PROJECT = ADO_PROJECT  # "A TDC Master Project" from config.py

BASE_URL = f"https://dev.azure.com/{ORG}/{PROJECT}"
API_VERSION = "7.1"

# Fields to IGNORE when determining if a revision is a meaningful action.
# Anything NOT in this set (and not WEF_*) counts as material follow-up.
#
# Three categories:
#   1. System bookkeeping — ADO auto-updates these on every save
#   2. Insignificant changes — bulk/automated, not a response to a comment
#   3. Companion fields — auto-set alongside a primary field change
IGNORE_FIELDS = {
    # ── System bookkeeping (auto-updated every revision) ──
    "System.Rev",
    "System.AuthorizedDate",
    "System.RevisedDate",
    "System.ChangedDate",
    "System.ChangedBy",
    "System.AuthorizedAs",
    "System.PersonId",
    "System.Watermark",
    "System.CommentCount",
    "System.History",                # the comment itself, not an action
    "System.IsDeleted",

    # ── Insignificant / bulk operations ──
    "Microsoft.VSTS.Common.BacklogPriority",  # drag-and-drop board reordering
    "System.BoardColumn",                      # auto-set when state changes
    "System.BoardColumnDone",                  # auto-set when state changes

    # ── Companion fields (always fire alongside a primary field) ──
    # State change companions (primary: System.State)
    "System.Reason",
    "Microsoft.VSTS.Common.StateChangeDate",
    "Microsoft.VSTS.Common.ActivatedDate",
    "Microsoft.VSTS.Common.ActivatedBy",
    "Microsoft.VSTS.Common.ClosedDate",
    "Microsoft.VSTS.Common.ClosedBy",
    # Iteration change companions (primary: System.IterationId)
    "System.IterationLevel2",
    "System.IterationLevel3",
    "System.IterationLevel4",
    "System.IterationLevel5",
    # Area change companions (primary: System.AreaId)
    "System.NodeName",
    "System.AreaLevel1",
    "System.AreaLevel2",
    "System.AreaLevel3",
}
# Also ignore Kanban board extension markers (WEF_*) -- auto-set when
# items move on boards, not deliberate field edits.


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_auth_headers():
    """Get auth headers -- tries Azure CLI first, then PAT env var."""

    # Method 1: Azure CLI token (matches existing az login setup)
    az_cmd = None
    az_candidates = [
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
    ]
    for candidate in az_candidates:
        if os.path.isfile(candidate):
            az_cmd = candidate
            break

    try:
        if not az_cmd:
            raise FileNotFoundError("az CLI not found")
        result = subprocess.run(
            [az_cmd, "account", "get-access-token", "--resource", "499b84ac-1321-427f-aa17-267ca6975798"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            token_data = json.loads(result.stdout)
            token = token_data["accessToken"]
            print("Auth: Using Azure CLI token (az login)")
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        pass

    # Method 2: PAT from environment variable
    pat = os.environ.get("ADO_PAT", "")
    if pat:
        auth = base64.b64encode(f":{pat}".encode()).decode()
        print("Auth: Using ADO_PAT environment variable")
        return {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
        }

    print("ERROR: No authentication available.")
    print("  Option 1: az login  (recommended -- matches your MCP setup)")
    print("  Option 2: set ADO_PAT=<your-personal-access-token>")
    sys.exit(1)


# ── API Helpers ───────────────────────────────────────────────────────────────
HEADERS = None  # initialized in main()


def refresh_token_if_needed(resp):
    """If we get a 401/non-JSON response, refresh the Azure CLI token."""
    global HEADERS
    if resp.status_code in (401, 403) or resp.status_code == 203:
        print("  Token expired, refreshing...")
        HEADERS = get_auth_headers()
        return True
    try:
        resp.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        print("  Non-JSON response (likely token expired), refreshing...")
        HEADERS = get_auth_headers()
        return True
    return False


def api_get(url):
    """GET with retry on 429/auth errors."""
    for attempt in range(3):
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 5))
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        if refresh_token_if_needed(resp) and attempt < 2:
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


def api_post(url, body):
    """POST with retry on 429/auth errors."""
    for attempt in range(3):
        resp = requests.post(url, headers=HEADERS, json=body)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 5))
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        if refresh_token_if_needed(resp) and attempt < 2:
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


# ── Step 1: WIQL query for candidates ────────────────────────────────────────
def get_candidate_ids():
    """Get IDs of all open work items created in the last year with comments."""
    one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    wiql = {
        "query": f"""
            SELECT [System.Id]
            FROM WorkItems
            WHERE [System.TeamProject] = @project
              AND [System.CreatedDate] >= '{one_year_ago}'
              AND [System.CommentCount] > 0
              AND [System.State] NOT IN ('Closed', 'Resolved', 'Done', 'Completed', 'Removed')
            ORDER BY [System.CreatedDate] DESC
        """
    }

    url = f"{BASE_URL}/_apis/wit/wiql?api-version={API_VERSION}"
    data = api_post(url, wiql)
    ids = [item["id"] for item in data.get("workItems", [])]
    print(f"WIQL returned {len(ids)} candidate work items.")
    return ids


# ── Step 2: Batch-fetch work item details ────────────────────────────────────
def get_work_items_batch(ids):
    """Fetch title, state, assignedTo, dates for a list of IDs (max 200/batch)."""
    fields = [
        "System.Id",
        "System.Title",
        "System.State",
        "System.WorkItemType",
        "System.AssignedTo",
        "System.CreatedDate",
        "System.ChangedDate",
        "System.CommentCount",
        "System.AreaPath",
    ]
    items = {}
    for i in range(0, len(ids), 200):
        batch = ids[i : i + 200]
        url = f"{BASE_URL}/_apis/wit/workitemsbatch?api-version={API_VERSION}"
        body = {"ids": batch, "fields": fields}
        data = api_post(url, body)
        for wi in data.get("value", []):
            f = wi["fields"]
            items[wi["id"]] = {
                "id": wi["id"],
                "title": f.get("System.Title", ""),
                "type": f.get("System.WorkItemType", ""),
                "state": f.get("System.State", ""),
                "assigned_to": (f.get("System.AssignedTo") or {}).get("displayName", "Unassigned"),
                "created_date": f.get("System.CreatedDate", ""),
                "changed_date": f.get("System.ChangedDate", ""),
                "comment_count": f.get("System.CommentCount", 0),
                "area_path": f.get("System.AreaPath", ""),
            }
        time.sleep(0.1)  # gentle rate limiting
    return items


# ── Step 3: Analyze update history per work item ─────────────────────────────
def get_updates(work_item_id):
    """Get all revisions/updates for a work item."""
    url = f"{BASE_URL}/_apis/wit/workItems/{work_item_id}/updates?api-version={API_VERSION}"
    return api_get(url).get("value", [])


def has_meaningful_changes(revision):
    """True if the revision includes any field change beyond system bookkeeping."""
    fields = revision.get("fields", {})
    for field_name in fields:
        if field_name in IGNORE_FIELDS:
            continue
        if field_name.startswith("WEF_"):  # Kanban board extensions
            continue
        return True
    return False


def is_comment_only(revision):
    """True if the revision added a comment but changed no actionable fields."""
    fields = revision.get("fields", {})
    has_comment = "System.History" in fields and fields["System.History"].get("newValue")
    return has_comment and not has_meaningful_changes(revision)


def get_revision_date(update):
    """Get the actual date this revision was created.

    IMPORTANT: The top-level 'revisedDate' on an update is when the revision
    was SUPERSEDED (i.e., when the NEXT edit happened), NOT when this revision
    was created.  The correct creation date is fields.System.ChangedDate.newValue.
    """
    fields = update.get("fields", {})
    changed = fields.get("System.ChangedDate", {})
    return changed.get("newValue") or update.get("revisedDate")


def get_revision_author(update):
    """Get who actually made this revision.

    IMPORTANT: The top-level 'revisedBy' on an update is who made the NEXT
    revision, NOT who made this one.  The correct author is
    fields.System.ChangedBy.newValue.
    """
    fields = update.get("fields", {})
    changed_by = fields.get("System.ChangedBy", {}).get("newValue")
    if changed_by:
        if isinstance(changed_by, dict):
            return changed_by.get("displayName", "Unknown")
        return str(changed_by)
    # Fallback: revisedBy (may be wrong for intermediate revisions,
    # but is correct for the latest revision where revisedDate=9999)
    return (update.get("revisedBy") or {}).get("displayName", "Unknown")


def analyze_ticket(work_item_id, stale_threshold_days):
    """
    Returns orphan info dict if the ticket's last comment had no follow-up,
    or None if the ticket is healthy.
    """
    updates = get_updates(work_item_id)
    if not updates:
        return None

    # Walk backwards to find the most recent comment-only revision
    last_comment_idx = None
    last_comment_date = None
    last_comment_by = None

    for idx in range(len(updates) - 1, -1, -1):
        u = updates[idx]
        if is_comment_only(u):
            last_comment_idx = idx
            last_comment_date = get_revision_date(u)
            last_comment_by = get_revision_author(u)
            break

    if last_comment_idx is None:
        return None  # no comment-only revisions at all

    # Check if any meaningful action happened AFTER that comment
    for u in updates[last_comment_idx + 1 :]:
        if has_meaningful_changes(u):
            return None  # there was follow-up -- ticket is fine

    # Calculate staleness
    if last_comment_date:
        try:
            comment_dt = datetime.fromisoformat(last_comment_date.replace("Z", "+00:00"))
            days_stale = (datetime.now(comment_dt.tzinfo) - comment_dt).days
        except (ValueError, TypeError):
            days_stale = None
    else:
        days_stale = None

    # Only flag if stale beyond threshold
    if days_stale is not None and days_stale < stale_threshold_days:
        return None

    return {
        "last_comment_date": last_comment_date,
        "last_comment_by": last_comment_by,
        "days_since_comment": days_stale,
    }


# ── Step 4: Main orchestration ───────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Find orphaned ADO tickets with unanswered comments")
    parser.add_argument("--days", type=int, default=30,
                        help="Stale threshold in days (default: 30)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory (default: script directory)")
    args = parser.parse_args()

    stale_threshold_days = args.days
    output_dir = args.output or os.path.dirname(os.path.abspath(__file__))

    # Auth
    global HEADERS
    HEADERS = get_auth_headers()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"ADO Orphaned Ticket Finder")
    print(f"Org: {ORG}  |  Project: {PROJECT}")
    print(f"Stale threshold: {stale_threshold_days} days")
    print(f"Output dir: {output_dir}")
    print(f"{'=' * 60}\n")

    # 1. Get candidate IDs
    candidate_ids = get_candidate_ids()
    if not candidate_ids:
        print("No candidates found. Check your project name and auth permissions.")
        return

    # 2. Batch-fetch metadata
    print("Fetching work item metadata...")
    items = get_work_items_batch(candidate_ids)

    # 3. Analyze each ticket's update history
    orphaned = []
    total = len(candidate_ids)
    print(f"Analyzing {total} tickets for orphaned comments...\n")

    for i, wid in enumerate(candidate_ids):
        if (i + 1) % 25 == 0 or i == 0:
            print(f"  [{i + 1}/{total}] analyzing...")

        result = analyze_ticket(wid, stale_threshold_days)
        if result and wid in items:
            entry = {**items[wid], **result}
            entry["url"] = f"https://dev.azure.com/{ORG}/{PROJECT}/_workitems/edit/{wid}"
            orphaned.append(entry)

        time.sleep(0.05)  # gentle rate limiting

    # 4. Sort by staleness (most stale first)
    orphaned.sort(key=lambda x: x.get("days_since_comment") or 0, reverse=True)

    # 5. Output results
    print(f"\n{'=' * 60}")
    print(f"ORPHANED TICKETS: {len(orphaned)} of {total} candidates")
    print(f"{'=' * 60}\n")

    if not orphaned:
        print("No orphaned tickets found -- all comments had follow-up actions.")
        return

    # Console summary (top 30)
    for t in orphaned[:30]:
        days = t.get("days_since_comment", "?")
        print(f"  #{t['id']}  [{t['type']}]  {t['state']}")
        print(f"    {t['title'][:80]}")
        print(f"    Assigned: {t['assigned_to']}  |  Last comment by: {t['last_comment_by']}")
        print(f"    Days stale: {days}  |  Comment date: {t['last_comment_date']}")
        print(f"    {t['url']}")
        print()

    if len(orphaned) > 30:
        print(f"  ... and {len(orphaned) - 30} more (see CSV/JSON output)\n")

    # CSV export
    csv_path = os.path.join(output_dir, f"orphaned_tickets_{timestamp}.csv")
    csv_fields = [
        "id", "type", "title", "state", "assigned_to", "area_path",
        "created_date", "changed_date", "comment_count",
        "last_comment_date", "last_comment_by", "days_since_comment", "url",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(orphaned)
    print(f"CSV saved: {csv_path}")

    # JSON export
    json_path = os.path.join(output_dir, f"orphaned_tickets_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(orphaned, f, indent=2, default=str)
    print(f"JSON saved: {json_path}")

    # Summary stats
    print(f"\n{'-' * 40}")
    print(f"Summary:")
    print(f"  Total candidates scanned: {total}")
    print(f"  Orphaned tickets found:   {len(orphaned)}")
    print(f"  Orphan rate:              {len(orphaned)/total*100:.1f}%")
    if orphaned:
        days_list = [t.get("days_since_comment", 0) or 0 for t in orphaned]
        print(f"  Avg days stale:           {sum(days_list)/len(days_list):.0f}")
        print(f"  Median days stale:        {sorted(days_list)[len(days_list)//2]}")
        print(f"  Max days stale:           {max(days_list)}")

    # By assignee breakdown
    by_assignee = {}
    for t in orphaned:
        name = t["assigned_to"]
        by_assignee[name] = by_assignee.get(name, 0) + 1
    print(f"\n  By assignee:")
    for name, count in sorted(by_assignee.items(), key=lambda x: -x[1]):
        print(f"    {name}: {count}")

    # By type breakdown
    by_type = {}
    for t in orphaned:
        tp = t["type"]
        by_type[tp] = by_type.get(tp, 0) + 1
    print(f"\n  By type:")
    for tp, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {tp}: {count}")

    # By state breakdown
    by_state = {}
    for t in orphaned:
        st = t["state"]
        by_state[st] = by_state.get(st, 0) + 1
    print(f"\n  By state:")
    for st, count in sorted(by_state.items(), key=lambda x: -x[1]):
        print(f"    {st}: {count}")


if __name__ == "__main__":
    main()
