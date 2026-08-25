@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE="

if exist "%PROJECT_DIR%venv\Scripts\python.exe" (
    "%PROJECT_DIR%venv\Scripts\python.exe" -c "print('ok')" >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=%PROJECT_DIR%venv\Scripts\python.exe"
)

if "%PYTHON_EXE%"=="" (
    where py >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=py -3"
)

if "%PYTHON_EXE%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=python"
)

if "%PYTHON_EXE%"=="" (
    if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
        set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    )
)

if "%PYTHON_EXE%"=="" (
    echo Python не найден. Установите Python 3.11+ или запустите мост через окружение Codex.
    pause
    exit /b 1
)

%PYTHON_EXE% -m pip show hidapi >nul 2>nul
if errorlevel 1 (
    echo Устанавливаю hidapi...
    %PYTHON_EXE% -m pip install hidapi==0.14.0.post4
    if errorlevel 1 (
        echo Не удалось установить hidapi.
        pause
        exit /b 1
    )
)

echo Запускаю локальный мост сканера DEJ-380...
%PYTHON_EXE% "%PROJECT_DIR%scanner_agent.py" --host 0.0.0.0 --port 8765
