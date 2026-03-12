#!/usr/bin/env python3
"""
VA Ticket Exporter
==================
Exports all open Virginia tickets (title starts with 'VA ' or 'VA2') to CSV
with ID, Title, Description, and Acceptance Criteria.

HTML is stripped from rich-text fields. CSV is UTF-8 with BOM for Excel.

Auth: Azure CLI (az login) or ADO_PAT environment variable.

Usage:
  python va_ticket_export.py
  python va_ticket_export.py --output C:/path/to/output
"""

import argparse
import base64
import csv
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from html.parser import HTMLParser

# ── Config ────────────────────────────────────────────────────────────────────
from config import ADO_PROJECT

ORG = "opusinspection"
PROJECT = ADO_PROJECT
BASE_URL = f"https://dev.azure.com/{ORG}/{PROJECT}"
API_VERSION = "7.1"


# ── HTML stripper ─────────────────────────────────────────────────────────────
class _HTMLStripper(HTMLParser):
    """Strip HTML tags, decode entities, normalize whitespace."""
    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "li", "tr"):
            self._parts.append("\n")
        if tag == "style":
            self._skip = True

    def handle_endtag(self, tag):
        if tag == "style":
            self._skip = False
        if tag in ("p", "div", "li", "tr", "ul", "ol", "table"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self):
        text = "".join(self._parts)
        # Collapse runs of whitespace on same line, normalize line breaks
        lines = text.splitlines()
        lines = [" ".join(line.split()) for line in lines]
        # Remove consecutive blank lines
        out = []
        for line in lines:
            if line or (out and out[-1]):
                out.append(line)
        return "\n".join(out).strip()


def strip_html(raw):
    """Convert HTML rich text to plain text."""
    if not raw:
        return ""
    stripper = _HTMLStripper()
    try:
        stripper.feed(raw)
        return stripper.get_text()
    except Exception:
        # Fallback: regex strip
        text = re.sub(r"<[^>]+>", " ", raw)
        return " ".join(text.split()).strip()


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_auth_headers():
    az_cmd = None
    for candidate in [
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
    ]:
        if os.path.isfile(candidate):
            az_cmd = candidate
            break

    try:
        if not az_cmd:
            raise FileNotFoundError
        result = subprocess.run(
            [az_cmd, "account", "get-access-token", "--resource", "499b84ac-1321-427f-aa17-267ca6975798"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            token = json.loads(result.stdout)["accessToken"]
            print("Auth: Azure CLI token")
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        pass

    pat = os.environ.get("ADO_PAT", "")
    if pat:
        auth = base64.b64encode(f":{pat}".encode()).decode()
        print("Auth: ADO_PAT env var")
        return {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

    print("ERROR: No auth. Use 'az login' or set ADO_PAT env var.")
    sys.exit(1)


# ── API helpers ───────────────────────────────────────────────────────────────
import requests

HEADERS = None


def refresh_token_if_needed(resp):
    global HEADERS
    if resp.status_code in (401, 403, 203):
        HEADERS = get_auth_headers()
        return True
    try:
        resp.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        HEADERS = get_auth_headers()
        return True
    return False


def api_post(url, body):
    for attempt in range(3):
        resp = requests.post(url, headers=HEADERS, json=body)
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 5)))
            continue
        if refresh_token_if_needed(resp) and attempt < 2:
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Export open VA tickets to CSV")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    args = parser.parse_args()
    output_dir = args.output or os.path.dirname(os.path.abspath(__file__))

    global HEADERS
    HEADERS = get_auth_headers()

    # 1. WIQL: open VA tickets
    wiql = {
        "query": """
            SELECT [System.Id]
            FROM WorkItems
            WHERE [System.TeamProject] = @project
              AND (
                  [System.Title] CONTAINS 'VA '
                  OR [System.Title] CONTAINS 'VA2'
              )
              AND [System.State] NOT IN ('Closed', 'Resolved', 'Done', 'Completed', 'Removed')
            ORDER BY [System.Id] DESC
        """
    }
    url = f"{BASE_URL}/_apis/wit/wiql?api-version={API_VERSION}"
    data = api_post(url, wiql)
    ids = [item["id"] for item in data.get("workItems", [])]
    print(f"WIQL returned {len(ids)} tickets matching VA title filter.")

    if not ids:
        print("No tickets found.")
        return

    # 2. Batch fetch - only the 4 fields we need
    fields = [
        "System.Id",
        "System.Title",
        "System.State",
        "System.Description",
        "Microsoft.VSTS.Common.AcceptanceCriteria",
    ]
    rows = []
    for i in range(0, len(ids), 200):
        batch = ids[i : i + 200]
        url = f"{BASE_URL}/_apis/wit/workitemsbatch?api-version={API_VERSION}"
        body = {"ids": batch, "fields": fields}
        data = api_post(url, body)
        for wi in data.get("value", []):
            f = wi["fields"]
            title = f.get("System.Title", "")
            # Filter: title must actually start with 'VA ' or 'VA2'
            if not (title.startswith("VA ") or title.startswith("VA2")):
                continue
            rows.append({
                "ID": wi["id"],
                "Title": title,
                "State": f.get("System.State", ""),
                "Description": strip_html(f.get("System.Description", "")),
                "Acceptance Criteria": strip_html(f.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")),
            })
        time.sleep(0.1)

    rows.sort(key=lambda r: r["ID"])
    print(f"Filtered to {len(rows)} tickets with title starting 'VA ' or 'VA2'.")

    # 3. Write CSV with UTF-8 BOM for Excel
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(output_dir, f"va_tickets_{timestamp}.csv")

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["ID", "Title", "State", "Description", "Acceptance Criteria"],
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV saved: {csv_path}")
    print(f"  {len(rows)} rows, 5 columns (ID, Title, State, Description, Acceptance Criteria)")


if __name__ == "__main__":
    main()
