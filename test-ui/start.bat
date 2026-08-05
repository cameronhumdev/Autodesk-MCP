@echo off
setlocal EnableExtensions

REM Full local pipeline: Ollama LLM + local RAG + real Inventor/AutoCAD MCP
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "VENV=%ROOT%\.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PORT=8787"
set "ENVFILE=%ROOT%\test-ui\.env"
set "PATH=%LocalAppData%\Programs\Ollama;%VENV%\Scripts;%PATH%"

REM Prefer PORT from test-ui\.env when set
if exist "%ENVFILE%" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /i /c:"PORT=" "%ENVFILE%"`) do (
    if not "%%B"=="" set "PORT=%%B"
  )
)

if not exist "%PY%" (
  echo Creating virtualenv...
  py -3 -m venv "%VENV%"
  if errorlevel 1 (
    echo Failed to create venv. Is Python installed as "py"?
    pause
    exit /b 1
  )
)

echo Ensuring dependencies ^(incl. autocad-mcp-pro^)...
"%PY%" -m pip install -q -r "%ROOT%\test-ui\requirements.txt"
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)

if not exist "%ENVFILE%" (
  copy "%ROOT%\test-ui\.env.example" "%ENVFILE%" >nul
  echo Created test-ui\.env for real MCP + Ollama
)

REM Clear stale overrides from parent environment
set "LLM_MODE="
set "LLM_BASE_URL="
set "LLM_MODEL="
set "LLM_API_KEY="
set "INVENTOR_BACKEND="
set "AUTOCAD_BACKEND="

where ollama >nul 2>&1
if not errorlevel 1 (
  start "" /b ollama serve >nul 2>&1
)

echo.
echo ============================================================
echo  Autodesk-MCP local app  http://127.0.0.1:%PORT%
echo  LLM: Ollama   RAG: local   CAD: real MCP ^(not mock^)
echo  Inventor: open manually or Confirm when the assistant asks
echo  AutoCAD:  open manually or Confirm when asked ^(opens a new drawing^)
echo            Status/startup will NOT launch AutoCAD
echo ============================================================
echo.

start "" "http://127.0.0.1:%PORT%/"
"%PY%" -m uvicorn test_ui_app.main:app --app-dir "%ROOT%\test-ui" --host 127.0.0.1 --port %PORT% --reload

echo.
echo Server stopped.
pause
