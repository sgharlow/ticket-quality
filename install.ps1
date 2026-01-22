# ADO Ticket Quality Assessment - Installation Script
# Run this script on a new PC to set up the solution
#
# Version 2.0 - Local Caching Strategy
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
Write-Host "Version 2.0 - Local Caching Strategy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Define paths
$DesktopPath = "C:\Users\$TargetUser\Desktop"
$ProjectPath = "$DesktopPath\ado-ticket-quality"
$ClaudePath = "$DesktopPath\.claude"

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
    @{ Name = "extract_and_assess.py"; Dest = $ProjectPath },
    @{ Name = "INSTALL_AND_USAGE.md"; Dest = $ProjectPath },
    @{ Name = "mcp.json"; Dest = $ClaudePath }
)

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
Write-Host "Required files:" -ForegroundColor White
Write-Host "  $ProjectPath\config.py              - Central configuration"
Write-Host "  $ProjectPath\check_cache.py         - Cache status checker"
Write-Host "  $ProjectPath\save_to_cache.py       - Save MCP results to cache"
Write-Host "  $ProjectPath\extract_and_assess.py  - Quality assessment"
Write-Host "  $ClaudePath\mcp.json                - MCP server config"
Write-Host ""
Write-Host "Optional files:" -ForegroundColor White
Write-Host "  $ProjectPath\INSTALL_AND_USAGE.md   - Documentation"
Write-Host "  $ProjectPath\ado_workitems_cache.json - Local cache (copy if available)"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Restart Claude Code (close and reopen)"
Write-Host "  2. Run: az login (if not already logged in)"
Write-Host "  3. Check cache: python check_cache.py"
Write-Host "  4. If cache is empty/incomplete, fetch via Claude Code MCP"
Write-Host "  5. Run assessment: python extract_and_assess.py"
Write-Host ""
Write-Host "Quick test (if cache exists):" -ForegroundColor Cyan
Write-Host "  cd $ProjectPath"
Write-Host "  python extract_and_assess.py"
Write-Host ""
Write-Host "Documentation: $ProjectPath\INSTALL_AND_USAGE.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
