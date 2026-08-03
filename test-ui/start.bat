@echo off
setlocal EnableExtensions

REM Autodesk-MCP test UI — uses test-ui\.env for LLM settings
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "VENV=%ROOT%\.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PORT=8080"
set "ENVFILE=%ROOT%\test-ui\.env"

if not exist "%PY%" (
  echo Creating virtualenv...
  py -3 -m venv "%VENV%"
  if errorlevel 1 (
    echo Failed to create venv. Is Python installed as "py"?
    pause
    exit /b 1
  )
)

echo Ensuring dependencies...
"%PY%" -m pip install -q -r "%ROOT%\test-ui\requirements.txt"
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)

if not exist "%ENVFILE%" (
  copy "%ROOT%\test-ui\.env.example" "%ENVFILE%" >nul
  echo Created test-ui\.env from .env.example
  echo.
  echo *** Edit test-ui\.env and set LLM_API_KEY for OpenAI ***
  echo     Or run test-ui\setup-openai.bat
  echo.
  pause
)

REM Load simple KEY=VALUE lines from .env into this process (no override of existing)
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENVFILE%") do (
  if not "%%A"=="" if not defined %%A set "%%A=%%B"
)

if "%RAG_BACKEND%"=="" set "RAG_BACKEND=local"

REM If still no key / still demo, warn
if /I "%LLM_MODE%"=="demo" goto :warn_demo
if "%LLM_API_KEY%"=="" if /I not "%LLM_MODE%"=="demo" goto :warn_key
goto :run

:warn_demo
echo.
echo LLM_MODE=demo — keyword mock only, not a real model.
echo Run test-ui\setup-openai.bat  OR set Ollama and LLM_MODE=auto in .env
echo.
goto :run

:warn_key
echo.
echo LLM_API_KEY is empty. OpenAI live chat will fail.
echo Run test-ui\setup-openai.bat
echo.

:run
echo.
echo LLM_MODE=%LLM_MODE%  MODEL=%LLM_MODEL%
echo Starting test UI on http://127.0.0.1:%PORT%
echo Close this window to stop.
echo.

start "" "http://127.0.0.1:%PORT%/"
"%PY%" -m uvicorn test_ui_app.main:app --app-dir "%ROOT%\test-ui" --host 127.0.0.1 --port %PORT%

echo.
echo Server stopped.
pause
