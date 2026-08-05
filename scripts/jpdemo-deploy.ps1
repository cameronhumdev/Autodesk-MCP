# From Windows: push (optional) + pull on jp-demo + start tmux stack session.
# Usage:
#   pwsh scripts\jpdemo-deploy.ps1
#   pwsh scripts\jpdemo-deploy.ps1 -NoPush
#   pwsh scripts\jpdemo-deploy.ps1 -Attach
param(
  [switch]$NoPush,
  [switch]$Attach
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$env:Path = "C:\Users\Cameron\AppData\Local\Microsoft\WinGet\Links;C:\Program Files\PuTTY;" + $env:Path
if (-not $env:BW_SESSION) {
  $env:BW_SESSION = (Get-Content "$env:USERPROFILE\.config\bitwarden\session" -Raw).Trim()
}
$pass = bw get password "JP DEMO"
$user = bw get username "JP DEMO"
$target = "${user}@192.168.1.169"

if (-not $NoPush) {
  Write-Host "==> git push origin HEAD"
  git push origin HEAD
}

Write-Host "==> remote pull + tmux start"
$remote = @'
set -euo pipefail
cd /opt/adsk-mcp-cloud
# bootstrap scripts if this is an old tree without them yet
if [ ! -f scripts/jpdemo-pull.sh ]; then
  git fetch origin && git pull --ff-only origin main
fi
bash scripts/jpdemo-pull.sh
ATTACH=0 bash scripts/jpdemo-tmux.sh
tmux ls
curl -fsS http://127.0.0.1:8790/v1/health; echo
curl -sS -o /dev/null -w "anythingllm_http=%{http_code}\n" http://127.0.0.1:3188/
echo "OK — attach with: ssh jp-demo -t 'tmux attach -t adsk-mcp'"
'@
$remote = $remote -replace "`r`n", "`n"
$tmp = Join-Path $env:TEMP "jpdemo-deploy-remote.sh"
[IO.File]::WriteAllText($tmp, $remote)
& pscp -batch -pw $pass $tmp "${target}:/tmp/jpdemo-deploy-remote.sh"
& plink -ssh -batch $target -pw $pass "bash /tmp/jpdemo-deploy-remote.sh"
Remove-Item $tmp -Force

if ($Attach) {
  Write-Host "==> attaching tmux (Ctrl-b d to detach)"
  & plink -ssh $target -pw $pass -t "tmux attach -t adsk-mcp"
}
