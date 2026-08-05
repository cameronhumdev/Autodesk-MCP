# Port-forward jp-demo cloud stack to this PC (AnythingLLM + gateway).
# Usage: pwsh scripts\tunnel-jpdemo.ps1
# Then:  http://127.0.0.1:13188  and  http://127.0.0.1:18790/v1/health
$ErrorActionPreference = "Stop"
$HostAlias = if ($env:JPDEMO_SSH) { $env:JPDEMO_SSH } else { "jp-demo" }
Write-Host "Tunneling $HostAlias -> localhost:13188 (AnythingLLM), :18790 (gateway)"
Write-Host "Leave this window open. Ctrl+C to stop."
ssh -N -L 18790:127.0.0.1:8790 -L 13188:127.0.0.1:3188 $HostAlias
