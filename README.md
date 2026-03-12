# ADO Ticket Quality Assessment

Automated quality grading for Azure DevOps work items (Features and User Stories). Grades tickets A-F based on completeness, clarity, and testability.

## Why This Exists

- **78% of committed tickets** lacked proper documentation when first assessed
- Developers can't build what isn't defined
- This tool identifies gaps before sprint commitment

## Two Implementation Options

| Approach | Best For | Dependencies |
|----------|----------|--------------|
| **Claude Code + Python** | Interactive use, ad-hoc assessments | Python, Node.js, Claude Code |
| **n8n Workflow** | Scheduled automation, team dashboards | n8n instance, ADO PAT |

---

## Option 1: Claude Code + Python (Interactive)

Uses Claude Code with MCP (Model Context Protocol) to fetch ADO data, with Python scripts for local caching and assessment.

### Key Benefits
- Interactive - ask follow-up questions about specific tickets
- Local caching prevents data loss during long sessions
- Works within existing Claude Code workflow

### Quick Start

```powershell
# Clone the repo
git clone https://github.com/sgharlow/ticket-quality.git
cd ticket-quality

# Run the installer (copies files, shows setup instructions)
.\install.ps1

# After MCP setup and data fetch, run assessment
python extract_and_assess.py
```

**Full documentation:** [INSTALL_AND_USAGE.md](INSTALL_AND_USAGE.md)

---

## Option 2: n8n Workflow (Automated)

Self-contained workflow that runs on a schedule, fetches data via ADO REST API, and sends reports via email/Slack.

### Key Benefits
- Fully automated - runs on schedule without intervention
- No Python/Claude Code dependencies
- Easy to share with team (just import the workflow)
- Visual workflow editor for customization

### Quick Start

1. **Prerequisites:** n8n instance + ADO Personal Access Token
2. **Import:** `n8n/ado_ticket_quality_workflow.json` into n8n
3. **Configure:** Update credentials and query GUIDs
4. **Activate:** Enable schedule trigger

**Full documentation:** [n8n/PREREQUISITES.md](n8n/PREREQUISITES.md)

**Implementation details:** [n8n_implementation_plan.md](n8n_implementation_plan.md)

### n8n Files

| File | Purpose |
|------|---------|
| `n8n/ado_ticket_quality_workflow.json` | Importable workflow (14 nodes) |
| `n8n/config.env.example` | Configuration template |
| `n8n/test_data.json` | Sample data for testing |
| `n8n/PREREQUISITES.md` | Setup checklist |

---

## Grading Methodology

### Grade Scale

| Grade | Score | Meaning |
|-------|-------|---------|
| **A** | 75-100 | Developer-ready |
| **B** | 55-74 | Good with minor gaps |
| **C** | 35-54 | Needs clarification |
| **D** | 20-34 | Major gaps |
| **F** | 0-19 | Cannot determine what to build |

### Critical Caps

| Condition | Maximum Grade |
|-----------|---------------|
| Acceptance Criteria < 15 words | C |
| Description < 10 words | D |
| Both empty/minimal | F |

### Scoring Dimensions (100 points)

**Qualitative (75 pts):**
- WHAT - Actions Defined (15 pts)
- WHO - Actor Identified (10 pts)
- WHY - Business Context (10 pts)
- HOW - Implementation Clarity (20 pts)
- DONE - Testable Criteria (15 pts)
- EDGE - Exception Handling (5 pts)

**Quantitative (25 pts):**
- Description Substance (12 pts)
- AC Substance (13 pts)

### Prelim Tagging

Tickets with Start Date > 7 days out are prefixed "Prelim:" - they have time for improvement.

---

## Output Reports

### CSV Report
Detailed per-ticket data with ID, type, title, state, creator, dates, grade, score, and rationale.

### Summary Report
- Grade distribution (counts and percentages)
- Prelim vs Imminent breakdown
- Risk assessment (F/D grades by urgency)
- Action required by creator

---

## Configuration

Both approaches use the same ADO queries defined in `config.py`:

```python
ADO_QUERIES = {
    "Q1 2026 Committed Features": "973996cc-b2c6-49fe-935b-f043f474f4cd",
    "Q1 2026 Committed User Stories": "1e9d9cc6-ffee-4ed3-a8d1-b8881451b294"
}
```

To assess different queries, update the GUIDs (found in ADO query URLs).

---

## Repository Structure

```
ticket-quality/
├── README.md                    # This file
├── INSTALL_AND_USAGE.md         # Claude Code approach documentation
├── install.ps1                  # Windows installer script
├── config.py                    # ADO query configuration
├── check_cache.py               # Cache status checker
├── save_to_cache.py             # Save MCP results to cache
├── sync_cache.py                # Sync cache with ADO queries
├── run_assessment.py            # Workflow orchestrator
├── extract_and_assess.py        # Quality assessment engine
├── n8n_implementation_plan.md   # n8n approach details
└── n8n/
    ├── PREREQUISITES.md         # n8n setup checklist
    ├── ado_ticket_quality_workflow.json  # Importable workflow
    ├── config.env.example       # Configuration template
    └── test_data.json           # Test data for validation
```

---

## License

Internal use - Opus Inspection

## Author

Built with Claude Code (Anthropic)
