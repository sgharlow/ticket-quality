# ADO Ticket Quality Assessment - Installation & Usage Guide

## Overview

This solution provides batch quality assessment for Azure DevOps work items (Features and User Stories) within Claude Code. It grades tickets on an A-F scale based on completeness, clarity, and testability.

### Key Features

- **Local Caching**: All data stored locally to prevent loss during context compaction
- **Batch Fetching**: Efficient MCP calls with explicit field requests
- **Offline Assessment**: Run quality checks entirely from local cache
- **Incremental Updates**: Only fetch what's missing or incomplete

### Components

| Component | Purpose |
|-----------|---------|
| `config.py` | Central configuration - ADO queries, fields, paths |
| `check_cache.py` | Shows cache status and identifies gaps |
| `save_to_cache.py` | Saves MCP fetch results to local cache (smart field merging) |
| `extract_and_assess.py` | Runs quality assessment from local cache |
| `sync_cache.py` | Syncs cache with current ADO query results |
| `run_assessment.py` | Orchestrates full workflow with auto-sync detection |

---

## Prerequisites

### Required Software

| Software | Version | Purpose | Install Command |
|----------|---------|---------|-----------------|
| Python | 3.8+ | Run assessment scripts | [python.org](https://python.org) |
| Node.js | 18+ | Run ADO MCP server | [nodejs.org](https://nodejs.org) |
| npm | 9+ | Install MCP packages | Included with Node.js |
| Claude Code | Latest | CLI interface | `npm install -g @anthropic-ai/claude-code` |

### Verify Installation

```powershell
python --version    # Should show Python 3.8+
node --version      # Should show v18+
npm --version       # Should show 9+
claude --version    # Should show Claude Code version
```

---

## Installation

### Step 1: Create Directory Structure

```powershell
# Create the project folder
New-Item -ItemType Directory -Path "$env:USERPROFILE\Desktop\ado-ticket-quality" -Force

# Create Claude Code config folder in user profile (if not exists)
New-Item -ItemType Directory -Path "$env:USERPROFILE\.claude" -Force
```

**Note:** The `.claude` folder must be in your user profile root (e.g., `C:\Users\YourName\.claude`), NOT on the Desktop.

### Step 2: Copy Files

Copy these files to the target PC:

| Source File | Destination |
|-------------|-------------|
| `config.py` | `Desktop\ado-ticket-quality\` |
| `check_cache.py` | `Desktop\ado-ticket-quality\` |
| `save_to_cache.py` | `Desktop\ado-ticket-quality\` |
| `sync_cache.py` | `Desktop\ado-ticket-quality\` |
| `run_assessment.py` | `Desktop\ado-ticket-quality\` |
| `extract_and_assess.py` | `Desktop\ado-ticket-quality\` |
| `INSTALL_AND_USAGE.md` | `Desktop\ado-ticket-quality\` |

**Note:** `mcp.json` must be CREATED manually (see Step 3) - it is not included in the source files.

**File structure:**
```
C:\Users\YourName\
├── Desktop\
│   └── ado-ticket-quality\
│       ├── config.py              # Configuration (ADO queries, fields)
│       ├── check_cache.py         # Cache status checker
│       ├── save_to_cache.py       # Save MCP results to cache
│       ├── sync_cache.py          # Sync cache with ADO queries
│       ├── run_assessment.py      # Full workflow orchestrator
│       ├── extract_and_assess.py  # Quality assessment
│       └── ado_workitems_cache.json  # Local cache (created on first run)
└── .claude\
    └── mcp.json                   # MCP server configuration (YOU CREATE THIS)
```

### Step 3: Configure ADO MCP Server

Create a new file at `C:\Users\YourName\.claude\mcp.json` with the following content:

```json
{
  "mcpServers": {
    "ado": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/claude-code-mcp-adapter", "npx", "-y", "@azure-devops/mcp", "opusinspection"]
    }
  }
}
```

**To change organization**: Replace `opusinspection` with your Azure DevOps organization name.

**How it works:**
- The MCP (Model Context Protocol) server allows Claude Code to communicate with Azure DevOps
- `@azure-devops/mcp` is the ADO MCP server package (installed automatically via npx)
- `@anthropic-ai/claude-code-mcp-adapter` bridges Claude Code with the MCP server
- The last argument (`opusinspection`) is your ADO organization name

### Step 4: Configure Azure DevOps Authentication

The ADO MCP server uses Azure CLI for authentication.

```powershell
# Install Azure CLI if not present
winget install Microsoft.AzureCLI

# Login to Azure (use your corporate account)
az login

# Verify you're logged in
az account show

# Set default organization (optional but recommended)
az devops configure --defaults organization=https://dev.azure.com/opusinspection
```

**Note:** You must have access to the Azure DevOps organization. If you get "Unauthorized" errors, contact your ADO administrator.

### Step 5: Restart Claude Code

Close and reopen Claude Code for the MCP configuration to take effect.

### Step 6: Verify MCP Connection

In Claude Code, test the connection by asking:
```
List the projects in Azure DevOps
```

If configured correctly, Claude will use the `mcp__ado__core_list_projects` tool and return your ADO projects.

---

## Usage - Optimized Workflow

### Quick Start (Assessment Only)

If the cache already has data:

```powershell
cd Desktop\ado-ticket-quality
python extract_and_assess.py
```

This runs the assessment entirely from local cache - no MCP calls needed.

### Self-Updating Workflow (Recommended)

Use the orchestrator script for automatic sync detection:

```powershell
cd Desktop\ado-ticket-quality
python run_assessment.py
```

This will:
1. Check if cache is in sync with ADO queries
2. Report any missing or extra items
3. Run the quality assessment

If sync is needed, use:
```powershell
python run_assessment.py --sync
```

This outputs MCP commands to fetch missing items.

### Full Workflow

#### Step 1: Check Cache Status

```powershell
python check_cache.py
```

Output shows:
- How many items are cached vs expected
- Which items are missing
- Which items are incomplete (missing Description/AC)

#### Step 2: Fetch Missing/Incomplete Items (In Claude Code)

If items are missing or incomplete, fetch them via MCP in Claude Code:

```
Fetch work items [IDs] from project "A TDC Master Project" with fields:
System.Id, System.WorkItemType, System.Title, System.Description,
Microsoft.VSTS.Common.AcceptanceCriteria, System.CreatedBy, System.State,
System.AreaPath, Microsoft.VSTS.Scheduling.StartDate, Microsoft.VSTS.Scheduling.TargetDate
```

Claude Code will use `mcp__ado__wit_get_work_items_batch_by_ids` with the fields parameter.

**IMPORTANT**: Always include the `fields` parameter to ensure Description and AcceptanceCriteria are fetched.

#### Step 3: Save Fetched Data to Cache

After Claude Code fetches items, save the JSON response:

```powershell
python save_to_cache.py batch_response.json
```

Or pipe directly:
```powershell
echo '<json_data>' | python save_to_cache.py
```

#### Step 4: Run Assessment

```powershell
python extract_and_assess.py
```

Outputs:
- `Q12026_Features_quality_report_TIMESTAMP.csv` - Detailed results
- `Q12026_Features_summary_TIMESTAMP.txt` - Executive summary

---

## Updating Expected Work Item IDs

The system uses ADO query GUIDs defined in `config.py` to dynamically determine expected work items:

```python
ADO_QUERIES = {
    "Q1 2026 Committed Features": "973996cc-b2c6-49fe-935b-f043f474f4cd",
    "Q1 2026 Committed User Stories": "1e9d9cc6-ffee-4ed3-a8d1-b8881451b294"
}
```

### Syncing with Current Query Results

When query results change (new items added, items removed):

1. Run query sync via Claude Code:
   ```
   Run the ADO queries and sync the cache with current results
   ```

2. Or manually with sync_cache.py:
   ```powershell
   # After getting query results as JSON
   python sync_cache.py --check query_results.json
   ```

3. Fetch any missing items, then run assessment:
   ```powershell
   python run_assessment.py
   ```

### Changing Queries

To assess different queries, update `config.py` with new query GUIDs:

1. Find the query GUID in ADO (query URL contains the GUID)
2. Update `ADO_QUERIES` dictionary
3. Run `python sync_cache.py --check` with new query results

---

## Output Files

### CSV Report

**Filename:** `Q12026_Features_quality_report_{timestamp}.csv`

| Column | Description |
|--------|-------------|
| ID | Work item ID |
| Work Item Type | Feature or User Story |
| Title | Work item title |
| State | Current state |
| Created By | Ticket author |
| Start Date | Planned start date |
| Target Date | Planned completion date |
| Grade | Quality grade (A-F, may have "Prelim:" prefix) |
| Score | Numeric score (0-100) |
| Rationale | Brief explanation of score |

### Summary Report

**Filename:** `Q12026_Features_summary_{timestamp}.txt`

**Sections:**
- Grade Distribution (A-F counts and percentages)
- Prelim vs Imminent breakdown
- Risk Assessment (F/D grades by urgency)
- Action Required by Creator (tickets by owner)

---

## Grading Methodology

### Grade Scale

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 75-100 | Developer-ready |
| B | 55-74 | Good with minor gaps |
| C | 35-54 | Needs clarification |
| D | 20-34 | Major gaps |
| F | 0-19 | Cannot determine what to build |

### Critical Caps

| Condition | Maximum Grade |
|-----------|---------------|
| Acceptance Criteria < 15 words | C |
| Description < 10 words | D |
| Both empty/minimal | F |

### Scoring Dimensions (100 points total)

**Qualitative (75 points):**
- WHAT - Actions Defined: 15 pts
- WHO - Actor Identified: 10 pts
- WHY - Business Context: 10 pts
- HOW - Implementation Clarity: 20 pts
- DONE - Testable Criteria: 15 pts
- EDGE - Exception Handling: 5 pts

**Quantitative (25 points):**
- Description Substance: 12 pts
- Acceptance Criteria Substance: 13 pts

### Prelim Tagging

Tickets with Start Date > 7 days from today are prefixed with "Prelim:" to indicate they have time for improvement before work begins.

---

## Troubleshooting

### MCP Server Not Working

**Symptom:** MCP tools not available in Claude Code, or "tool not found" errors

**Solutions:**
1. Verify `mcp.json` exists in `C:\Users\YourName\.claude\` (NOT Desktop\.claude)
2. Check the JSON syntax is valid (no trailing commas, proper quotes)
3. Restart Claude Code after adding/modifying MCP config
4. Check Node.js is installed: `node --version` (requires v18+)
5. Test MCP manually in terminal:
   ```powershell
   npx -y @azure-devops/mcp opusinspection
   ```
   This should start without errors (press Ctrl+C to exit)
6. Check Azure CLI is logged in: `az account show`

### Azure Authentication Failed

**Symptom:** "Unauthorized" or "Authentication required" errors

**Solutions:**
```powershell
az logout
az login
az account show
```

### Cache Shows "Incomplete" Items

**Symptom:** check_cache.py shows many incomplete items

**Cause:** Items were fetched without the `fields` parameter, so Description/AcceptanceCriteria are missing.

**Solution:** Re-fetch those specific IDs with the full fields list:
```
fields: ["System.Id", "System.WorkItemType", "System.Title", "System.Description",
         "Microsoft.VSTS.Common.AcceptanceCriteria", "System.CreatedBy", "System.State",
         "System.AreaPath", "Microsoft.VSTS.Scheduling.StartDate", "Microsoft.VSTS.Scheduling.TargetDate"]
```

### Windows Encoding Errors

**Symptom:** UnicodeEncodeError with special characters

**Cause:** Windows console uses cp1252 encoding which doesn't support all Unicode characters

**Solution:** As of v2.2, all scripts use ASCII-compatible characters. If you encounter encoding errors with older versions, update to the latest version from GitHub.

### Many Tickets Have F Grades

**Cause:** This often reflects the actual state of tickets in ADO - many tickets genuinely lack Description or Acceptance Criteria.

**Action:** Use the "ACTION REQUIRED BY CREATOR" section in the summary report to identify who needs to improve their tickets.

---

## Why Local Caching?

The local caching approach was designed to solve these problems:

1. **Context Compaction**: Long Claude Code sessions compact context, losing previously fetched data
2. **Repeated MCP Calls**: Without caching, the same data must be re-fetched each session
3. **Incomplete Data**: MCP calls without explicit `fields` parameter return minimal data
4. **Large Datasets**: 396 work items exceed what can be reasonably held in context

**Benefits:**
- Assessment runs instantly from local cache
- No data loss between sessions
- Incremental updates - only fetch what's needed
- Full field data preserved permanently

---

## File Reference

### config.py

Central configuration file containing:
- `ADO_QUERIES` - Dictionary of query names to GUIDs (dynamic ID lookup)
- `REQUIRED_FIELDS` - Fields that must be fetched from ADO
- `ADO_PROJECT` - Project name ("A TDC Master Project")
- `CACHE_FILE` - Path to local cache JSON file

### check_cache.py

Usage: `python check_cache.py`

Shows:
- Total items in cache vs expected
- Missing item IDs
- Incomplete items (missing Description/AC)
- Completeness percentage

### save_to_cache.py

Usage: `python save_to_cache.py [json_file]`

- Reads JSON from file or stdin
- Merges with existing cache using smart field merging
- For each field: keeps the non-empty or more complete value
- Reports added/updated counts

### sync_cache.py

Usage: `python sync_cache.py [options]`

Options:
- `--check <file>` - Check query results JSON against cache
- `--clean <file>` - Remove items not in query results

Syncs the local cache with current ADO query results.

### run_assessment.py

Usage: `python run_assessment.py [options]`

Options:
- `--sync` - Output MCP commands for syncing if needed
- `--query-ids <file>` - Provide query IDs JSON file

Orchestrates the full workflow:
1. Checks cache vs expected IDs
2. Reports sync status
3. Runs quality assessment

### extract_and_assess.py

Usage: `python extract_and_assess.py`

- Loads data from local cache only (no MCP calls)
- Filters to expected IDs from config.py
- Runs quality assessment algorithm
- Generates CSV and summary reports

### ado_workitems_cache.json

Local cache file containing:
```json
{
  "metadata": {
    "last_updated": "2026-01-21T17:00:00",
    "total_items": 396
  },
  "work_items": [
    { "id": 12345, "fields": { ... } },
    ...
  ]
}
```

---

## Quick Start Checklist

- [ ] Python 3.8+ installed
- [ ] Node.js 18+ installed
- [ ] Claude Code installed
- [ ] `config.py` copied to `Desktop\ado-ticket-quality\`
- [ ] `check_cache.py` copied to `Desktop\ado-ticket-quality\`
- [ ] `save_to_cache.py` copied to `Desktop\ado-ticket-quality\`
- [ ] `sync_cache.py` copied to `Desktop\ado-ticket-quality\`
- [ ] `run_assessment.py` copied to `Desktop\ado-ticket-quality\`
- [ ] `extract_and_assess.py` copied to `Desktop\ado-ticket-quality\`
- [ ] `mcp.json` CREATED at `C:\Users\YourName\.claude\mcp.json`
- [ ] Azure CLI installed and logged in (`az login`)
- [ ] Claude Code restarted after MCP config
- [ ] MCP connection verified (test with "List ADO projects")
- [ ] Cache populated (via MCP fetch + save_to_cache.py)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-21 | Initial release with skills-based approach |
| 2.0 | 2026-01-21 | Complete rewrite with local caching strategy |
|     |            | - Added config.py for central configuration |
|     |            | - Added check_cache.py for cache inspection |
|     |            | - Added save_to_cache.py for MCP result storage |
|     |            | - Added extract_and_assess.py for offline assessment |
|     |            | - Eliminates data loss during context compaction |
|     |            | - Explicit fields parameter ensures complete data |
| 2.1 | 2026-01-22 | Self-updating workflow and field merging improvements |
|     |            | - Added sync_cache.py for ADO query synchronization |
|     |            | - Added run_assessment.py for workflow orchestration |
|     |            | - Dynamic query GUIDs instead of hardcoded IDs |
|     |            | - Smart field merging: keeps non-empty/more complete values |
|     |            | - Fixed metadata fields (CreatedBy, dates) now properly merged |
| 2.2 | 2026-01-22 | Windows compatibility fix |
|     |            | - Replaced emoji characters with ASCII equivalents |
|     |            | - Scripts now run cleanly on Windows console |
