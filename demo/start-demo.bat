@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Full demo: Docker Desktop K8s + AnythingLLM + Ollama
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "K8S=%ROOT%\k8s\anythingllm"
set "WINGET=%LocalAppData%\Microsoft\WindowsApps\winget.exe"
set "DOCKER_DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set "DOCKER=%ProgramFiles%\Docker\Docker\resources\bin\docker.exe"
set "KUBECTL=%ProgramFiles%\Docker\Docker\resources\bin\kubectl.exe"

echo === Autodesk-MCP demo bootstrap ===
echo.

REM --- Docker CLI on PATH for this session ---
if exist "%ProgramFiles%\Docker\Docker\resources\bin" (
  set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
)

where docker >nul 2>&1
if errorlevel 1 (
  if exist "%DOCKER%" (
    set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
  ) else (
    echo Docker not found. Installing Docker Desktop via winget...
    echo Approve the Windows admin / UAC prompt if it appears.
    if exist "%WINGET%" (
      "%WINGET%" install --id Docker.DockerDesktop -e --accept-package-agreements --accept-source-agreements
    ) else (
      echo winget missing. Install Docker Desktop manually:
      echo https://www.docker.com/products/docker-desktop/
      pause
      exit /b 1
    )
    if not exist "%DOCKER_DESKTOP%" (
      echo Docker Desktop install did not finish. Reboot if asked, then re-run this script.
      pause
      exit /b 1
    )
  )
)

REM --- Start Docker Desktop ---
if exist "%DOCKER_DESKTOP%" (
  echo Starting Docker Desktop...
  start "" "%DOCKER_DESKTOP%"
)

echo Waiting for Docker engine...
set /a N=0
:wait_docker
set /a N+=1
docker info >nul 2>&1
if not errorlevel 1 goto docker_ready
if !N! GEQ 90 (
  echo Docker engine did not become ready. Open Docker Desktop and wait until it says Running, then re-run.
  pause
  exit /b 1
)
timeout /t 5 /nobreak >nul
goto wait_docker

:docker_ready
echo Docker is ready.

REM --- Enable Kubernetes ---
echo Ensuring Kubernetes is available...
kubectl cluster-info >nul 2>&1
if errorlevel 1 (
  echo.
  echo Kubernetes is not running yet.
  echo In Docker Desktop: Settings -^> Kubernetes -^> Enable Kubernetes -^> Apply ^& Restart
  echo Then re-run this script.
  echo.
  echo Meanwhile starting AnythingLLM with Compose on port 3188...
  call "%ROOT%\demo\start-demo-compose.bat"
  exit /b %ERRORLEVEL%
)

REM --- Ollama ---
where ollama >nul 2>&1
if errorlevel 1 (
  if exist "%LocalAppData%\Programs\Ollama\ollama.exe" (
    set "PATH=%LocalAppData%\Programs\Ollama;%PATH%"
  )
)
where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama not on PATH. Install from https://ollama.com then re-run.
  echo ^(Or set LLM in AnythingLLM UI to any provider.^)
) else (
  echo Pulling qwen2.5:7b ^(Ollama^)...
  start "" /b ollama serve >nul 2>&1
  ollama pull qwen2.5:7b
)

REM --- Deploy AnythingLLM to K8s ---
echo Deploying AnythingLLM to Kubernetes...
kubectl apply -k "%K8S%"
kubectl -n autodesk-mcp-demo rollout status deploy/anythingllm --timeout=300s

echo.
echo ============================================
echo  AnythingLLM demo:  http://localhost:30080
echo  Namespace:         autodesk-mcp-demo
echo ============================================
echo In UI: confirm Ollama + qwen2.5:7b, create workspace, upload PDF, chat.
echo.
start "" "http://localhost:30080/"
pause
