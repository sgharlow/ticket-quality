# n8n ADO Ticket Quality Assessment - Prerequisites Checklist

Use this checklist to ensure everything is ready before importing and configuring the workflow.

## 1. n8n Instance Requirements

- [ ] **n8n installed and accessible**
  - Self-hosted: Docker, npm, or desktop app
  - Cloud: n8n.cloud account active
  - Version: 1.0.0 or higher recommended

- [ ] **Required n8n nodes available**
  - Schedule Trigger (built-in)
  - Manual Trigger (built-in)
  - HTTP Request (built-in)
  - Code (built-in)
  - IF (built-in)
  - Merge (built-in)
  - Email Send OR Microsoft Outlook (for notifications)
  - Slack (optional, for Slack notifications)

## 2. Azure DevOps Requirements

### 2.1 Access & Permissions
- [ ] **ADO Organization access**
  - Organization name: `opusinspection` (or your org)
  - URL format: `https://dev.azure.com/{organization}`

- [ ] **Project access**
  - Project name: `A TDC Master Project` (or your project)
  - Read access to Work Items

- [ ] **Saved Queries exist**
  - Queries return Features and/or User Stories
  - Query GUIDs noted (from query URL)
  - Current queries:
    - Q1 2026 Committed Features: `973996cc-b2c6-49fe-935b-f043f474f4cd`
    - Q1 2026 Committed User Stories: `1e9d9cc6-ffee-4ed3-a8d1-b8881451b294`

### 2.2 Authentication (Choose One)

#### Option A: Personal Access Token (Simpler)
- [ ] **PAT Created**
  - Go to: `https://dev.azure.com/{org}/_usersSettings/tokens`
  - Click "New Token"
  - Name: `n8n-ticket-quality`
  - Expiration: Set appropriate duration (max 1 year)
  - Scopes: Work Items → Read
  - Copy and save token securely

- [ ] **PAT Credentials in n8n**
  - Create "Header Auth" credential
  - Header Name: `Authorization`
  - Header Value: `Basic {base64(:{PAT})}`
  - Note: Use empty username, just colon before PAT

#### Option B: OAuth2 / Azure AD App (More Secure)
- [ ] **Azure AD App Registration**
  - Go to: Azure Portal → Azure Active Directory → App registrations
  - New registration
  - Name: `n8n-ado-ticket-quality`
  - Redirect URI: `https://your-n8n-instance/rest/oauth2-credential/callback`

- [ ] **API Permissions configured**
  - Add permission → APIs my organization uses
  - Search: Azure DevOps
  - Delegated: `user_impersonation`
  - Grant admin consent

- [ ] **Client Secret created**
  - Certificates & secrets → New client secret
  - Copy and save securely

- [ ] **OAuth2 Credential in n8n**
  - Create "OAuth2 API" credential
  - Grant Type: Authorization Code
  - Authorization URL: `https://app.vssps.visualstudio.com/oauth2/authorize`
  - Access Token URL: `https://app.vssps.visualstudio.com/oauth2/token`
  - Client ID: From app registration
  - Client Secret: From app registration
  - Scope: `499b84ac-1321-427f-aa17-267ca6975798/.default`

## 3. Notification Setup (Optional)

### Email Notifications
- [ ] **SMTP configured** (for Email Send node)
  - SMTP server address
  - Port (usually 587 for TLS)
  - Username/password or OAuth
  - From address

- [ ] **OR Microsoft 365 configured** (for Outlook node)
  - OAuth2 credentials for Microsoft Graph
  - Mail.Send permission

### Slack Notifications
- [ ] **Slack App created** (for Slack node)
  - Go to: api.slack.com/apps
  - Create new app
  - OAuth scopes: `chat:write`
  - Install to workspace
  - Copy Bot User OAuth Token

- [ ] **OR Webhook URL** (simpler)
  - Go to: Slack → Apps → Incoming Webhooks
  - Create webhook for target channel
  - Copy webhook URL

## 4. Pre-Import Checklist

Before importing the workflow:

- [ ] All credentials created in n8n
- [ ] Test ADO API access manually:
  ```
  curl -u :{PAT} "https://dev.azure.com/{org}/{project}/_apis/wit/queries/{query-guid}?api-version=7.1-preview.2"
  ```
- [ ] Verify query returns expected work items
- [ ] Decide on schedule (default: Monday 8 AM)
- [ ] Identify email recipients

## 5. Post-Import Configuration

After importing `ado_ticket_quality_workflow.json`:

1. [ ] **Update HTTP Request credentials**
   - Select your ADO credential in both HTTP Request nodes

2. [ ] **Update Organization/Project**
   - Edit "Execute ADO Query" node
   - Update URL with your org/project

3. [ ] **Update Query GUIDs**
   - Edit "Configuration" Code node
   - Update `ADO_QUERIES` array with your query GUIDs

4. [ ] **Configure notifications**
   - Edit Email/Slack nodes with your settings
   - Or delete if not needed

5. [ ] **Test manually**
   - Click "Execute Workflow" with Manual Trigger
   - Verify all nodes execute successfully
   - Check output CSV format

6. [ ] **Activate workflow**
   - Toggle workflow to Active
   - Verify schedule trigger is set correctly

## 6. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Check PAT expiration, verify scopes |
| 404 Not Found | Verify org/project name, query GUID |
| Empty results | Check query returns data in ADO web |
| Timeout on batch fetch | Reduce batch size in Code node |
| Email not sending | Verify SMTP credentials, check spam |

### API Testing Commands

```bash
# Test PAT authentication
curl -u :{YOUR_PAT} "https://dev.azure.com/opusinspection/_apis/projects?api-version=7.1-preview.4"

# Test query execution
curl -u :{YOUR_PAT} "https://dev.azure.com/opusinspection/A%20TDC%20Master%20Project/_apis/wit/wiql/973996cc-b2c6-49fe-935b-f043f474f4cd?api-version=7.1-preview.2"

# Test work item fetch
curl -u :{YOUR_PAT} "https://dev.azure.com/opusinspection/A%20TDC%20Master%20Project/_apis/wit/workitems?ids=12345&api-version=7.1-preview.3"
```

## 7. Maintenance

### Regular Tasks
- [ ] Monitor PAT expiration (set calendar reminder)
- [ ] Review query results periodically (ensure they capture intended tickets)
- [ ] Update queries for new quarters/sprints
- [ ] Review grade distribution trends

### Quarterly Updates
- [ ] Create new ADO queries for upcoming quarter
- [ ] Update query GUIDs in Configuration node
- [ ] Archive previous quarter's reports
