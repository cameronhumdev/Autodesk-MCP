@echo off
setlocal EnableExtensions

REM Fallback when K8s not enabled yet — Compose AnythingLLM on :3188
cd /d "%~dp0\..\docker"

set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker CLI not found. Start Docker Desktop first.
  pause
  exit /b 1
)

echo Waiting for Docker...
:wait
docker info >nul 2>&1
if errorlevel 1 (
  timeout /t 3 /nobreak >nul
  goto wait
)

where ollama >nul 2>&1
if not errorlevel 1 (
  start "" /b ollama serve >nul 2>&1
  ollama pull qwen2.5:7b
)

echo Starting AnythingLLM ^(Compose^) on http://127.0.0.1:3188 ...
docker compose -f compose.anythingllm.yml up -d
if errorlevel 1 (
  echo Compose failed.
  pause
  exit /b 1
)

echo.
echo AnythingLLM: http://127.0.0.1:3188
echo In UI: Settings -^> LLM -^> Ollama
echo   URL: http://host.docker.internal:11434
echo   Model: qwen2.5:7b
echo.
start "" "http://127.0.0.1:3188/"
pause
