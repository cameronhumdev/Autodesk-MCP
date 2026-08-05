# One-time / refresh: real Inventor + AutoCAD MCP (no Docker)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
$Vendor = Join-Path $Root "vendor"

Write-Host "==> Python CAD MCP (U-C4N)"
if (-not (Test-Path $VenvPy)) { throw "Missing venv — run test-ui\start.bat once first" }
& $VenvPy -m pip install -U "autocad-mcp-pro[com]"

Write-Host "==> Clone / update ipt-mcp"
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null
$Ipt = Join-Path $Vendor "ipt-mcp"
if (-not (Test-Path (Join-Path $Ipt ".git"))) {
  git clone --depth 1 https://github.com/bimwright/ipt-mcp.git $Ipt
} else {
  git -C $Ipt pull --ff-only
}

# Prefer net9 if host has no net8 targeting pack
$ServerCsproj = Join-Path $Ipt "src\server\Bimwright.Ipt.Server.csproj"
$csproj = Get-Content $ServerCsproj -Raw
if ($csproj -match "<TargetFramework>net8\.0</TargetFramework>") {
  $csproj = $csproj -replace "<TargetFramework>net8\.0</TargetFramework>",
    "<!-- host SDK retarget --><TargetFramework>net9.0</TargetFramework>"
  Set-Content -Path $ServerCsproj -Value $csproj -NoNewline
}

Write-Host "==> Build Inventor MCP server"
dotnet build (Join-Path $Ipt "src\server\Bimwright.Ipt.Server.csproj") -c Release

Write-Host "==> Build + deploy Inventor 2027 add-in bundle"
pwsh -NoProfile -File (Join-Path $Ipt "scripts\package-bundle.ps1") -Years 2027 -Configuration Release

Write-Host ""
Write-Host "Done."
Write-Host "1) Start Inventor 2027 (add-in: Bimwright.Ipt.bundle)."
Write-Host "2) Start AutoCAD 2027 (COM backend)."
Write-Host "3) Run test-ui\start.bat"
Write-Host "Env defaults: INVENTOR_BACKEND=mcp, AUTOCAD_BACKEND=mcp, AUTOCAD_MCP_BACKEND=com"
