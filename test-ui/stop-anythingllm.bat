@echo off
cd /d "%~dp0\..\docker"
docker compose -f compose.anythingllm.yml down
echo AnythingLLM stopped.
pause
