# ADO Ticket Quality Assessment - n8n Implementation Plan

## Overview

This plan details how to rebuild the ticket-quality assessment system in n8n workflow automation platform.

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Trigger   │────▶│  Fetch ADO  │────▶│   Assess    │────▶│   Report    │
│  (Schedule) │     │    Data     │     │   Quality   │     │  & Notify   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

---

## Workflow Components

### 1. Trigger Node
**Type:** Schedule Trigger or Manual Trigger

```
Schedule: Daily at 6:00 AM
- or -
Manual: On-demand execution
```

### 2. ADO Authentication
**Type:** HTTP Request with OAuth2 or PAT

**Option A: Personal Access Token (Simpler)**
```json
{
  "headers": {
    "Authorization": "Basic {{ $base64encode(':' + $credentials.adoPAT) }}"
  }
}
```

**Option B: Azure AD OAuth (More Secure)**
- Use n8n's OAuth2 credential type
- Configure Azure AD app registration
- Scope: `499b84ac-1321-427f-aa17-267ca6975798/.default`

### 3. Fetch Query Results
**Type:** HTTP Request Node

**Endpoint:**
```
POST https://dev.azure.com/{organization}/{project}/_apis/wit/wiql/{queryId}?api-version=7.0
```

**For each query:**
- Q1 2026 Committed Features: `973996cc-b2c6-49fe-935b-f043f474f4cd`
- Q1 2026 Committed User Stories: `1e9d9cc6-ffee-4ed3-a8d1-b8881451b294`

**Response Processing:**
```javascript
// Extract work item IDs from query results
const workItemIds = items.json.workItems.map(wi => wi.id);
return [{ json: { ids: workItemIds } }];
```

### 4. Batch Fetch Work Items
**Type:** Loop Over Items + HTTP Request

**Endpoint:**
```
POST https://dev.azure.com/{organization}/{project}/_apis/wit/workitemsbatch?api-version=7.0
```

**Request Body:**
```json
{
  "ids": [/* batch of up to 200 IDs */],
  "fields": [
    "System.Id",
    "System.WorkItemType",
    "System.Title",
    "System.Description",
    "Microsoft.VSTS.Common.AcceptanceCriteria",
    "System.CreatedBy",
    "System.State",
    "System.AreaPath",
    "Microsoft.VSTS.Scheduling.StartDate",
    "Microsoft.VSTS.Scheduling.TargetDate"
  ]
}
```

**Batching Logic (Code Node):**
```javascript
const allIds = $input.first().json.ids;
const batchSize = 200;
const batches = [];

for (let i = 0; i < allIds.length; i += batchSize) {
  batches.push({
    json: {
      ids: allIds.slice(i, i + batchSize),
      batchNumber: Math.floor(i / batchSize) + 1
    }
  });
}

return batches;
```

### 5. Quality Assessment (Code Node)
**Type:** Code Node (JavaScript)

```javascript
// Quality Assessment Algorithm
function assessTicket(item) {
  const fields = item.fields;
  const title = fields['System.Title'] || '';
  const description = stripHtml(fields['System.Description'] || '');
  const ac = stripHtml(fields['Microsoft.VSTS.Common.AcceptanceCriteria'] || '');
  const startDate = fields['Microsoft.VSTS.Scheduling.StartDate'];
  const targetDate = fields['Microsoft.VSTS.Scheduling.TargetDate'];

  let score = 0;
  let rationale = [];

  // === QUANTITATIVE SCORING (25 points) ===

  // Description Substance (12 points)
  const descWords = description.split(/\s+/).filter(w => w.length > 0).length;
  if (descWords >= 50) {
    score += 12;
  } else if (descWords >= 30) {
    score += 9;
  } else if (descWords >= 15) {
    score += 6;
  } else if (descWords >= 5) {
    score += 3;
  }

  // AC Substance (13 points)
  const acWords = ac.split(/\s+/).filter(w => w.length > 0).length;
  if (acWords >= 50) {
    score += 13;
  } else if (acWords >= 30) {
    score += 10;
  } else if (acWords >= 15) {
    score += 7;
  } else if (acWords >= 5) {
    score += 4;
  }

  // === QUALITATIVE SCORING (75 points) ===
  const combinedText = (title + ' ' + description + ' ' + ac).toLowerCase();

  // WHAT - Actions Defined (15 points)
  const actionPatterns = /\b(shall|must|will|should|can|allow|enable|provide|display|show|create|update|delete|send|receive|process|validate|calculate)\b/gi;
  const actionMatches = combinedText.match(actionPatterns) || [];
  if (actionMatches.length >= 5) score += 15;
  else if (actionMatches.length >= 3) score += 10;
  else if (actionMatches.length >= 1) score += 5;

  // WHO - Actor Identified (10 points)
  const actorPatterns = /\b(user|admin|administrator|system|customer|inspector|manager|operator|technician|as a)\b/gi;
  const actorMatches = combinedText.match(actorPatterns) || [];
  if (actorMatches.length >= 2) score += 10;
  else if (actorMatches.length >= 1) score += 5;

  // WHY - Business Context (10 points)
  const whyPatterns = /\b(so that|in order to|because|to enable|to allow|to ensure|to support|requirement|compliance|business)\b/gi;
  const whyMatches = combinedText.match(whyPatterns) || [];
  if (whyMatches.length >= 2) score += 10;
  else if (whyMatches.length >= 1) score += 5;

  // HOW - Implementation Clarity (20 points)
  const howPatterns = /\b(when|if|then|click|select|enter|navigate|button|field|screen|page|form|api|endpoint|database|table)\b/gi;
  const howMatches = combinedText.match(howPatterns) || [];
  if (howMatches.length >= 8) score += 20;
  else if (howMatches.length >= 5) score += 15;
  else if (howMatches.length >= 3) score += 10;
  else if (howMatches.length >= 1) score += 5;

  // DONE - Testable Criteria (15 points)
  const donePatterns = /\b(verify|confirm|check|test|ensure|validate|expected|result|outcome|success|fail|error|given|when|then)\b/gi;
  const doneMatches = combinedText.match(donePatterns) || [];
  if (doneMatches.length >= 5) score += 15;
  else if (doneMatches.length >= 3) score += 10;
  else if (doneMatches.length >= 1) score += 5;

  // EDGE - Exception Handling (5 points)
  const edgePatterns = /\b(error|exception|invalid|fail|edge case|boundary|limit|maximum|minimum|timeout|retry)\b/gi;
  const edgeMatches = combinedText.match(edgePatterns) || [];
  if (edgeMatches.length >= 2) score += 5;
  else if (edgeMatches.length >= 1) score += 3;

  // === CRITICAL CAPS ===
  let maxGrade = 'A';

  if (acWords < 15) {
    maxGrade = 'C';
    rationale.push('AC too short (<15 words)');
  }

  if (descWords < 10) {
    maxGrade = maxGrade === 'C' ? 'F' : 'D';
    rationale.push('Description too short (<10 words)');
  }

  if (descWords === 0 && acWords === 0) {
    maxGrade = 'F';
    score = 0;
    rationale.push('No Description or AC');
  }

  // === DETERMINE GRADE ===
  let grade;
  if (score >= 75) grade = 'A';
  else if (score >= 55) grade = 'B';
  else if (score >= 35) grade = 'C';
  else if (score >= 20) grade = 'D';
  else grade = 'F';

  // Apply cap
  const gradeOrder = ['F', 'D', 'C', 'B', 'A'];
  if (gradeOrder.indexOf(grade) > gradeOrder.indexOf(maxGrade)) {
    grade = maxGrade;
    rationale.push(`Capped at ${maxGrade}`);
  }

  // === PRELIM TAGGING ===
  let isPrelim = false;
  if (startDate) {
    const start = new Date(startDate);
    const now = new Date();
    const daysUntilStart = (start - now) / (1000 * 60 * 60 * 24);
    if (daysUntilStart > 7) {
      isPrelim = true;
      grade = `Prelim: ${grade}`;
    }
  }

  return {
    id: fields['System.Id'],
    workItemType: fields['System.WorkItemType'],
    title: title,
    state: fields['System.State'],
    createdBy: extractName(fields['System.CreatedBy']),
    areaPath: fields['System.AreaPath'],
    startDate: startDate ? startDate.split('T')[0] : '',
    targetDate: targetDate ? targetDate.split('T')[0] : '',
    grade: grade,
    score: score,
    rationale: rationale.join('; ') || 'Standard scoring',
    isPrelim: isPrelim,
    descWords: descWords,
    acWords: acWords
  };
}

function stripHtml(html) {
  return html.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
}

function extractName(createdBy) {
  if (!createdBy) return '(Unknown)';
  if (typeof createdBy === 'string') {
    return createdBy.split('<')[0].trim();
  }
  return createdBy.displayName || '(Unknown)';
}

// Process all items
const results = [];
for (const item of $input.all()) {
  results.push({ json: assessTicket(item.json) });
}

return results;
```

### 6. Generate Summary Statistics (Code Node)

```javascript
const items = $input.all().map(i => i.json);

// Grade distribution
const grades = { A: 0, B: 0, C: 0, D: 0, F: 0 };
const byCreator = {};
let prelimCount = 0;
let imminentCount = 0;

for (const item of items) {
  const baseGrade = item.grade.replace('Prelim: ', '');
  grades[baseGrade]++;

  if (item.isPrelim) prelimCount++;
  else imminentCount++;

  const creator = item.createdBy;
  if (!byCreator[creator]) {
    byCreator[creator] = { F: [], D: [], C: [], B: [], A: [] };
  }
  byCreator[creator][baseGrade].push(item.id);
}

// Risk assessment
const fGradeImminent = items.filter(i => !i.isPrelim && i.grade === 'F');
const dGradeImminent = items.filter(i => !i.isPrelim && i.grade === 'D');

return [{
  json: {
    totalTickets: items.length,
    grades: grades,
    gradePercentages: {
      A: ((grades.A / items.length) * 100).toFixed(1),
      B: ((grades.B / items.length) * 100).toFixed(1),
      C: ((grades.C / items.length) * 100).toFixed(1),
      D: ((grades.D / items.length) * 100).toFixed(1),
      F: ((grades.F / items.length) * 100).toFixed(1)
    },
    prelimCount: prelimCount,
    imminentCount: imminentCount,
    fGradeImminentCount: fGradeImminent.length,
    dGradeImminentCount: dGradeImminent.length,
    byCreator: byCreator,
    generatedAt: new Date().toISOString()
  }
}];
```

### 7. Generate CSV Report (Code Node)

```javascript
const items = $input.all().map(i => i.json);

// CSV Header
const headers = ['ID', 'Work Item Type', 'Title', 'State', 'Created By',
                 'Start Date', 'Target Date', 'Grade', 'Score', 'Rationale'];

// CSV Rows
const rows = items.map(item => [
  item.id,
  item.workItemType,
  `"${item.title.replace(/"/g, '""')}"`,
  item.state,
  item.createdBy,
  item.startDate,
  item.targetDate,
  item.grade,
  item.score,
  `"${item.rationale.replace(/"/g, '""')}"`
]);

const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');

return [{
  json: {
    csv: csv,
    filename: `ticket_quality_report_${new Date().toISOString().split('T')[0]}.csv`
  }
}];
```

### 8. Output Options

#### Option A: Save to SharePoint/OneDrive
**Type:** Microsoft OneDrive Node or HTTP Request

```
POST https://graph.microsoft.com/v1.0/drives/{driveId}/items/{folderId}:/{filename}:/content
Content-Type: text/csv

{csv content}
```

#### Option B: Send Email Summary
**Type:** Send Email Node (SMTP or Microsoft 365)

```javascript
// Email body template
const summary = $('Generate Summary').first().json;
const body = `
ADO Ticket Quality Report - ${new Date().toLocaleDateString()}

GRADE DISTRIBUTION
==================
A: ${summary.grades.A} (${summary.gradePercentages.A}%)
B: ${summary.grades.B} (${summary.gradePercentages.B}%)
C: ${summary.grades.C} (${summary.gradePercentages.C}%)
D: ${summary.grades.D} (${summary.gradePercentages.D}%)
F: ${summary.grades.F} (${summary.gradePercentages.F}%)

Total: ${summary.totalTickets} tickets
Prelim (>7 days): ${summary.prelimCount}
Imminent (<=7 days): ${summary.imminentCount}

RISK ASSESSMENT
===============
F-grade imminent (IMMEDIATE RISK): ${summary.fGradeImminentCount}
D-grade imminent (HIGH RISK): ${summary.dGradeImminentCount}

See attached CSV for full details.
`;

return [{ json: { emailBody: body } }];
```

#### Option C: Post to Slack/Teams
**Type:** Slack or Microsoft Teams Node

```javascript
// Slack message format
const summary = $('Generate Summary').first().json;

return [{
  json: {
    blocks: [
      {
        type: "header",
        text: { type: "plain_text", text: "📊 ADO Ticket Quality Report" }
      },
      {
        type: "section",
        fields: [
          { type: "mrkdwn", text: `*Total Tickets:* ${summary.totalTickets}` },
          { type: "mrkdwn", text: `*F-Grade Imminent:* ${summary.fGradeImminentCount}` }
        ]
      },
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `*Grade Distribution:*\nA: ${summary.gradePercentages.A}% | B: ${summary.gradePercentages.B}% | C: ${summary.gradePercentages.C}% | D: ${summary.gradePercentages.D}% | F: ${summary.gradePercentages.F}%`
        }
      }
    ]
  }
}];
```

---

## Complete Workflow Structure

```
1. Schedule Trigger (Daily 6 AM)
   │
2. Set Variables (org, project, queries)
   │
3. ┌─ HTTP Request: Execute Query 1 (Features)
   │  │
   └─ HTTP Request: Execute Query 2 (User Stories)
   │
4. Merge: Combine query results
   │
5. Code: Create batches of 200 IDs
   │
6. Loop: For each batch
   │  │
   │  └─ HTTP Request: Fetch work items batch
   │
7. Merge: Combine all work items
   │
8. Code: Assess quality (scoring algorithm)
   │
9. ┌─ Code: Generate summary statistics
   │  │
   │  └─ Code: Generate CSV report
   │
10. ┌─ OneDrive: Save CSV
    │
    ├─ Email: Send summary with attachment
    │
    └─ Slack: Post summary notification
```

---

## Setup Instructions

### 1. Create Azure AD App Registration (for OAuth)

1. Go to Azure Portal > Azure Active Directory > App registrations
2. New registration:
   - Name: `n8n-ado-integration`
   - Redirect URI: `https://your-n8n-instance/rest/oauth2-credential/callback`
3. API Permissions:
   - Azure DevOps > `user_impersonation`
4. Create client secret
5. Note: Application (client) ID, Directory (tenant) ID, Client secret

### 2. Configure n8n Credentials

**Azure DevOps OAuth2:**
```
Grant Type: Authorization Code
Authorization URL: https://app.vssps.visualstudio.com/oauth2/authorize
Access Token URL: https://app.vssps.visualstudio.com/oauth2/token
Client ID: {from app registration}
Client Secret: {from app registration}
Scope: 499b84ac-1321-427f-aa17-267ca6975798/.default
```

**Or Personal Access Token:**
```
Create PAT at: https://dev.azure.com/{org}/_usersSettings/tokens
Scopes needed: Work Items (Read)
```

### 3. Import Workflow

1. Create new workflow in n8n
2. Add nodes as described above
3. Configure credentials
4. Test with manual trigger first
5. Enable schedule trigger

---

## Estimated Development Time

| Component | Time |
|-----------|------|
| ADO Authentication setup | 1-2 hours |
| Query execution nodes | 1 hour |
| Batch fetching logic | 2 hours |
| Quality scoring algorithm | 3-4 hours |
| Report generation | 2 hours |
| Output integrations | 2-3 hours |
| Testing & debugging | 3-4 hours |
| **Total** | **14-18 hours** |

---

## Advantages of n8n Implementation

1. **Scheduled Execution**: Automatic daily/weekly reports
2. **No Local Setup**: Runs on server, no desktop dependency
3. **Multi-channel Output**: Email, Slack, Teams, SharePoint
4. **Visual Workflow**: Easy to modify and maintain
5. **Audit Trail**: Execution history and logs
6. **Scalable**: Can add more queries/projects easily

---

## Limitations vs Current Solution

1. **No AI Analysis**: Heuristic scoring only (unless AI node added)
2. **No Interactive Mode**: Can't ask follow-up questions
3. **Fixed Schedule**: Less flexible than on-demand Claude Code
4. **Setup Complexity**: Requires n8n instance and Azure AD config

---

## Optional Enhancements

### Add AI-Powered Scoring
Add OpenAI/Claude node for nuanced assessment:

```javascript
// Prompt for AI scoring
const prompt = `
Assess this ADO ticket for developer-readiness. Score 0-100.

Title: ${item.title}
Description: ${item.description}
Acceptance Criteria: ${item.ac}

Consider:
- Clarity of requirements
- Testability
- Implementation guidance
- Edge case coverage

Return JSON: { "score": N, "rationale": "..." }
`;
```

### Dashboard Integration
- Power BI: Push data via HTTP
- Grafana: Store metrics in InfluxDB
- Custom dashboard: Store in PostgreSQL
