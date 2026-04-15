# Ticket Quality

Automated quality grading for Azure DevOps work items (Features and User Stories). Grades tickets A-F based on completeness, clarity, and testability. Two modes: interactive (Claude Code + Python) and automated (n8n workflow).

## Tech Stack

- **Language:** Python 3.x
- **Automation:** n8n (optional, for scheduled runs)
- **Data Source:** Azure DevOps REST API (via saved queries)
- **Output:** CSV reports + text summaries

## Key Scripts

- `extract_and_assess.py` — Main quality assessment engine (grades A-F, 100-point scoring)
- `run_assessment.py` — Workflow orchestrator
- `config.py` — ADO query GUIDs and project settings
- `save_to_cache.py` — Saves MCP-fetched data to local cache
- `sync_cache.py` — Syncs cache with ADO queries
- `check_cache.py` — Cache status checker
- `ado_orphaned_tickets.py` — Finds orphaned/stale tickets
- `va_ticket_export.py` — VA-specific ticket export
- `install.ps1` — Windows installer script

## Key Directories

- `n8n/` — n8n workflow files (14-node automated pipeline)

## Running

```powershell
# Interactive mode (requires Claude Code MCP setup)
python extract_and_assess.py

# Check cached data
python check_cache.py

# Find orphaned tickets
python ado_orphaned_tickets.py
```

## Grading Methodology

100-point scale across 8 dimensions (WHAT, WHO, WHY, HOW, DONE, EDGE + description/AC substance). Critical caps: AC < 15 words = max C, Description < 10 words = max D.

## Dependencies

Requires ADO PAT for API access. See `INSTALL_AND_USAGE.md` for full setup.
