@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"

echo Stopping Compose AnythingLLM ^(if any^)...
docker compose -f docker\compose.anythingllm.yml down 2>nul

echo Deleting K8s demo namespace ^(if any^)...
kubectl delete namespace autodesk-mcp-demo --ignore-not-found 2>nul

echo Done.
pause
