# ─────────────────────────────────────────────────────────────────────────────
#  setup_local_claude.ps1
#  One-shot setup for a LOCAL Claude Code session with Obsidian vault access.
#  Run this ONCE on the Windows machine that has your Obsidian vault.
#
#  Usage (PowerShell, in the repo folder):
#     powershell -ExecutionPolicy Bypass -File .\setup_local_claude.ps1
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

$VAULT = "C:\Users\ravin\Documents\Dermatology venereology and leprosy"
$REPO  = "C:\Users\ravin\Desktop\Obsidian_Daily_Quiz"

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  [!]  $msg" -ForegroundColor Yellow }

Write-Host "Claude Code + Obsidian MCP local setup" -ForegroundColor White

# 1 ── Node.js (needed for npx / the MCP server) ──────────────────────────────
Write-Step "Checking Node.js"
try {
    $nodeVer = node --version
    Write-Ok "Node.js found: $nodeVer"
} catch {
    Write-Warn "Node.js NOT found. Install it first from https://nodejs.org (LTS), then re-run this script."
    Start-Process "https://nodejs.org/en/download"
    exit 1
}

# 2 ── Install Claude Code CLI ────────────────────────────────────────────────
Write-Step "Installing Claude Code CLI"
try {
    $claudeVer = claude --version 2>$null
    Write-Ok "Claude Code already installed: $claudeVer"
} catch {
    Write-Host "  Installing @anthropic-ai/claude-code globally via npm..."
    npm install -g @anthropic-ai/claude-code
    Write-Ok "Claude Code installed"
}

# 3 ── Verify the vault path exists ───────────────────────────────────────────
Write-Step "Checking Obsidian vault path"
if (Test-Path $VAULT) {
    $mdCount = (Get-ChildItem -Path $VAULT -Recurse -Filter *.md -ErrorAction SilentlyContinue).Count
    Write-Ok "Vault found: $VAULT"
    Write-Ok "$mdCount markdown notes detected"
} else {
    Write-Warn "Vault NOT found at: $VAULT"
    Write-Warn "Edit the `$VAULT line at the top of this script AND the path in .mcp.json,"
    Write-Warn "then re-run."
    exit 1
}

# 4 ── Pre-warm the Obsidian MCP server (downloads it via npx) ─────────────────
Write-Step "Pre-downloading the Obsidian MCP server"
try {
    Start-Process -FilePath "cmd" -ArgumentList "/c npx -y obsidian-mcp `"$VAULT`" --help" -NoNewWindow -Wait -TimeoutSec 120 2>$null
    Write-Ok "obsidian-mcp package cached"
} catch {
    Write-Warn "Could not pre-warm obsidian-mcp (it will download on first run instead). Continuing."
}

# 5 ── Done ───────────────────────────────────────────────────────────────────
Write-Step "Setup complete"
Write-Host @"

  Next steps:
  1. Open a terminal in this repo folder:
        cd "$REPO"
  2. Start Claude Code:
        claude
  3. The repo's .mcp.json auto-loads the 'obsidian' server.
     Approve it when Claude Code asks to trust the MCP server.
  4. Verify with:
        /mcp          (should list 'obsidian' connected)
     or just ask:  "List the folders in my Obsidian vault."

  Then ask things like:
     "Read my Quiz Prediction Model note and make 30 tough questions, then
      write them to daily_questions.json and push to GitHub."

"@ -ForegroundColor White
