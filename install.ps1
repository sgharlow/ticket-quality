# ADO Ticket Quality Assessment - Installation Script
# Run this script on a new PC to set up the solution
#
# Version 2.2 - Windows Compatibility
#
# Usage:
#   .\install.ps1
#   .\install.ps1 -SourcePath "\\server\share\ado-ticket-quality"
#   .\install.ps1 -TargetUser "OtherUser"

param(
    [string]$SourcePath = "",  # Leave empty to skip file copy
    [string]$TargetUser = $env:USERNAME
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ADO Ticket Quality Assessment Installer" -ForegroundColor Cyan
Write-Host "Version 2.2 - Windows Compatibility" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Define paths
$DesktopPath = "C:\Users\$TargetUser\Desktop"
$ProjectPath = "$DesktopPath\ado-ticket-quality"
$ClaudePath = "C:\Users\$TargetUser\.claude"  # Must be in user profile root, NOT Desktop

# Step 1: Check prerequisites
Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow

$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Python not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}
Write-Host "  Python: $pythonVersion" -ForegroundColor Green

$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Node.js not found. Install from https://nodejs.org" -ForegroundColor Red
    exit 1
}
Write-Host "  Node.js: $nodeVersion" -ForegroundColor Green

$claudeVersion = claude --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  WARNING: Claude Code not found. Install with: npm install -g @anthropic-ai/claude-code" -ForegroundColor Yellow
}
else {
    Write-Host "  Claude Code: $claudeVersion" -ForegroundColor Green
}

# Step 2: Create directories
Write-Host ""
Write-Host "[2/5] Creating directories..." -ForegroundColor Yellow

New-Item -ItemType Directory -Path $ProjectPath -Force | Out-Null
Write-Host "  Created: $ProjectPath" -ForegroundColor Green

New-Item -ItemType Directory -Path $ClaudePath -Force | Out-Null
Write-Host "  Created: $ClaudePath" -ForegroundColor Green

# Step 3: Copy files (if source exists)
Write-Host ""
Write-Host "[3/5] Copying files..." -ForegroundColor Yellow

$filesToCopy = @(
    @{ Name = "config.py"; Dest = $ProjectPath },
    @{ Name = "check_cache.py"; Dest = $ProjectPath },
    @{ Name = "save_to_cache.py"; Dest = $ProjectPath },
    @{ Name = "sync_cache.py"; Dest = $ProjectPath },
    @{ Name = "run_assessment.py"; Dest = $ProjectPath },
    @{ Name = "extract_and_assess.py"; Dest = $ProjectPath },
    @{ Name = "INSTALL_AND_USAGE.md"; Dest = $ProjectPath }
)

# Note: mcp.json must be created manually - see documentation

if ($SourcePath -and (Test-Path $SourcePath)) {
    foreach ($file in $filesToCopy) {
        $sourcefile = Join-Path $SourcePath $file.Name
        if (Test-Path $sourcefile) {
            Copy-Item $sourcefile $file.Dest -Force
            Write-Host "  Copied: $($file.Name)" -ForegroundColor Green
        }
        else {
            Write-Host "  Not found: $($file.Name)" -ForegroundColor Yellow
        }
    }
}
else {
    Write-Host "  Source path not specified or not found." -ForegroundColor Yellow
    Write-Host "  Please copy files manually:" -ForegroundColor Yellow
    Write-Host ""
    foreach ($file in $filesToCopy) {
        Write-Host "    $($file.Name) -> $($file.Dest)\" -ForegroundColor White
    }
    Write-Host ""
}

# Step 4: Check Azure CLI
Write-Host ""
Write-Host "[4/5] Checking Azure CLI authentication..." -ForegroundColor Yellow

$azAccount = az account show 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Azure CLI not logged in. Please run:" -ForegroundColor Yellow
    Write-Host "    az login" -ForegroundColor Cyan
}
else {
    $accountInfo = $azAccount | ConvertFrom-Json
    Write-Host "  Logged in as: $($accountInfo.user.name)" -ForegroundColor Green
}

# Step 5: Summary
Write-Host ""
Write-Host "[5/5] Installation Summary" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project files installed to:" -ForegroundColor White
Write-Host "  $ProjectPath\" -ForegroundColor Green
Write-Host ""
Write-Host "MCP Configuration (YOU MUST CREATE THIS):" -ForegroundColor Yellow
Write-Host "  File: $ClaudePath\mcp.json" -ForegroundColor White
Write-Host ""
Write-Host "  Create this file with the following content:" -ForegroundColor White
Write-Host '  {' -ForegroundColor Cyan
Write-Host '    "mcpServers": {' -ForegroundColor Cyan
Write-Host '      "ado": {' -ForegroundColor Cyan
Write-Host '        "command": "npx",' -ForegroundColor Cyan
Write-Host '        "args": ["-y", "@anthropic-ai/claude-code-mcp-adapter", "npx", "-y", "@azure-devops/mcp", "opusinspection"]' -ForegroundColor Cyan
Write-Host '      }' -ForegroundColor Cyan
Write-Host '    }' -ForegroundColor Cyan
Write-Host '  }' -ForegroundColor Cyan
Write-Host ""
Write-Host "  Replace 'opusinspection' with your ADO organization name." -ForegroundColor Yellow
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. CREATE mcp.json file as shown above"
Write-Host "  2. Run: az login (if not already logged in)"
Write-Host "  3. Restart Claude Code (close and reopen)"
Write-Host "  4. Verify MCP: Ask Claude 'List ADO projects'"
Write-Host "  5. Check cache: python check_cache.py"
Write-Host "  6. Fetch data via Claude Code MCP"
Write-Host "  7. Run assessment: python extract_and_assess.py"
Write-Host ""
Write-Host "Documentation: $ProjectPath\INSTALL_AND_USAGE.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
