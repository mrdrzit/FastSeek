@echo off
setlocal

set "ENV_NAME=fastseek"
set "APP_MODULE=src.app.run_fastseek"
set "CONDA_CMD="

echo.
echo [FastSeek Launcher]
echo.

:: --- Find conda/mamba ---
echo [INFO] Searching for conda/mamba...

for %%D in (
    "%USERPROFILE%\miniforge3"
    "%USERPROFILE%\mambaforge"
    "%USERPROFILE%\mambaforge3"
    "%USERPROFILE%\miniconda3"
    "%ProgramData%\miniforge3"
    "%ProgramData%\mambaforge"
    "%ProgramData%\mambaforge3"
    "%ProgramData%\Miniconda3"
) do (
    if not defined CONDA_CMD (
        if exist "%%~D\Scripts\mamba.exe" (
            set "CONDA_CMD=%%~D\Scripts\mamba.exe"
            echo [INFO] Found mamba at %%~D
        ) else if exist "%%~D\condabin\conda.bat" (
            set "CONDA_CMD=%%~D\condabin\conda.bat"
            echo [INFO] Found conda at %%~D
        )
    )
)

:: --- If found, test env and run ---
if defined CONDA_CMD (
    echo [INFO] Checking environment "%ENV_NAME%"...

    call "%CONDA_CMD%" run -n "%ENV_NAME%" python -c "import sys" >nul 2>&1

    if not errorlevel 1 (
        echo [INFO] Environment found. Launching FastSeek...
        call "%CONDA_CMD%" run -n "%ENV_NAME%" python -m %APP_MODULE%
        goto :end
    ) else (
        echo [WARN] Environment "%ENV_NAME%" not found or invalid.
    )
) else (
    echo [WARN] No conda/mamba installation found.
)

:: --- Fallback ---
echo [INFO] Falling back to system Python...
python -m %APP_MODULE%

:end
echo.
echo [INFO] FastSeek closed with exit code %ERRORLEVEL%.
pause
endlocal