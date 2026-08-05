@echo off
setlocal EnableExtensions

REM AnythingLLM on http://127.0.0.1:3188  (host 3188 → container 3001)
REM Note: http://localhost:3000 is NOT this app — use 3188 or Desktop.
cd /d "%~dp0\..\docker"

where docker >nul 2>&1
if errorlevel 1 (
  echo.
  echo Docker is not installed ^(or not on PATH^).
  echo.
  echo Port 3188 only works after AnythingLLM is running in Docker.
  echo Ollama alone is NOT AnythingLLM — it only serves models.
  echo.
  echo Options:
  echo   1^) Install Docker Desktop: https://www.docker.com/products/docker-desktop/
  echo      Then re-run this script.
  echo   2^) Install AnythingLLM Desktop ^(no Docker^):
  echo      https://anythingllm.com/download
  echo      Desktop usually opens its own window ^(often API on 3001, not 3000^).
  echo   3^) Use our test UI + Ollama instead: setup-ollama.bat then start.bat
  echo      http://127.0.0.1:8787
  echo.
  pause
  exit /b 1
)

echo Starting AnythingLLM on port 3188...
docker compose -f compose.anythingllm.yml up -d
if errorlevel 1 (
  echo Failed to start. Is Docker Desktop running?
  pause
  exit /b 1
)

echo.
echo AnythingLLM UI: http://127.0.0.1:3188
echo First run: onboarding wizard → set LLM ^(OpenAI API key or Ollama^).
echo.
start "" "http://127.0.0.1:3188/"
pause
