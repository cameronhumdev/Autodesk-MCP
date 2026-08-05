# Laptop CAD agent — connects OUT to jp-demo gateway; keep this window open.
# Usage:
#   $env:GATEWAY_URL = "http://192.168.1.169:8790"   # or via SSH tunnel http://127.0.0.1:18790
#   $env:LICENSE_KEY = "dev-local"
#   pwsh scripts\serve-agent.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
if (-not $env:GATEWAY_URL) { $env:GATEWAY_URL = "http://192.168.1.169:8790" }
if (-not $env:LICENSE_KEY) { $env:LICENSE_KEY = "dev-local" }
$env:DEPLOY_MODE = "local"  # MCP binaries from this PC
Write-Host "Gateway: $env:GATEWAY_URL"
Write-Host "Local MCP + outbound agent. Ctrl+C to stop."
& .\.venv\Scripts\python.exe -m client serve-agent
